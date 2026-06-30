from datetime import date
import unittest

from stock_monitor.data_providers import SampleDataProvider
from stock_monitor.data_providers import _bar_from_akshare_row
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
