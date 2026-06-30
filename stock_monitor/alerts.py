from __future__ import annotations

from typing import Iterable, List

from .models import AlertDecision, AlertEvent, AlertLevel, AlertRule, ThresholdProfile


class AlertRuleEngine:
    """V1 placeholder for the PRD intraday alert system.

    The engine exposes the future contract but does not run a real-time market loop in V1.
    """

    def __init__(self, rules: Iterable[AlertRule]) -> None:
        self.rules = list(rules)

    def evaluate(self, events: Iterable[AlertEvent], thresholds: dict[str, ThresholdProfile]) -> List[AlertDecision]:
        decisions: List[AlertDecision] = []
        for event in events:
            rule = next((item for item in self.rules if item.rule_id == event.rule_id), None)
            if not rule:
                continue
            confidence = 50 + min(40, len(rule.required_dimensions) * 10)
            decisions.append(AlertDecision(event, rule.level, confidence, False, "V1 仅预留盘中预警接口，不触发推送。"))
        return decisions


DEFAULT_ALERT_RULES = [
    AlertRule("volume_breakdown", "放量破位", AlertLevel.WARNING, "down", ["price", "volume"], 120),
    AlertRule("main_fund_outflow", "主力大幅流出", AlertLevel.WARNING, "down", ["funding", "order"], 120),
    AlertRule("breakout_with_funds", "放量突破", AlertLevel.WARNING, "up", ["price", "volume", "funding"], 120),
]
