# AI Stock Monitor V1

V1 implements the PRD-aligned daily workflow:

- Four scheduled reports: `pre_market`, `morning_check`, `close_report`, `evening_intel`
- Three-agent workflow: Research -> Decision -> Writer
- Core metrics and adaptive threshold calibration
- Feishu delivery through `lark-cli`
- Extension points for intraday alerts, weekly review, DCF, portfolio management, backtests, and Q&A

## Quick Start

```bash
python3 -m stock_monitor.calibrate_thresholds --date 2026-06-30
python3 -m stock_monitor.run_report --type close_report --date 2026-06-30 --dry-run
```

V1 uses `SampleDataProvider` by default so the end-to-end workflow runs without an external market data source.

## Feishu Delivery

Delivery uses `lark-cli` instead of direct OpenAPI token management:

```bash
export FEISHU_DELIVERY_PROVIDER=lark_cli
export FEISHU_SEND_AS=bot
export FEISHU_TARGET_TYPE=chat
export FEISHU_CHAT_ID=oc_xxx
python3 -m stock_monitor.run_report --type pre_market
```

Use `--dry-run` first to preview both the report and the `lark-cli` request.

Local dry-run example:

```bash
FEISHU_CHAT_ID=oc_xxx python3 -m stock_monitor.run_report --type close_report --dry-run
```

## GitHub Actions Deployment

The workflow in `.github/workflows/daily_reports.yml` installs `lark-cli`, initializes a `stock-monitor` bot profile from GitHub Secrets, calibrates thresholds, and sends the selected report.

Add these repository secrets in `Settings -> Secrets and variables -> Actions`:

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_CHAT_ID`

The app secret is passed to `lark-cli config init --app-secret-stdin` through stdin at runtime and is not stored in the repository.

Manual acceptance test:

1. Open the `AI Stock Monitor Daily Reports` workflow in GitHub Actions.
2. Run `workflow_dispatch` with `report_type=close_report`.
3. Confirm the job passes `Install lark-cli`, `Configure lark-cli bot profile`, `Calibrate thresholds`, and `Run report`.
4. Confirm the Feishu group receives the report.

Common failures:

- `Bot/User can NOT be out of the chat`: add the application bot to the target group.
- Permission error: enable the IM message sending permission in the Feishu developer console.
- Secret validation failure: check that the three GitHub Secrets exist and are named exactly as above.

## Configuration

- `config/watchlist.yaml`: stocks, sectors, watch metrics, delivery target
- `config/report_types.yaml`: report templates, modules, schedules, required fields
- `config/thresholds.yaml`: calibration windows and adaptive threshold rules

These `.yaml` files are intentionally JSON-compatible so V1 can run with the Python standard library only.

## Templates

Report templates live under `templates/*.md.j2`. Each report has independent fields and layout so future edits to wording, order, or formatting do not require changing the agent workflow.
