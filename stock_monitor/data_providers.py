from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Dict, List, Protocol

from .models import NewsItem, PriceBar, StockConfig


class MarketDataProvider(Protocol):
    def get_history(self, stock: StockConfig, end_date: date, lookback_days: int) -> List[PriceBar]:
        ...


class NewsDataProvider(Protocol):
    def get_news(self, stocks: List[StockConfig], report_date: date) -> List[NewsItem]:
        ...


class SampleDataProvider:
    """Deterministic sample data provider for V1 local runs and tests."""

    def get_history(self, stock: StockConfig, end_date: date, lookback_days: int) -> List[PriceBar]:
        bars: List[PriceBar] = []
        base = 80.0 + (sum(ord(ch) for ch in stock.symbol) % 30)
        cap_factor = max(0.8, min(1.4, stock.float_market_cap_cny / 200_000_000_000))
        for idx in range(lookback_days):
            day = end_date - timedelta(days=lookback_days - idx - 1)
            seasonal = math.sin(idx / 7.0) * 0.018 + math.cos(idx / 17.0) * 0.012
            drift = idx * 0.0009
            close = base * (1 + drift + seasonal)
            open_price = close * (1 - 0.004 + math.sin(idx / 5.0) * 0.006)
            amplitude = 0.025 + abs(math.sin(idx / 9.0)) * 0.025 / cap_factor
            high = max(open_price, close) * (1 + amplitude / 2)
            low = min(open_price, close) * (1 - amplitude / 2)
            amount = 1_200_000_000 * cap_factor * (1 + 0.25 * math.sin(idx / 11.0))
            turnover = 0.018 * (1 / cap_factor) + 0.006 * abs(math.sin(idx / 13.0))
            main_flow = amount * (0.015 * math.sin(idx / 8.0))
            northbound = amount * (0.006 * math.cos(idx / 10.0))
            margin = 9_000_000_000 * cap_factor * (1 + 0.04 * math.sin(idx / 19.0))
            market_return = 0.004 * math.sin(idx / 6.0)
            sector_return = market_return + 0.006 * math.sin(idx / 8.0)
            bars.append(
                PriceBar(
                    date=day,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    amount=amount,
                    turnover_rate=turnover,
                    main_net_inflow=main_flow,
                    northbound_net_inflow=northbound,
                    large_order_ratio=0.18 + 0.03 * math.sin(idx / 6.0),
                    margin_balance=margin,
                    profit_ratio=0.48 + 0.2 * math.sin(idx / 18.0),
                    average_cost=close * (0.96 + 0.03 * math.cos(idx / 12.0)),
                    chip_width_90=0.18 + 0.04 * math.cos(idx / 15.0),
                    sector_return=sector_return,
                    market_return=market_return,
                )
            )
        return bars

    def get_news(self, stocks: List[StockConfig], report_date: date) -> List[NewsItem]:
        sectors = sorted({stock.sector for stock in stocks})
        return [
            NewsItem("海外科技股表现分化", "海外", "中性", "中", "隔夜外盘对成长板块影响偏中性，需观察开盘承接。"),
            NewsItem(f"{'、'.join(sectors)}板块政策预期升温", "政策", "利好", "中", "市场关注产业支持政策落地节奏。"),
            NewsItem("样例公告数据源未接入", "公司", "中性", "弱", "V1 示例数据不接入真实公告，正式部署需替换 NewsDataProvider。"),
        ]


