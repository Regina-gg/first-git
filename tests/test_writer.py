from datetime import date
import unittest

from stock_monitor.agents.writer import TemplateValidationError, WriterAgent
from stock_monitor.models import DecisionResult, ReportType


def decision_with_sections(report_type):
    sections = {
        "market_transmission": "x",
        "news_summary": "x",
        "funding_preview": "x",
        "key_levels": "x",
        "daily_outlook": "x",
        "morning_volume": "x",
        "fund_flow_check": "x",
        "sector_check": "x",
        "technical_check": "x",
        "strategy_update": "x",
        "price_volume_review": "x",
        "technical_review": "x",
        "funding_review": "x",
        "chip_review": "x",
        "sector_comparison": "x",
        "trend_rating": "x",
        "tomorrow_levels": "x",
        "policy_intel": "x",
        "industry_intel": "x",
        "company_intel": "x",
        "sentiment_intel": "x",
        "next_day_preview": "x",
    }
    return DecisionResult(report_type, date(2026, 6, 30), "summary", 70, "震荡", [], [], [], sections)


class WriterTest(unittest.TestCase):
    def test_all_daily_templates_render(self):
        writer = WriterAgent()
        for report_type in [ReportType.PRE_MARKET, ReportType.MORNING_CHECK, ReportType.CLOSE_REPORT, ReportType.EVENING_INTEL]:
            message = writer.render(decision_with_sections(report_type), None)
            self.assertNotIn("{{", message.markdown)
            self.assertIn("数据质量", message.markdown)

    def test_template_missing_field_fails_clearly(self):
        writer = WriterAgent()
        decision = decision_with_sections(ReportType.PRE_MARKET)
        del decision.sections["daily_outlook"]
        with self.assertRaises(TemplateValidationError):
            writer.render(decision, None)
