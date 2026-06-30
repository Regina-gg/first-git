from datetime import date
import unittest

from stock_monitor.agents.decision import DecisionAgent
from stock_monitor.agents.research import ResearchAgent
from stock_monitor.agents.writer import WriterAgent
from stock_monitor.models import NewsItem, ReportType, StockConfig, ThresholdProfile
from stock_monitor.workflow import build_report


class FailingProvider:
    def get_history(self, stock, end_date, lookback_days):
        raise RuntimeError("upstream disconnected")

    def get_news(self, stocks, report_date):
        return [NewsItem("新闻接口正常", "公司", "中性", "弱", "仅用于测试。")]


class WorkflowTest(unittest.TestCase):
    def test_build_all_daily_reports_with_sample_data(self):
        for report_type in [ReportType.PRE_MARKET, ReportType.MORNING_CHECK, ReportType.CLOSE_REPORT, ReportType.EVENING_INTEL]:
            message = build_report(report_type, date(2026, 6, 30), None)
            self.assertTrue(message.markdown.startswith("# "))
            self.assertIn("数据质量", message.markdown)

    def test_report_still_renders_when_market_data_fails(self):
        stock = StockConfig("603019.SH", "中科曙光", "算力", 100_000_000_000, ["amount"])
        profile = ThresholdProfile(
            symbol=stock.symbol,
            name=stock.name,
            as_of=date(2026, 6, 30),
            short_mean_days=20,
            percentile_days=60,
            volatility_days=20,
            beta_days=250,
            avg_amount_20d=1,
            avg_turnover_20d=1,
            avg_amplitude_20d=1,
            pct_change_std_20d=1,
            beta_250d=1,
            stock_type="中波动",
            threshold_multiplier=1,
            funding_multiplier=1,
        )
        research = ResearchAgent(FailingProvider(), FailingProvider()).run(
            ReportType.EVENING_INTEL,
            date(2026, 6, 30),
            [stock],
            {stock.symbol: profile},
        )
        message = WriterAgent().render(DecisionAgent().run(research), None)
        self.assertIn("行情数据暂缺", message.markdown)
        self.assertIn("upstream disconnected", message.markdown)
