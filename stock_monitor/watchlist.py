from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import PROJECT_ROOT


DEFAULT_WATCH_METRICS = ["volume", "money_flow", "technical", "chip"]
WATCHLIST_PATH = PROJECT_ROOT / "config" / "watchlist.yaml"


class WatchlistError(ValueError):
    pass


def load_watchlist(path: Path = WATCHLIST_PATH) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_watchlist(config: Dict[str, Any], path: Path = WATCHLIST_PATH) -> None:
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_watchlist(config: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    stocks = config.get("stocks")
    if not isinstance(stocks, list) or not stocks:
        return ["watchlist must contain at least one stock"]
    seen = set()
    for index, stock in enumerate(stocks, start=1):
        prefix = f"stock #{index}"
        symbol = stock.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            errors.append(f"{prefix}: symbol is required")
        elif symbol in seen:
            errors.append(f"{prefix}: duplicate symbol {symbol}")
        else:
            seen.add(symbol)
        for field in ["name", "sector"]:
            if not isinstance(stock.get(field), str) or not stock[field].strip():
                errors.append(f"{prefix}: {field} is required")
        cap = stock.get("float_market_cap_cny")
        if not isinstance(cap, (int, float)) or cap <= 0:
            errors.append(f"{prefix}: float_market_cap_cny must be positive")
        metrics = stock.get("watch_metrics")
        if not isinstance(metrics, list) or not metrics or not all(isinstance(item, str) and item for item in metrics):
            errors.append(f"{prefix}: watch_metrics must be a non-empty list of strings")
    return errors


def add_stock(
    config: Dict[str, Any],
    symbol: str,
    name: str,
    sector: str,
    float_market_cap_cny: float,
    watch_metrics: Optional[List[str]] = None,
) -> Dict[str, Any]:
    symbol = symbol.strip().upper()
    stocks = config.setdefault("stocks", [])
    if any(stock["symbol"].upper() == symbol for stock in stocks):
        raise WatchlistError(f"{symbol} already exists in watchlist")
    stocks.append(
        {
            "symbol": symbol,
            "name": name.strip(),
            "sector": sector.strip(),
            "float_market_cap_cny": float_market_cap_cny,
            "watch_metrics": watch_metrics or list(DEFAULT_WATCH_METRICS),
        }
    )
    errors = validate_watchlist(config)
    if errors:
        raise WatchlistError("; ".join(errors))
    return config


def remove_stock(config: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    symbol = symbol.strip().upper()
    stocks = config.get("stocks", [])
    remaining = [stock for stock in stocks if stock["symbol"].upper() != symbol]
    if len(remaining) == len(stocks):
        raise WatchlistError(f"{symbol} is not in watchlist")
    config["stocks"] = remaining
    errors = validate_watchlist(config)
    if errors:
        raise WatchlistError("; ".join(errors))
    return config


def parse_metrics(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the AI Stock Monitor watchlist.")
    parser.add_argument("--config", default=str(WATCHLIST_PATH), help="Path to watchlist config.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List watched stocks.")
    subparsers.add_parser("validate", help="Validate watchlist config.")

    add_parser = subparsers.add_parser("add", help="Add a stock.")
    add_parser.add_argument("--symbol", required=True)
    add_parser.add_argument("--name", required=True)
    add_parser.add_argument("--sector", required=True)
    add_parser.add_argument("--float-market-cap-cny", required=True, type=float)
    add_parser.add_argument("--watch-metrics", help="Comma-separated metric list.")

    remove_parser = subparsers.add_parser("remove", help="Remove a stock.")
    remove_parser.add_argument("--symbol", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    path = Path(args.config)
    config = load_watchlist(path)
    if args.command == "list":
        for stock in config.get("stocks", []):
            metrics = ",".join(stock["watch_metrics"])
            print(f"{stock['symbol']}\t{stock['name']}\t{stock['sector']}\t{stock['float_market_cap_cny']:.0f}\t{metrics}")
        return 0
    if args.command == "validate":
        errors = validate_watchlist(config)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print("watchlist ok")
        return 0
    if args.command == "add":
        add_stock(
            config,
            args.symbol,
            args.name,
            args.sector,
            args.float_market_cap_cny,
            parse_metrics(args.watch_metrics),
        )
        save_watchlist(config, path)
        print(f"added {args.symbol.upper()}")
        return 0
    if args.command == "remove":
        remove_stock(config, args.symbol)
        save_watchlist(config, path)
        print(f"removed {args.symbol.upper()}")
        return 0
    raise WatchlistError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
