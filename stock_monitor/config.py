from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_config(path: str) -> Dict[str, Any]:
    config_path = PROJECT_ROOT / path
    with config_path.open("r", encoding="utf-8") as handle:
        text = handle.read()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ValueError(f"{path} is not valid JSON and PyYAML is not installed for YAML parsing.") from exc
        loaded = yaml.safe_load(text)
        return loaded or {}


def ensure_project_path(path: str) -> Path:
    resolved = (PROJECT_ROOT / path).resolve()
    if PROJECT_ROOT not in resolved.parents and resolved != PROJECT_ROOT:
        raise ValueError(f"Path escapes project root: {path}")
    return resolved
