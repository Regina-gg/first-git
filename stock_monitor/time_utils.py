from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


APP_TIMEZONE = ZoneInfo("Asia/Shanghai")


def today_shanghai() -> date:
    return datetime.now(APP_TIMEZONE).date()


def format_generated_at() -> str:
    return datetime.now(APP_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S 北京时间")
