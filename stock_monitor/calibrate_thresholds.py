from __future__ import annotations

import argparse
import os
from datetime import date

from .data_providers import provider_from_name
from .thresholds import calibrate_watchlist, save_profiles
from .workflow import load_stocks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate adaptive stock thresholds.")
    parser.add_argument("--date", default=date.today().isoformat())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    as_of = date.fromisoformat(args.date)
    provider = provider_from_name(os.getenv("DATA_PROVIDER", "sample"))
    profiles = calibrate_watchlist(load_stocks(), provider, as_of)
    save_profiles(profiles)
    for profile in profiles.values():
        print(
            f"{profile.symbol} {profile.name}: {profile.stock_type}, "
            f"threshold={profile.threshold_multiplier:.1f}, funding={profile.funding_multiplier:.1f}, beta={profile.beta_250d:.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
