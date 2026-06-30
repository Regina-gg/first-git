from __future__ import annotations

import os
from datetime import date
from typing import List, Optional

from .agents.decision import DecisionAgent
from .agents.research import ResearchAgent
from .agents.writer import WriterAgent
from .config import load_config
from .data_providers import provider_from_name
from .delivery import DeliveryResult, LarkCliDelivery
from .models import ReportMessage, ReportType, StockConfig
from .thresholds import calibrate_watchlist, load_profiles


def load_stocks() -> List[StockConfig]:
    raw = load_config("config/watchlist.yaml")
    return [
        StockConfig(
            symbol=item["symbol"],
            name=item["name"],
            sector=item["sector"],
            float_market_cap_cny=float(item["float_market_cap_cny"]),
            watch_metrics=list(item["watch_metrics"]),
        )
        for item in raw["stocks"]
    ]


def build_report(report_type: ReportType, report_date: date, target_chat_id: Optional[str] = None) -> ReportMessage:
    provider = provider_from_name(os.getenv("DATA_PROVIDER", "sample"))
    stocks = load_stocks()
    thresholds = load_profiles()
    if not thresholds:
        thresholds = calibrate_watchlist(stocks, provider, report_date)
    research = ResearchAgent(provider, provider).run(report_type, report_date, stocks, thresholds)
    decision = DecisionAgent().run(research)
    return WriterAgent().render(decision, target_chat_id)


def deliver_report(message: ReportMessage, dry_run: bool) -> DeliveryResult:
    provider = os.getenv("FEISHU_DELIVERY_PROVIDER", "lark_cli")
    if provider != "lark_cli":
        raise ValueError(f"Unsupported delivery provider in V1: {provider}")
    return LarkCliDelivery().send(message, dry_run=dry_run)
