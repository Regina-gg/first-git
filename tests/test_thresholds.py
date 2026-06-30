from datetime import date
import unittest

from stock_monitor.data_providers import SampleDataProvider
from stock_monitor.thresholds import calibrate_watchlist
from stock_monitor.workflow import load_stocks


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
