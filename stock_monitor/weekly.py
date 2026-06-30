from __future__ import annotations


class WeeklyReviewNotEnabled(RuntimeError):
    pass


def run_weekly_review_placeholder() -> None:
    raise WeeklyReviewNotEnabled("weekly_review is reserved for a later version and is disabled in V1.")
