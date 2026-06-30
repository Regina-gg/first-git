from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, Optional

from ..config import ensure_project_path, load_config
from ..models import DecisionResult, ReportMessage


TOKEN_RE = re.compile(r"{{\s*([a-zA-Z0-9_.]+)\s*}}")
IDEMPOTENCY_RE = re.compile(r"[^a-zA-Z0-9_-]+")


class TemplateValidationError(ValueError):
    pass


class WriterAgent:
    """Renders the Decision Agent output into a deliverable report."""

    def __init__(self) -> None:
        self.report_config = load_config("config/report_types.yaml")["reports"]

    def render(self, decision: DecisionResult, target_chat_id: Optional[str] = None) -> ReportMessage:
        report_key = decision.report_type.value
        config = self.report_config[report_key]
        title = self._title(decision)
        context: Dict[str, str] = {
            "title": title,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_quality": "\n".join([f"- {item}" for item in ["缺失字段会在 Research 阶段标注，Writer 不编造未接入数据。"]]),
        }
        context.update(decision.sections)
        self._validate_required(config.get("required_fields", []), context)
        template = ensure_project_path(config["template"]).read_text(encoding="utf-8")
        markdown = TOKEN_RE.sub(lambda match: str(context.get(match.group(1), f"{{{{ {match.group(1)} }}}}")), template)
        idempotency_key = self._idempotency_key(report_key, decision.report_date.isoformat(), target_chat_id or "dry-run")
        return ReportMessage(decision.report_type, title, markdown, target_chat_id, idempotency_key)

    def _title(self, decision: DecisionResult) -> str:
        names = {
            "pre_market": "盘前简报",
            "morning_check": "早盘确认",
            "close_report": "收盘日报",
            "evening_intel": "晚间情报站",
            "weekly_review": "周度复盘",
        }
        return f"{names[decision.report_type.value]} | {decision.report_date.isoformat()} | {decision.stance} {decision.confidence}分"

    def _validate_required(self, required_fields: list[str], context: Dict[str, str]) -> None:
        missing = [field for field in required_fields if field not in context or context[field] in (None, "")]
        if missing:
            raise TemplateValidationError(f"Template context is missing required fields: {', '.join(missing)}")

    def _idempotency_key(self, report_key: str, report_date: str, target: str) -> str:
        raw = f"stock-monitor-{report_key}-{report_date}-{target}"
        return IDEMPOTENCY_RE.sub("-", raw)[:64]
