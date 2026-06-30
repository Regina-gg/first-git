from __future__ import annotations

from datetime import date
from typing import List

from ..data_providers import MarketDataProvider, NewsDataProvider
from ..metrics import compute_metrics
from ..models import ReportType, ResearchResult, StockConfig, ThresholdProfile
from ..thresholds import calibrate_watchlist


class ResearchAgent:
    """Owns data retrieval, indicator calculation, and research analysis inputs."""

    def __init__(self, market_provider: MarketDataProvider, news_provider: NewsDataProvider) -> None:
        self.market_provider = market_provider
        self.news_provider = news_provider

    def run(
        self,
        report_type: ReportType,
        report_date: date,
        stocks: List[StockConfig],
        thresholds: dict[str, ThresholdProfile],
    ) -> ResearchResult:
        if not thresholds or any(stock.symbol not in thresholds for stock in stocks):
            thresholds = calibrate_watchlist(stocks, self.market_provider, report_date)
        data_quality = ["V1 当前使用示例数据源；正式部署需接入真实行情、资金、公告和新闻适配器。"]
        metrics = []
        for stock in stocks:
            bars = self.market_provider.get_history(stock, report_date, 260)
            metrics.append(compute_metrics(stock, bars, thresholds[stock.symbol]))
        news = self.news_provider.get_news(stocks, report_date)
        return ResearchResult(report_type, report_date, metrics, thresholds, news, data_quality)
