from __future__ import annotations

import os
from datetime import date
from typing import List

from ..data_providers import MarketDataProvider, NewsDataProvider
from ..enrichment_providers import enrichment_provider_from_env
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
        data_quality = list(
            getattr(
                self.market_provider,
                "quality_notes",
                ["V1 当前使用示例数据源；正式部署需接入真实行情、资金、公告和新闻适配器。"],
            )
        )
        metrics = []
        enrichment_provider = enrichment_provider_from_env()
        for stock in stocks:
            try:
                bars = self.market_provider.get_history(stock, report_date, 260)
                bars, enrichment_notes = enrichment_provider.enrich_history(stock, bars, report_date)
                data_quality.extend(enrichment_notes)
                metrics.append(compute_metrics(stock, bars, thresholds[stock.symbol]))
            except Exception as exc:
                data_quality.append(_market_data_missing_note(stock, exc))
        news = self.news_provider.get_news(stocks, report_date)
        return ResearchResult(report_type, report_date, metrics, thresholds, news, _dedupe_notes(data_quality))


def _market_data_missing_note(stock: StockConfig, exc: Exception) -> str:
    if os.getenv("INCLUDE_PROVIDER_ERRORS", "").lower() in {"1", "true", "yes"}:
        return f"{stock.name}（{stock.symbol}）行情数据暂缺：{exc}"
    return f"{stock.name}（{stock.symbol}）行情数据暂缺：已配置行情源连接失败或返回空数据，本次不生成该股量价判断。"


def _dedupe_notes(notes: List[str]) -> List[str]:
    seen = set()
    result = []
    for note in notes:
        if note in seen:
            continue
        seen.add(note)
        result.append(note)
    return result
