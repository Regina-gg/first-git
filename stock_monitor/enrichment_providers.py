from __future__ import annotations

import os
from dataclasses import replace
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Protocol, Tuple

from .config import load_config
from .data_providers import _float, _sanitize_provider_error, _strip_exchange, _trade_date
from .metrics import safe_div
from .models import PriceBar, StockConfig


class EnrichmentProvider(Protocol):
    def enrich_history(self, stock: StockConfig, bars: List[PriceBar], end_date: date) -> Tuple[List[PriceBar], List[str]]:
        ...


class NoopEnrichmentProvider:
    def enrich_history(self, stock: StockConfig, bars: List[PriceBar], end_date: date) -> Tuple[List[PriceBar], List[str]]:
        return bars, ["增强数据源未启用；资金、融资、筹码和板块基准字段保持行情源默认值。"]


class TushareEnrichmentProvider:
    """Adds money flow, margin, chip, and benchmark fields from Tushare Pro."""

    def __init__(self, token: Optional[str] = None) -> None:
        token = token or os.getenv("TUSHARE_TOKEN")
        if not token:
            raise RuntimeError("Tushare enrichment requires TUSHARE_TOKEN.")
        try:
            import tushare as ts  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Tushare enrichment requires installing tushare.") from exc
        self.pro = ts.pro_api(token)
        self.benchmarks = load_config("config/sector_benchmarks.yaml")

    def enrich_history(self, stock: StockConfig, bars: List[PriceBar], end_date: date) -> Tuple[List[PriceBar], List[str]]:
        notes: List[str] = []
        enriched = list(bars)
        start = (end_date - timedelta(days=max(len(bars) * 3, 380))).strftime("%Y%m%d")
        end = end_date.strftime("%Y%m%d")
        enriched, note = self._with_money_flow(stock, enriched, start, end)
        notes.append(note)
        enriched, note = self._with_margin(stock, enriched, start, end)
        notes.append(note)
        enriched, note = self._with_chip(stock, enriched, start, end)
        notes.append(note)
        enriched, note = self._with_sector_benchmark(stock, enriched, start, end)
        notes.append(note)
        return enriched, notes

    def _with_money_flow(self, stock: StockConfig, bars: List[PriceBar], start: str, end: str) -> Tuple[List[PriceBar], str]:
        try:
            frame = self.pro.moneyflow(ts_code=stock.symbol, start_date=start, end_date=end)
            if frame is None or len(frame) == 0:
                return bars, f"{stock.name} 主力资金：Tushare moneyflow 未返回数据。"
            by_date = {str(row["trade_date"]): row for row in frame.to_dict("records")}
            updated = []
            for bar in bars:
                row = by_date.get(bar.date.strftime("%Y%m%d"))
                if not row:
                    updated.append(bar)
                    continue
                buy_lg = _float(row, ["buy_lg_amount"])
                buy_elg = _float(row, ["buy_elg_amount"])
                sell_lg = _float(row, ["sell_lg_amount"])
                sell_elg = _float(row, ["sell_elg_amount"])
                net = (buy_lg + buy_elg - sell_lg - sell_elg) * 10000
                large_total = (buy_lg + buy_elg + sell_lg + sell_elg) * 10000
                updated.append(replace(bar, main_net_inflow=net, large_order_ratio=safe_div(large_total, bar.amount)))
            return updated, f"{stock.name} 主力资金：已接入 Tushare moneyflow。"
        except Exception as exc:
            return bars, f"{stock.name} 主力资金暂缺：{_sanitize_provider_error('Tushare moneyflow', exc)}"

    def _with_margin(self, stock: StockConfig, bars: List[PriceBar], start: str, end: str) -> Tuple[List[PriceBar], str]:
        try:
            frame = self.pro.margin_detail(ts_code=stock.symbol, start_date=start, end_date=end)
            if frame is None or len(frame) == 0:
                return bars, f"{stock.name} 融资融券：Tushare margin_detail 未返回数据。"
            by_date = {str(row["trade_date"]): row for row in frame.to_dict("records")}
            updated = []
            for bar in bars:
                row = by_date.get(bar.date.strftime("%Y%m%d"))
                if not row:
                    updated.append(bar)
                    continue
                updated.append(replace(bar, margin_balance=_float(row, ["rzye", "rzrqye"], bar.margin_balance) * 10000))
            return updated, f"{stock.name} 融资融券：已接入 Tushare margin_detail。"
        except Exception as exc:
            return bars, f"{stock.name} 融资融券暂缺：{_sanitize_provider_error('Tushare margin_detail', exc)}"

    def _with_chip(self, stock: StockConfig, bars: List[PriceBar], start: str, end: str) -> Tuple[List[PriceBar], str]:
        try:
            frame = self.pro.cyq_perf(ts_code=stock.symbol, start_date=start, end_date=end)
            if frame is None or len(frame) == 0:
                return bars, f"{stock.name} 筹码：Tushare cyq_perf 未返回数据。"
            by_date = {str(row["trade_date"]): row for row in frame.to_dict("records")}
            updated = []
            for bar in bars:
                row = by_date.get(bar.date.strftime("%Y%m%d"))
                if not row:
                    updated.append(bar)
                    continue
                average_cost = _float(row, ["cost_50pct", "weight_avg"], bar.average_cost)
                width = abs(_float(row, ["cost_85pct"], average_cost) - _float(row, ["cost_15pct"], average_cost))
                updated.append(
                    replace(
                        bar,
                        profit_ratio=_float(row, ["winner_rate"], bar.profit_ratio),
                        average_cost=average_cost,
                        chip_width_90=width or bar.chip_width_90,
                    )
                )
            return updated, f"{stock.name} 筹码：已接入 Tushare cyq_perf。"
        except Exception as exc:
            return bars, f"{stock.name} 筹码暂缺：{_sanitize_provider_error('Tushare cyq_perf', exc)}"

    def _with_sector_benchmark(self, stock: StockConfig, bars: List[PriceBar], start: str, end: str) -> Tuple[List[PriceBar], str]:
        benchmark = self.benchmarks.get("sector_benchmarks", {}).get(stock.sector)
        if not benchmark:
            return bars, f"{stock.name} 板块基准：未配置 {stock.sector} 对应指数。"
        try:
            frame = self.pro.index_daily(ts_code=benchmark["symbol"], start_date=start, end_date=end)
            if frame is None or len(frame) == 0:
                return bars, f"{stock.name} 板块基准：{benchmark['name']} 未返回指数行情。"
            rows = sorted(frame.to_dict("records"), key=lambda item: item["trade_date"])
            returns = {}
            prev_close = None
            for row in rows:
                close = _float(row, ["close"])
                returns[str(row["trade_date"])] = safe_div(close - prev_close, prev_close) if prev_close else 0.0
                prev_close = close
            updated = [replace(bar, sector_return=returns.get(bar.date.strftime("%Y%m%d"), bar.sector_return)) for bar in bars]
            return updated, f"{stock.name} 板块基准：已接入 {benchmark['name']}（{benchmark['symbol']}）。"
        except Exception as exc:
            return bars, f"{stock.name} 板块基准暂缺：{_sanitize_provider_error('Tushare index_daily', exc)}"


