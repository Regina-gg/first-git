#!/usr/bin/env bash
set -euo pipefail

# Example only. Review paths and environment variables before installing.
PROJECT_DIR="/Users/jinrui/Desktop/git"
PYTHON_BIN="/usr/bin/python3"

cat <<CRON
30 8 * * 1-5 cd "$PROJECT_DIR" && DATA_PROVIDER=sample "$PYTHON_BIN" -m stock_monitor.run_report --type pre_market
0 10 * * 1-5 cd "$PROJECT_DIR" && DATA_PROVIDER=sample "$PYTHON_BIN" -m stock_monitor.run_report --type morning_check
10 15 * * 1-5 cd "$PROJECT_DIR" && DATA_PROVIDER=sample "$PYTHON_BIN" -m stock_monitor.run_report --type close_report
0 21 * * 1-5 cd "$PROJECT_DIR" && DATA_PROVIDER=sample "$PYTHON_BIN" -m stock_monitor.run_report --type evening_intel
CRON
