from datetime import date
import os
import unittest

from stock_monitor.data_providers import SampleDataProvider
from stock_monitor.enrichment_providers import MultiEnrichmentProvider
from stock_monitor.models import StockConfig


class EnrichmentTest(unittest.TestCase):
    def test_multi_enrichment_with_noop_does_not_change_bars(self):
        stock = StockConfig("603019.SH", "中科曙光", "算力", 156_000_000_000, ["money_flow"])
        bars = SampleDataProvider().get_history(stock, date(2026, 6, 30), 80)
        enriched, notes = MultiEnrichmentProvider(chain="none").enrich_history(stock, bars, date(2026, 6, 30))
        self.assertEqual(enriched[-1].close, bars[-1].close)
        self.assertIn("增强数据源未启用", "；".join(notes))

    def test_default_enrichment_chain_does_not_require_tushare_token(self):
        old_token = os.environ.pop("TUSHARE_TOKEN", None)
        try:
            provider = MultiEnrichmentProvider(chain="tushare")
            stock = StockConfig("603019.SH", "中科曙光", "算力", 156_000_000_000, ["money_flow"])
            bars = SampleDataProvider().get_history(stock, date(2026, 6, 30), 80)
            enriched, notes = provider.enrich_history(stock, bars, date(2026, 6, 30))
            self.assertEqual(enriched[-1].close, bars[-1].close)
            self.assertIn("tushare 增强数据源未启用", "；".join(notes))
        finally:
            if old_token is not None:
                os.environ["TUSHARE_TOKEN"] = old_token