class AkShareEnrichmentProvider:
    """Best-effort public-source enrichment via AkShare."""

    def __init__(self) -> None:
        try:
            import akshare as ak  # type: ignore
        except ImportError as exc:
            raise RuntimeError("AkShare enrichment requires installing akshare.") from exc
        self.ak = ak

    def enrich_history(self, stock: StockConfig, bars: List[PriceBar], end_date: date) -> Tuple[List[PriceBar], List[str]]:
        enriched, money_note = self._with_money_flow(stock, bars)
        enriched, margin_note = self._with_margin(stock, enriched)
        return enriched, [money_note, margin_note, f"{stock.name} 筹码/板块基准：AkShare fallback 暂未提供稳定统一映射。"]

    def _with_money_flow(self, stock: StockConfig, bars: List[PriceBar]) -> Tuple[List[PriceBar], str]:
        try:
            frame = self.ak.stock_individual_fund_flow(stock=_strip_exchange(stock.symbol), market="sh" if stock.symbol.endswith(".SH") else "sz")
            if frame is None or len(frame) == 0:
                return bars, f"{stock.name} 主力资金：AkShare 未返回数据。"
            by_date = {_trade_date(row.get("日期")).strftime("%Y%m%d"): row for row in frame.to_dict("records")}
            updated = []
            for bar in bars:
                row = by_date.get(bar.date.strftime("%Y%m%d"))
                if not row:
                    updated.append(bar)
                    continue
                updated.append(
                    replace(
                        bar,
                        main_net_inflow=_float(row, ["主力净流入-净额", "主力净流入净额"], bar.main_net_inflow),
                        large_order_ratio=_float(row, ["主力净流入-净占比", "主力净流入净占比"], 0.0) / 100,
                    )
                )
            return updated, f"{stock.name} 主力资金：已接入 AkShare 个股资金流。"
        except Exception as exc:
            return bars, f"{stock.name} 主力资金暂缺：{_sanitize_provider_error('AkShare fund flow', exc)}"

    def _with_margin(self, stock: StockConfig, bars: List[PriceBar]) -> Tuple[List[PriceBar], str]:
        try:
            frame = self.ak.stock_margin_detail_sse(date=bars[-1].date.strftime("%Y%m%d")) if stock.symbol.endswith(".SH") else None
            if frame is None or len(frame) == 0:
                return bars, f"{stock.name} 融资融券：AkShare 暂未返回可映射数据。"
            code = _strip_exchange(stock.symbol)
            rows = [row for row in frame.to_dict("records") if str(row.get("标的证券代码", row.get("证券代码", ""))).zfill(6) == code]
            if not rows:
                return bars, f"{stock.name} 融资融券：AkShare 未找到该股票记录。"
            row = rows[-1]
            latest = replace(bars[-1], margin_balance=_float(row, ["融资余额", "融资融券余额"], bars[-1].margin_balance))
            return bars[:-1] + [latest], f"{stock.name} 融资融券：已接入 AkShare 最新交易日融资余额。"
        except Exception as exc:
            return bars, f"{stock.name} 融资融券暂缺：{_sanitize_provider_error('AkShare margin', exc)}"


