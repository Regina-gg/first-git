from __future__ import annotations

import argparse
import os
import sys
from datetime import date

from .models import ReportType
from .time_utils import today_shanghai
from .workflow import build_report, deliver_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an AI Stock Monitor daily report.")
    parser.add_argument("--type", required=True, choices=[item.value for item in ReportType if item != ReportType.WEEKLY_REVIEW])
    parser.add_argument("--date", default=today_shanghai().isoformat())
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_date = date.fromisoformat(args.date)
    chat_id = os.getenv("FEISHU_CHAT_ID")
    message = build_report(ReportType(args.type), report_date, chat_id)
    if args.dry_run:
        print(message.markdown)
        print("\n--- delivery dry-run ---")
    result = deliver_report(message, dry_run=args.dry_run)
    if not result.ok:
        print(result.stderr or result.stdout, file=sys.stderr)
        return 1
    if args.dry_run:
        print(result.stdout or "lark-cli dry-run completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
