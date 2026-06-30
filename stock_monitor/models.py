from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional


class ReportType(str, Enum):
    PRE_MARKET = "pre_market"
    MORNING_CHECK = "morning_check"
    CLOSE_REPORT = "close_report"
    EVENING_INTEL = "evening_intel"
    WEEKLY_REVIEW = "weekly_review"


@dataclass(frozen=True)
class StockConfig:
    symbol: str
    name: str
    sector: str
    float_market_cap_cny: float
    watch_metrics: List[str]


@dataclass(frozen=True)
class PriceBar:
    date: date
    open: float
    high: float
    low: float
    close: float
    amount: float
    turnover_rate: float
    main_net_inflow: float
    northbound_net_inflow: float
    large_order_ratio: float
    margin_balance: float
    profit_ratio: float
    average_cost: float
    chip_width_90: float
    sector_return: float
    market_return: float


@dataclass(frozen=True)
class NewsItem:
    title: str
    category: str
    sentiment: str
    impact: str
    summary: str


@dataclass
class StockMetrics:
    symbol: str
    name: str
    close: float
    pct_change: float
    amount_ratio: float
    turnover_ratio: float
    amplitude_ratio: float
    main_fund_strength: float
    northbound_deviation: float
    large_order_deviation: float
    margin_change_rate: float
    pct_change_sigma: float
    ma5_deviation: float
    ma10_deviation: float
    ma20_deviation: float
    previous_high_breakout: float
    rsi: float
    rsi_percentile: float
    macd_bar_strength: float
    bollinger_position: float
    ma_alignment: str
    profit_ratio_change_5d: float
    cost_deviation: float
    chip_concentration_ratio: float
    sector_excess_return: float
    market_excess_return: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class ThresholdProfile:
    symbol: str
    name: str
    as_of: date
    short_mean_days: int
    percentile_days: int
    volatility_days: int
    beta_days: int
    avg_amount_20d: float
    avg_turnover_20d: float
    avg_amplitude_20d: float
    pct_change_std_20d: float
    beta_250d: float
    stock_type: str
    threshold_multiplier: float
    funding_multiplier: float
    notes: List[str] = field(default_factory=list)


@dataclass
class ResearchResult:
    report_type: ReportType
    report_date: date
    stocks: List[StockMetrics]
    thresholds: Dict[str, ThresholdProfile]
    news: List[NewsItem]
    data_quality: List[str]


@dataclass
class DecisionResult:
    report_type: ReportType
    report_date: date
    summary: str
    confidence: int
    stance: str
    risks: List[str]
    catalysts: List[str]
    actions: List[str]
    sections: Dict[str, str]


@dataclass
class ReportMessage:
    report_type: ReportType
    title: str
    markdown: str
    target_chat_id: Optional[str]
    idempotency_key: str


class AlertLevel(str, Enum):
    WATCH = "watch"
    WARNING = "warning"
    ACTION = "action"


@dataclass(frozen=True)
class AlertRule:
    rule_id: str
    name: str
    level: AlertLevel
    direction: str
    required_dimensions: List[str]
    cooldown_minutes: int


@dataclass(frozen=True)
class AlertEvent:
    symbol: str
    rule_id: str
    observed_at: str
    evidence: Dict[str, float]


@dataclass(frozen=True)
class AlertDecision:
    event: AlertEvent
    level: AlertLevel
    confidence: int
    should_push: bool
    reason: str


@dataclass
class AlertCooldownState:
    last_pushed_at_by_rule: Dict[str, str] = field(default_factory=dict)
    daily_count_by_level: Dict[str, int] = field(default_factory=dict)