class MultiEnrichmentProvider:
    def __init__(self, chain: Optional[str] = None) -> None:
        names = [item.strip() for item in (chain or os.getenv("ENRICHMENT_CHAIN", "tushare,akshare")).split(",") if item.strip()]
        self.providers = []
        self.init_notes = ["增强数据源按顺序尝试：" + " -> ".join(names)]
        for name in names:
            try:
                self.providers.append((name, _enrichment_provider_from_name(name)))
            except Exception as exc:
                self.init_notes.append(f"{name} 增强数据源未启用：{_sanitize_provider_error(name, exc)}")

    def enrich_history(self, stock: StockConfig, bars: List[PriceBar], end_date: date) -> Tuple[List[PriceBar], List[str]]:
        notes = list(self.init_notes)
        enriched = bars
        for name, provider in self.providers:
            try:
                enriched, provider_notes = provider.enrich_history(stock, enriched, end_date)
                notes.extend(provider_notes)
            except Exception as exc:
                notes.append(f"{stock.name} {name} 增强失败：{_sanitize_provider_error(name, exc)}")
        return enriched, notes


def _enrichment_provider_from_name(name: str) -> EnrichmentProvider:
    if name == "none":
        return NoopEnrichmentProvider()
    if name == "tushare":
        return TushareEnrichmentProvider()
    if name == "akshare":
        return AkShareEnrichmentProvider()
    raise ValueError(f"Unsupported enrichment provider: {name}")


def enrichment_provider_from_env() -> EnrichmentProvider:
    provider = os.getenv("ENRICHMENT_PROVIDER", "multi")
    if provider == "multi":
        return MultiEnrichmentProvider()
    return _enrichment_provider_from_name(provider)
