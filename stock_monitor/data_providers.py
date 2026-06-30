from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Dict, List, Protocol

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


def provider_from_name(name: str) -> SampleDataProvider:
    if name != "sample":
        raise ValueError(f"Unsupported provider in V1: {name}")
    return SampleDataProvider()
