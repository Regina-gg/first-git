from datetime import date
import unittest

from stock_monitor.data_providers import SampleDataProvider
from stock_monitor.data_providers import _sanitize_provider_error
from stock_monitor.models import StockConfig
from stock_monitor.thresholds import calibrate_watchlist
from stock_monitor.workflow import load_stocks


class FailingProvider:
    def get_history(self, stock, as_of, lookback):
        raise RuntimeError("Tushare 抱歉，您没有访问该接口的权限，积分不足")


class ThresholdsTest(unittest.TestCase):
    def test_calibrate_watchlist_builds_threshold_profiles(self):
        profiles = calibrate_watchlist(load_stocks(), SampleDataProvider(), date(2026, 6, 30))
        self.assertTrue(profiles)
        for profile in profiles.values():
            self.assertGreater(profile.avg_amount_20d, 0)
            self.assertGreater(profile.avg_turnover_20d, 0)
            self.assertGreater(profile.avg_amplitude_20d, 0)
            self.assertGreaterEqual(profile.pct_change_std_20d, 0)
            self.assertIn(profile.stock_type, {"high_volatility_growth", "balanced", "low_volatility_value"})
            self.assertIn(profile.threshold_multiplier, {0.7, 1.0, 1.3})

    def test_calibration_falls_back_when_provider_fails(self):
        stock = StockConfig("603019.SH", "中科曙光", "算力", 156_000_000_000, ["volume"])
        profiles = calibrate_watchlist([stock], FailingProvider(), date(2026, 6, 30))
        self.assertIn(stock.symbol, profiles)
        self.assertIn("样例基准兜底", "；".join(profiles[stock.symbol].notes))

    def test_tushare_quota_error_is_sanitized(self):
        message = _sanitize_provider_error("Tushare daily", RuntimeError("抱歉，您没有访问该接口的权限，积分不足"))
        self.assertIn("权限/积分/频率限制", message)
