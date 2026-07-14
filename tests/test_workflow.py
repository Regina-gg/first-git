from datetime import date
import unittest

from stock_monitor.agents.decision import DecisionAgent
from stock_monitor.agents.research import ResearchAgent
from stock_monitor.agents.writer import WriterAgent
from stock_monitor.models import NewsItem, ReportType, ResearchResult, StockConfig, StockMetrics, ThresholdProfile
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

    def test_evening_report_has_non_empty_intel_fallbacks_and_short_quality(self):
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
        self.assertNotIn("暂无已接入政策数据", message.markdown)
        self.assertNotIn("暂无已接入行业数据", message.markdown)
        quality = message.markdown.split("## 数据质量", 1)[1]
        self.assertLessEqual(len([line for line in quality.splitlines() if line.strip().startswith("- ")]), 4)

    def test_morning_and_close_suppress_unavailable_funding_numbers(self):
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
        metrics = StockMetrics(
            symbol=stock.symbol,
            name=stock.name,
            close=100,
            pct_change=0.01,
            amount_ratio=1.2,
            turnover_ratio=1.1,
            amplitude_ratio=1.0,
            main_fund_strength=0,
            northbound_deviation=0,
            large_order_deviation=0,
            margin_change_rate=0,
            pct_change_sigma=0.5,
            ma5_deviation=0.01,
            ma10_deviation=0.01,
            ma20_deviation=0.01,
            previous_high_breakout=0,
            rsi=50,
            rsi_percentile=50,
            macd_bar_strength=0,
            bollinger_position=0.5,
            ma_alignment="缠绕",
            profit_ratio_change_5d=0,
            cost_deviation=0,
            chip_concentration_ratio=1,
            sector_excess_return=0,
            market_excess_return=0,
            labels={"量比": "正常", "趋势评级": "震荡", "布林": "通道内", "RSI": "中性"},
        )
        research = ResearchResult(
            ReportType.MORNING_CHECK,
            date(2026, 6, 30),
            [metrics],
            {stock.symbol: profile},
            [],
            ["中科曙光（603019.SH）行情使用 eastmoney 数据源。", "中科曙光 主力资金暂缺：AkShare fund flow 网络连接失败或超时，已跳过该字段"],
        )
        morning = WriterAgent().render(DecisionAgent().run(research), None).markdown
        self.assertIn("日线量比/换手率倍数作为早盘确认代理", morning)
        self.assertIn("主力资金源暂缺", morning)

        research.report_type = ReportType.CLOSE_REPORT
        close_report = WriterAgent().render(DecisionAgent().run(research), None).markdown
        self.assertIn("主力资金源暂缺", close_report)
