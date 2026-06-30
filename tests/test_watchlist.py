import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from stock_monitor.watchlist import add_stock, remove_stock, validate_watchlist


BASE_CONFIG = {
    "timezone": "Asia/Shanghai",
    "stocks": [
        {
            "symbol": "603019.SH",
            "name": "中科曙光",
            "sector": "算力",
            "float_market_cap_cny": 156000000000,
            "watch_metrics": ["volume", "money_flow", "technical", "chip"],
        }
    ],
    "delivery": {"provider": "lark_cli", "target_type": "chat", "chat_id_env": "FEISHU_CHAT_ID"},
}


class WatchlistTest(unittest.TestCase):
    def test_add_and_remove_stock(self):
        config = copy.deepcopy(BASE_CONFIG)
        add_stock(config, "300750.SZ", "宁德时代", "新能源", 860000000000, ["volume", "technical"])
        self.assertEqual(len(config["stocks"]), 2)
        remove_stock(config, "300750.SZ")
        self.assertEqual(len(config["stocks"]), 1)

    def test_validate_duplicate_symbol(self):
        config = copy.deepcopy(BASE_CONFIG)
        config["stocks"].append(copy.deepcopy(config["stocks"][0]))
        self.assertTrue(any("duplicate symbol" in error for error in validate_watchlist(config)))

    def test_cli_add_validate_remove(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "watchlist.json"
            path.write_text(json.dumps(copy.deepcopy(BASE_CONFIG), ensure_ascii=False), encoding="utf-8")
            add_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "stock_monitor.watchlist",
                    "--config",
                    str(path),
                    "add",
                    "--symbol",
                    "000001.SZ",
                    "--name",
                    "平安银行",
                    "--sector",
                    "银行",
                    "--float-market-cap-cny",
                    "200000000000",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(add_result.returncode, 0, add_result.stderr)
            validate_result = subprocess.run(
                [sys.executable, "-m", "stock_monitor.watchlist", "--config", str(path), "validate"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(validate_result.returncode, 0, validate_result.stderr)
