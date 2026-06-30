from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional

from .models import ReportMessage


@dataclass
class DeliveryResult:
    ok: bool
    command: List[str]
    stdout: str = ""
    stderr: str = ""


class LarkCliDelivery:
    def __init__(self, profile: Optional[str] = None, send_as: str = "bot") -> None:
        self.profile = profile or os.getenv("LARK_CLI_PROFILE") or None
        self.send_as = send_as or os.getenv("FEISHU_SEND_AS", "bot")

    def send(self, message: ReportMessage, dry_run: bool = False) -> DeliveryResult:
        if not shutil.which("lark-cli"):
            raise RuntimeError("lark-cli is not installed or not on PATH.")
        chat_id = message.target_chat_id or os.getenv("FEISHU_CHAT_ID")
        if not chat_id and dry_run:
            chat_id = "oc_dry_run_placeholder"
        if not chat_id:
            raise RuntimeError("Missing Feishu chat target. Set FEISHU_CHAT_ID or pass target_chat_id.")
        command = ["lark-cli"]
        if self.profile:
            command.extend(["--profile", self.profile])
        command.extend(
            [
                "im",
                "+messages-send",
                "--as",
                self.send_as,
                "--chat-id",
                chat_id,
                "--markdown",
                message.markdown,
            ]
        )
        if dry_run:
            command.append("--dry-run")
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        return DeliveryResult(completed.returncode == 0, command, completed.stdout, completed.stderr)
