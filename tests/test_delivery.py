from datetime import date
import unittest
from unittest.mock import Mock, patch

from stock_monitor.delivery import LarkCliDelivery
from stock_monitor.models import ReportMessage, ReportType


class DeliveryTest(unittest.TestCase):
    def test_lark_cli_delivery_builds_dry_run_command(self):
        message = ReportMessage(ReportType.CLOSE_REPORT, "t", "# report", None, "key")
        completed = Mock(returncode=0, stdout="ok", stderr="")
        with patch("stock_monitor.delivery.shutil.which", return_value="/opt/homebrew/bin/lark-cli"), patch(
            "stock_monitor.delivery.subprocess.run", return_value=completed
        ) as run:
            result = LarkCliDelivery().send(message, dry_run=True)
        self.assertTrue(result.ok)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["lark-cli", "im", "+messages-send"])
        self.assertIn("--as", command)
        self.assertIn("bot", command)
        self.assertIn("--markdown", command)
        self.assertIn("--dry-run", command)
        self.assertIn("oc_dry_run_placeholder", command)
