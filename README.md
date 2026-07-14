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

V1 can run with sample data locally, but production pushes should use `DATA_PROVIDER=multi`.

## Market Data Sources

`DATA_PROVIDER=multi` tries configured sources in order and records the winning source or failure reason in the report's data-quality section:

```bash
export DATA_PROVIDER=multi
export MARKET_DATA_CHAIN=hithink,eastmoney,akshare
export PRICE_ADJUST=qfq
export HITHINK_FINANCE_API_KEY=your_hithink_key_optional
export ENRICHMENT_PROVIDER=multi
export ENRICHMENT_CHAIN=tushare,akshare
export TUSHARE_ENRICHMENT_ENDPOINTS=moneyflow,margin,chip,sector
export TUSHARE_ENRICHMENT_TIMEOUT_SECONDS=8
export TUSHARE_TOKEN=your_tushare_token_optional
python3 -m stock_monitor.run_report --type close_report --dry-run
```

Supported V1 sources:

- `hithink`: requires `HITHINK_FINANCE_API_KEY`; uses HiThink-Tech Financial-API historical A-share prices for OHLCV, volume, and amount. Turnover rate is proxied by amount / float market cap when this source wins.
- `tushare`: requires `TUSHARE_TOKEN`; uses Tushare Pro daily/daily_basic for OHLCV, amount, pct change, and turnover.
- `eastmoney`: no token; calls Eastmoney historical K-line directly.
- `akshare`: no token; uses AkShare's Eastmoney wrapper and stock news helper.
- `sample`: deterministic local sample data for tests and offline demos.

`PRICE_ADJUST` controls the price series used by technical indicators. Default is `qfq` (前复权), matching the A-share research-report convention for moving averages, MACD, RSI, and support/resistance. Supported values are `qfq`, `hfq`, and `none`.

For GitHub Actions, add `HITHINK_FINANCE_API_KEY` and `TUSHARE_TOKEN` as optional repository secrets. Base OHLCV now tries HiThink Financial-API first, then Eastmoney and AkShare. Tushare remains enabled for enrichment fields such as money flow, margin, chip, and benchmarks because forward-adjusted `pro_bar` can hit `adj_factor` rate limits on lower-quota accounts.

## Enrichment Data

After base OHLCV data is loaded, the Research Agent runs an enrichment layer that fills the PRD's richer fields when the source is available:

- 主力资金：Tushare `moneyflow`, with AkShare individual fund flow fallback.
- 融资融券：Tushare `margin_detail`, with best-effort AkShare latest margin fallback.
- 筹码：Tushare `cyq_perf` when the account has access.
- 板块基准：Tushare `index_daily` based on `config/sector_benchmarks.yaml`.
- 北向资金：field is reserved; only fill it after a stable per-stock northbound holdings adapter is added.

Each enrichment failure is recorded in the report data-quality section and does not block delivery.
`TUSHARE_ENRICHMENT_ENDPOINTS` can be narrowed, for example `moneyflow,margin`, when the account does not have access to chip or index endpoints. `TUSHARE_ENRICHMENT_TIMEOUT_SECONDS` keeps optional enrichment from delaying the scheduled Feishu push.

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
- `HITHINK_FINANCE_API_KEY` (optional, recommended for an additional primary quote source)
- `TUSHARE_TOKEN` (optional, recommended for more stable market data)

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

## Watchlist Management

The watched stock list is stored in `config/watchlist.yaml`. For low-frequency changes, use the CLI instead of editing JSON by hand:

```bash
python3 -m stock_monitor.watchlist list
python3 -m stock_monitor.watchlist validate
python3 -m stock_monitor.watchlist add \
  --symbol 000001.SZ \
  --name 平安银行 \
  --sector 银行 \
  --float-market-cap-cny 200000000000 \
  --watch-metrics volume,money_flow,technical,chip
python3 -m stock_monitor.watchlist remove --symbol 000001.SZ
```

After changing the watchlist:

```bash
python3 -m stock_monitor.watchlist validate
python3 -m stock_monitor.calibrate_thresholds
python3 -m stock_monitor.run_report --type close_report --dry-run
git add config/watchlist.yaml
git commit -m "Update stock watchlist"
git push origin main
```

GitHub Actions will use the updated watchlist on the next scheduled or manually triggered run.

## Templates

Report templates live under `templates/*.md.j2`. Each report has independent fields and layout so future edits to wording, order, or formatting do not require changing the agent workflow.
