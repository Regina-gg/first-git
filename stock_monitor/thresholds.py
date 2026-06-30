from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, List

from .config import PROJECT_ROOT, load_config
from .data_providers import MarketDataProvider
from .metrics import beta, returns, safe_div
from .models import PriceBar, StockConfig, ThresholdProfile


def calibrate_stock(stock: StockConfig, bars: List[PriceBar], as_of: date, settings: Dict) -> ThresholdProfile:
    windows = settings["windows"]
    if len(bars) < windows["percentile_days"]:
        raise ValueError(f"{stock.symbol} requires at least {windows['percentile_days']} bars for calibration.")
    last20 = bars[-windows["short_mean_days"] :]
    last60 = bars[-windows["percentile_days"] :]
    avg_amount = mean([bar.amount for bar in last20])
    avg_turnover = mean([bar.turnover_rate for bar in last20])
    avg_amplitude_20 = mean([safe_div(bar.high - bar.low, bar.close) for bar in last20])
    avg_amplitude_60 = mean([safe_div(bar.high - bar.low, bar.close) for bar in last60])
    avg_turnover_60 = mean([bar.turnover_rate for bar in last60])
    stock_rets = returns(bars)
    pct_std = pstdev(stock_rets[-windows["volatility_days"] :]) if len(stock_rets[-windows["volatility_days"] :]) > 1 else 0.0
    market_rets = [bar.market_return for bar in bars[1:]]
    beta_250d = beta(stock_rets[-windows["beta_days"] :], market_rets[-windows["beta_days"] :])
    profiles = settings["stock_profiles"]
    stock_type = "balanced"
    threshold_multiplier = profiles["balanced"]["threshold_multiplier"]
    notes: List[str] = []
    if avg_amplitude_60 > profiles["high_volatility_growth"]["amplitude_min"] and avg_turnover_60 > profiles["high_volatility_growth"]["turnover_min"]:
        stock_type = "high_volatility_growth"
        threshold_multiplier = profiles[stock_type]["threshold_multiplier"]
    elif avg_amplitude_60 < profiles["low_volatility_value"]["amplitude_max"] and avg_turnover_60 < profiles["low_volatility_value"]["turnover_max"]:
        stock_type = "low_volatility_value"
        threshold_multiplier = profiles[stock_type]["threshold_multiplier"]
    funding_multiplier = 1.0
    if stock.float_market_cap_cny > profiles["large_cap_blue_chip"]["float_market_cap_min"]:
        funding_multiplier = profiles["large_cap_blue_chip"]["funding_multiplier"]
        notes.append("大盘蓝筹资金阈值放宽")
    elif stock.float_market_cap_cny < profiles["small_cap_theme"]["float_market_cap_max"]:
        funding_multiplier = profiles["small_cap_theme"]["funding_multiplier"]
        notes.append("小盘题材资金阈值收紧")
    return ThresholdProfile(
        symbol=stock.symbol,
        name=stock.name,
        as_of=as_of,
        short_mean_days=windows["short_mean_days"],
        percentile_days=windows["percentile_days"],
        volatility_days=windows["volatility_days"],
        beta_days=windows["beta_days"],
        avg_amount_20d=avg_amount,
        avg_turnover_20d=avg_turnover,
        avg_amplitude_20d=avg_amplitude_20,
        pct_change_std_20d=pct_std,
        beta_250d=beta_250d,
        stock_type=stock_type,
        threshold_multiplier=threshold_multiplier,
        funding_multiplier=funding_multiplier,
        notes=notes,
    )


def calibrate_watchlist(stocks: List[StockConfig], provider: MarketDataProvider, as_of: date) -> Dict[str, ThresholdProfile]:
    settings = load_config("config/thresholds.yaml")
    lookback = max(settings["windows"].values()) + 5
    profiles = {}
    for stock in stocks:
        bars = provider.get_history(stock, as_of, lookback)
        profiles[stock.symbol] = calibrate_stock(stock, bars, as_of, settings)
    return profiles


def save_profiles(profiles: Dict[str, ThresholdProfile], path: Path = PROJECT_ROOT / "data" / "threshold_profiles.json") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        symbol: {
            **profile.__dict__,
            "as_of": profile.as_of.isoformat(),
        }
        for symbol, profile in profiles.items()
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_profiles(path: Path = PROJECT_ROOT / "data" / "threshold_profiles.json") -> Dict[str, ThresholdProfile]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    profiles = {}
    for symbol, item in raw.items():
        item["as_of"] = date.fromisoformat(item["as_of"])
        profiles[symbol] = ThresholdProfile(**item)
    return profiles
