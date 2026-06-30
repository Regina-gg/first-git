from datetime import date
import unittest

from stock_monitor.models import ReportType
from stock_monitor.workflow import build_report


class WorkflowTest(unittest.TestCase):
    def test_build_all_daily_reports_with_sample_data(self):
        for report_type in [ReportType.PRE_MARKET, ReportType.MORNING_CHECK, ReportType.CLOSE_REPORT, ReportType.EVENING_INTEL]:
            message = build_report(report_type, date(2026, 6, 30), None)
            self.assertTrue(message.markdown.startswith("# "))
            self.assertIn("数据质量", message.markdown)
