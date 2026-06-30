from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Iterable, List

from .models import PriceBar, StockConfig, StockMetrics, ThresholdProfile


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator else default


def returns(bars: List[PriceBar]) -> List[float]:
    return [safe_div(bars[i].close - bars[i - 1].close, bars[i - 1].close) for i in range(1, len(bars))]


def rolling_mean(values: Iterable[float]) -> float:
    values = list(values)
    return mean(values) if values else 0.0


def percentile_rank(values: List[float], current: float) -> float:
    if not values:
        return 0.0
    below_or_equal = sum(1 for value in values if value <= current)
    return below_or_equal / len(values) * 100


def moving_average(bars: List[PriceBar], days: int) -> float:
    return rolling_mean([bar.close for bar in bars[-days:]])


def rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) <= period:
        return 50.0
    gains = []
    losses = []
    for idx in range(len(closes) - period, len(closes)):
        change = closes[idx] - closes[idx - 1]
        gains.append(max(change, 0.0))
        losses.append(abs(min(change, 0.0)))
    avg_gain = rolling_mean(gains)
    avg_loss = rolling_mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def ema(values: List[float], period: int) -> List[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1 - alpha) * result[-1])
    return result


def macd_bars(closes: List[float]) -> List[float]:
    if len(closes) < 35:
        return [0.0 for _ in closes]
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    dif = [a - b for a, b in zip(ema12, ema26)]
    dea = ema(dif, 9)
    return [(d - e) * 2 for d, e in zip(dif, dea)]


def beta(stock_returns: List[float], market_returns: List[float]) -> float:
    count = min(len(stock_returns), len(market_returns))
    if count < 2:
        return 1.0
    sr = stock_returns[-count:]
    mr = market_returns[-count:]
    avg_s = mean(sr)
    avg_m = mean(mr)
    covariance = sum((s - avg_s) * (m - avg_m) for s, m in zip(sr, mr)) / count
    variance = sum((m - avg_m) ** 2 for m in mr) / count
    return safe_div(covariance, variance, 1.0)


def classify_amount_ratio(value: float) -> str:
    if value < 0.7:
        return "缩量"
    if value <= 1.3:
        return "正常"
    if value <= 1.8:
        return "放量"
    return "巨量"


def classify_trend(metrics: StockMetrics) -> str:
    score = 0
    score += 1 if metrics.ma_alignment.startswith("多头") else -1 if metrics.ma_alignment.startswith("空头") else 0
    score += 1 if metrics.main_fund_strength > 0.05 else -1 if metrics.main_fund_strength < -0.05 else 0
    score += 1 if metrics.amount_ratio > 1.3 and metrics.pct_change > 0 else -1 if metrics.amount_ratio > 1.3 and metrics.pct_change < 0 else 0
    if score >= 2:
        return "强多"
    if score == 1:
        return "弱多"
    if score == 0:
        return "震荡"
    if score == -1:
        return "弱空"
    return "强空"


def compute_metrics(stock: StockConfig, bars: List[PriceBar], profile: ThresholdProfile) -> StockMetrics:
    if len(bars) < 60:
        raise ValueError("At least 60 bars are required to compute V1 metrics.")
    latest = bars[-1]
    prev = bars[-2]
    last20 = bars[-20:]
    last60 = bars[-60:]
    pct = safe_div(latest.close - prev.close, prev.close)
    amplitudes20 = [safe_div(bar.high - bar.low, bar.close) for bar in last20]
    closes = [bar.close for bar in bars]
    stock_rets = returns(bars)
    pct_std = pstdev(stock_rets[-20:]) if len(stock_rets[-20:]) > 1 else 0.0
    current_rsi = rsi(closes)
    rsi_series = [rsi(closes[: idx + 1]) for idx in range(max(15, len(closes) - 60), len(closes))]
    macd_series = macd_bars(closes)
    macd_abs_mean = rolling_mean([abs(value) for value in macd_series[-20:]])
    ma5 = moving_average(bars, 5)
    ma10 = moving_average(bars, 10)
    ma20 = moving_average(bars, 20)
    ma60 = moving_average(bars, 60)
    boll_mid = ma20
    boll_std = pstdev([bar.close for bar in last20])
    boll_upper = boll_mid + 2 * boll_std
    ma_alignment = "缠绕"
    if ma5 > ma10 > ma20 > ma60:
        ma_alignment = "多头发散"
    elif ma5 >= ma10 >= ma20:
        ma_alignment = "多头粘合"
    elif ma5 < ma10 < ma20 < ma60:
        ma_alignment = "空头发散"
    elif ma5 <= ma10 <= ma20:
        ma_alignment = "空头粘合"
    previous_high = max(bar.high for bar in bars[-61:-1])
    avg_northbound_abs = rolling_mean([abs(bar.northbound_net_inflow) for bar in last20])
    avg_large_order = rolling_mean([bar.large_order_ratio for bar in last20])
    avg_margin = rolling_mean([bar.margin_balance for bar in last20])
    metrics = StockMetrics(
        symbol=stock.symbol,
        name=stock.name,
        close=latest.close,
        pct_change=pct,
        amount_ratio=safe_div(latest.amount, profile.avg_amount_20d),
        turnover_ratio=safe_div(latest.turnover_rate, profile.avg_turnover_20d),
        amplitude_ratio=safe_div(safe_div(latest.high - latest.low, latest.close), profile.avg_amplitude_20d),
        main_fund_strength=safe_div(latest.main_net_inflow, profile.avg_amount_20d),
        northbound_deviation=safe_div(latest.northbound_net_inflow, avg_northbound_abs),
        large_order_deviation=latest.large_order_ratio - avg_large_order,
        margin_change_rate=safe_div(latest.margin_balance - prev.margin_balance, avg_margin),
        pct_change_sigma=safe_div(abs(pct), pct_std),
        ma5_deviation=safe_div(latest.close - ma5, ma5),
        ma10_deviation=safe_div(latest.close - ma10, ma10),
        ma20_deviation=safe_div(latest.close - ma20, ma20),
        previous_high_breakout=safe_div(latest.close - previous_high, previous_high),
        rsi=current_rsi,
        rsi_percentile=percentile_rank(rsi_series, current_rsi),
        macd_bar_strength=safe_div(macd_series[-1], macd_abs_mean),
        bollinger_position=safe_div(latest.close - boll_mid, boll_upper - boll_mid),
        ma_alignment=ma_alignment,
        profit_ratio_change_5d=latest.profit_ratio - bars[-6].profit_ratio,
        cost_deviation=safe_div(latest.close - latest.average_cost, latest.average_cost),
        chip_concentration_ratio=safe_div(latest.chip_width_90, rolling_mean([bar.chip_width_90 for bar in last20])),
        sector_excess_return=pct - latest.sector_return,
        market_excess_return=pct - latest.market_return,
    )
    metrics.labels = {
        "量比": classify_amount_ratio(metrics.amount_ratio),
        "趋势评级": classify_trend(metrics),
        "RSI": "超买" if metrics.rsi_percentile > 90 else "超卖" if metrics.rsi_percentile < 10 else "中性",
        "布林": "突破上轨" if metrics.bollinger_position > 1 else "跌破下轨" if metrics.bollinger_position < -1 else "通道内",
    }
    return metrics
