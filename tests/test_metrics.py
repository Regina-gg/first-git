from datetime import date
import unittest

from stock_monitor.data_providers import SampleDataProvider
from stock_monitor.data_providers import _bar_from_akshare_row
from stock_monitor.data_providers import _bar_from_eastmoney_kline
from stock_monitor.data_providers import _bar_from_hithink_row
from stock_monitor.data_providers import _bar_from_tushare_row
from stock_monitor.data_providers import _eastmoney_fqt
from stock_monitor.data_providers import _hithink_adjust
from stock_monitor.data_providers import _price_adjust
from stock_monitor.metrics import compute_metrics, percentile_rank
from stock_monitor.models import StockConfig
from stock_monitor.thresholds import calibrate_stock
from stock_monitor.config import load_config


def sample_stock():
    return StockConfig("603019.SH", "中科曙光", "算力", 156_000_000_000, ["volume"])


class MetricsTest(unittest.TestCase):
    def test_percentile_rank(self):
        self.assertEqual(percentile_rank([1, 2, 3, 4], 3), 75)

    def test_compute_metrics_contains_prd_core_indicators(self):
        provider = SampleDataProvider()
        stock = sample_stock()
        bars = provider.get_history(stock, date(2026, 6, 30), 260)
        profile = calibrate_stock(stock, bars, date(2026, 6, 30), load_config("config/thresholds.yaml"))
        metrics = compute_metrics(stock, bars, profile)
        self.assertGreater(metrics.amount_ratio, 0)
        self.assertGreater(metrics.turnover_ratio, 0)
        self.assertGreater(metrics.amplitude_ratio, 0)
        self.assertGreaterEqual(metrics.pct_change_sigma, 0)
        self.assertTrue(0 <= metrics.rsi_percentile <= 100)
        self.assertIn("趋势评级", metrics.labels)

    def test_akshare_row_mapping(self):
        bar = _bar_from_akshare_row(
            {
                "日期": "2026-06-30",
                "开盘": 10,
                "最高": 11,
                "最低": 9,
                "收盘": 10.5,
                "成交额": 123456,
                "换手率": 2.5,
                "涨跌幅": 1.2,
            }
        )
        self.assertEqual(bar.close, 10.5)
        self.assertEqual(bar.amount, 123456)
        self.assertAlmostEqual(bar.turnover_rate, 0.025)
        self.assertAlmostEqual(bar.market_return, 0.012)

    def test_tushare_row_mapping(self):
        bar = _bar_from_tushare_row(
            {
                "trade_date": "20260630",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "amount": 123.456,
                "turnover_rate": 2.5,
                "pct_chg": 1.2,
            }
        )
        self.assertEqual(bar.date.isoformat(), "2026-06-30")
        self.assertEqual(bar.close, 10.5)
        self.assertEqual(bar.amount, 123456)
        self.assertAlmostEqual(bar.turnover_rate, 0.025)
        self.assertAlmostEqual(bar.market_return, 0.012)

    def test_eastmoney_kline_mapping(self):
        bar = _bar_from_eastmoney_kline("2026-06-30,10,10.5,11,9,1000,123456,20,1.2,0.12,2.5")
        self.assertEqual(bar.date.isoformat(), "2026-06-30")
        self.assertEqual(bar.close, 10.5)
        self.assertEqual(bar.amount, 123456)
        self.assertAlmostEqual(bar.turnover_rate, 0.025)
        self.assertAlmostEqual(bar.market_return, 0.012)

    def test_hithink_row_mapping(self):
        stock = StockConfig("603019.SH", "中科曙光", "算力", 1_000_000, ["volume"])
        bar = _bar_from_hithink_row(
            {
                "date_ms": 1782748800000,
                "open_price": 10,
                "high_price": 11,
                "low_price": 9,
                "close_price": 10.5,
                "volume": 1000,
                "turnover": 123456,
                "prev_price": 10,
            },
            stock,
        )
        self.assertEqual(bar.date.isoformat(), "2026-06-30")
        self.assertEqual(bar.close, 10.5)
        self.assertEqual(bar.amount, 123456)
        self.assertAlmostEqual(bar.turnover_rate, 0.123456)
        self.assertAlmostEqual(bar.market_return, 0.05)

    def test_default_price_adjustment_is_forward_adjusted(self):
        self.assertEqual(_price_adjust(), "qfq")
        self.assertEqual(_eastmoney_fqt(), "1")
        self.assertEqual(_hithink_adjust(), "forward")

    def test_default_market_chain_avoids_tushare_adjust_rate_limit_first(self):
        with open(".github/workflows/daily_reports.yml", encoding="utf-8") as file:
            workflow = file.read()
        self.assertIn("MARKET_DATA_CHAIN: hithink,eastmoney,akshare", workflow)
        self.assertIn("HITHINK_FINANCE_API_KEY:", workflow)
        self.assertNotIn("MARKET_DATA_CHAIN: tushare", workflow)