class AkShareDataProvider:
    """AkShare-backed A-share daily data provider.

    V1 uses AkShare for real OHLCV, amount, amplitude, and turnover data.
    Funding, chip, margin, sector, and benchmark fields remain neutral unless
    a richer provider is added.
    """

    def __init__(self) -> None:
        try:
            import akshare as ak  # type: ignore
        except ImportError as exc:
            raise RuntimeError("DATA_PROVIDER=akshare requires installing akshare.") from exc
        self.ak = ak
        self.quality_notes = [
            "行情数据来自 AkShare/Eastmoney 接口，包含日线 OHLCV、成交额、涨跌幅、振幅、换手率。",
            "V1 AkShare 适配器暂未接入逐股主力资金、北向、融资、筹码和板块基准；相关字段按中性值处理。",
        ]

    def get_history(self, stock: StockConfig, end_date: date, lookback_days: int) -> List[PriceBar]:
        symbol = _strip_exchange(stock.symbol)
        start_date = (end_date - timedelta(days=max(lookback_days * 3, 380))).strftime("%Y%m%d")
        end = end_date.strftime("%Y%m%d")
        try:
            frame = self.ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end, adjust="")
        except TypeError:
            frame = self.ak.stock_zh_a_hist(symbol=symbol, start_date=start_date, end_date=end, adjust="")
        if frame is None or len(frame) == 0:
            raise RuntimeError(f"AkShare returned no daily bars for {stock.symbol}.")
        rows = frame.tail(lookback_days).to_dict("records")
        bars = [_bar_from_akshare_row(row) for row in rows]
        if len(bars) < min(60, lookback_days):
            raise RuntimeError(f"AkShare returned only {len(bars)} bars for {stock.symbol}; at least 60 are required.")
        return bars

    def get_news(self, stocks: List[StockConfig], report_date: date) -> List[NewsItem]:
        items: List[NewsItem] = []
        for stock in stocks:
            symbol = _strip_exchange(stock.symbol)
            try:
                frame = self.ak.stock_news_em(symbol=symbol)
            except Exception:
                continue
            if frame is None or len(frame) == 0:
                continue
            for row in frame.head(3).to_dict("records"):
                title = str(_value(row, ["新闻标题", "标题", "title"], f"{stock.name} 新闻"))
                summary = str(_value(row, ["新闻内容", "内容", "summary"], "新闻摘要暂缺。"))
                items.append(NewsItem(title=title, category="公司", sentiment="中性", impact="中", summary=summary[:160]))
        if items:
            return items
        return [NewsItem("AkShare 新闻接口暂未返回内容", "公司", "中性", "弱", "今晚报告仅使用真实行情数据，新闻/公告需后续接入更稳定来源。")]


def _strip_exchange(symbol: str) -> str:
    return symbol.split(".")[0]


def _value(row: Dict[str, Any], names: List[str], default: Any = 0.0) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return default


def _float(row: Dict[str, Any], names: List[str], default: float = 0.0) -> float:
    value = _value(row, names, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _date(row: Dict[str, Any]) -> date:
    value = _value(row, ["日期", "date"])
    if hasattr(value, "date"):
        return value.date()
    return date.fromisoformat(str(value)[:10])


def _bar_from_akshare_row(row: Dict[str, Any]) -> PriceBar:
    close = _float(row, ["收盘", "收盘价", "close"])
    open_price = _float(row, ["开盘", "open"], close)
    high = _float(row, ["最高", "high"], close)
    low = _float(row, ["最低", "low"], close)
    pct_change = _float(row, ["涨跌幅"], 0.0) / 100
    return PriceBar(
        date=_date(row),
        open=open_price,
        high=high,
        low=low,
        close=close,
        amount=_float(row, ["成交额", "amount"], 0.0),
        turnover_rate=_float(row, ["换手率"], 0.0) / 100,
        main_net_inflow=0.0,
        northbound_net_inflow=0.0,
        large_order_ratio=0.0,
        margin_balance=1.0,
        profit_ratio=0.5,
        average_cost=close,
        chip_width_90=1.0,
        sector_return=pct_change,
        market_return=pct_change,
    )


def provider_from_name(name: str):
    if name == "sample":
        return SampleDataProvider()
    if name == "akshare":
        return AkShareDataProvider()
    raise ValueError(f"Unsupported provider in V1: {name}")
