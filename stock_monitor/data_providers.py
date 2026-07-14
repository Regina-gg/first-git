from __future__ import annotations

import math
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Protocol

from .models import NewsItem, PriceBar, StockConfig


class MarketDataProvider(Protocol):
    def get_history(self, stock: StockConfig, end_date: date, lookback_days: int) -> List[PriceBar]:
        ...


class NewsDataProvider(Protocol):
    def get_news(self, stocks: List[StockConfig], report_date: date) -> List[NewsItem]:
        ...


class SampleDataProvider:
    """Deterministic sample data provider for V1 local runs and tests."""

    def get_history(self, stock: StockConfig, end_date: date, lookback_days: int) -> List[PriceBar]:
        bars: List[PriceBar] = []
        base = 80.0 + (sum(ord(ch) for ch in stock.symbol) % 30)
        cap_factor = max(0.8, min(1.4, stock.float_market_cap_cny / 200_000_000_000))
        for idx in range(lookback_days):
            day = end_date - timedelta(days=lookback_days - idx - 1)
            seasonal = math.sin(idx / 7.0) * 0.018 + math.cos(idx / 17.0) * 0.012
            drift = idx * 0.0009
            close = base * (1 + drift + seasonal)
            open_price = close * (1 - 0.004 + math.sin(idx / 5.0) * 0.006)
            amplitude = 0.025 + abs(math.sin(idx / 9.0)) * 0.025 / cap_factor
            high = max(open_price, close) * (1 + amplitude / 2)
            low = min(open_price, close) * (1 - amplitude / 2)
            amount = 1_200_000_000 * cap_factor * (1 + 0.25 * math.sin(idx / 11.0))
            turnover = 0.018 * (1 / cap_factor) + 0.006 * abs(math.sin(idx / 13.0))
            main_flow = amount * (0.015 * math.sin(idx / 8.0))
            northbound = amount * (0.006 * math.cos(idx / 10.0))
            margin = 9_000_000_000 * cap_factor * (1 + 0.04 * math.sin(idx / 19.0))
            market_return = 0.004 * math.sin(idx / 6.0)
            sector_return = market_return + 0.006 * math.sin(idx / 8.0)
            bars.append(
                PriceBar(
                    date=day,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    amount=amount,
                    turnover_rate=turnover,
                    main_net_inflow=main_flow,
                    northbound_net_inflow=northbound,
                    large_order_ratio=0.18 + 0.03 * math.sin(idx / 6.0),
                    margin_balance=margin,
                    profit_ratio=0.48 + 0.2 * math.sin(idx / 18.0),
                    average_cost=close * (0.96 + 0.03 * math.cos(idx / 12.0)),
                    chip_width_90=0.18 + 0.04 * math.cos(idx / 15.0),
                    sector_return=sector_return,
                    market_return=market_return,
                )
            )
        return bars

    def get_news(self, stocks: List[StockConfig], report_date: date) -> List[NewsItem]:
        sectors = sorted({stock.sector for stock in stocks})
        return [
            NewsItem("海外科技股表现分化", "海外", "中性", "中", "隔夜外盘对成长板块影响偏中性，需观察开盘承接。"),
            NewsItem(f"{'、'.join(sectors)}板块政策预期升温", "政策", "利好", "中", "市场关注产业支持政策落地节奏。"),
            NewsItem("样例公告数据源未接入", "公司", "中性", "弱", "V1 示例数据不接入真实公告，正式部署需替换 NewsDataProvider。"),
        ]


class AkShareDataProvider:
    """AkShare-backed A-share daily data provider.

    V1 uses AkShare for real OHLCV, amount, amplitude, and turnover data.
    Funding, chip, margin, sector, and benchmark fields remain neutral unless
    a richer provider is added.
    """

    def __init__(self) -> None:
        try:
            import akshare as ak  # type: ignore
        except ImportError as exc:
            raise RuntimeError("DATA_PROVIDER=akshare requires installing akshare.") from exc
        self.ak = ak
        self.quality_notes = [
            f"行情数据来自 AkShare/Eastmoney 接口，复权方式 {_price_adjust()}，包含日线 OHLCV、成交额、涨跌幅、振幅、换手率。",
            "V1 AkShare 适配器暂未接入逐股主力资金、北向、融资、筹码和板块基准；相关字段按中性值处理。",
        ]

    def get_history(self, stock: StockConfig, end_date: date, lookback_days: int) -> List[PriceBar]:
        symbol = _strip_exchange(stock.symbol)
        start_date = (end_date - timedelta(days=max(lookback_days * 3, 380))).strftime("%Y%m%d")
        end = end_date.strftime("%Y%m%d")
        adjust = _akshare_adjust()
        try:
            frame = self.ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end, adjust=adjust)
        except TypeError:
            frame = self.ak.stock_zh_a_hist(symbol=symbol, start_date=start_date, end_date=end, adjust=adjust)
        if frame is None or len(frame) == 0:
            raise RuntimeError(f"AkShare returned no daily bars for {stock.symbol}.")
        rows = frame.tail(lookback_days).to_dict("records")
        bars = [_bar_from_akshare_row(row) for row in rows]
        if len(bars) < min(60, lookback_days):
            raise RuntimeError(f"AkShare returned only {len(bars)} bars for {stock.symbol}; at least 60 are required.")
        return bars

    def get_news(self, stocks: List[StockConfig], report_date: date) -> List[NewsItem]:
        items: List[NewsItem] = []
        for stock in stocks:
            symbol = _strip_exchange(stock.symbol)
            try:
                frame = self.ak.stock_news_em(symbol=symbol)
            except Exception:
                continue
            if frame is None or len(frame) == 0:
                continue
            for row in frame.head(3).to_dict("records"):
                title = str(_value(row, ["新闻标题", "标题", "title"], f"{stock.name} 新闻"))
                summary = str(_value(row, ["新闻内容", "内容", "summary"], "新闻摘要暂缺。"))
                category = _classify_news_category(title, summary, stock)
                items.append(NewsItem(title=title, category=category, sentiment=_classify_sentiment(title + summary), impact="中", summary=summary[:160]))
        if items:
            return _dedupe_news(items)
        return []


class TushareDataProvider:
    """Tushare Pro daily data provider.

    Requires TUSHARE_TOKEN. Daily bars come from pro.daily; turnover is enriched
    from pro.daily_basic when available.
    """

    def __init__(self, token: Optional[str] = None) -> None:
        token = token or os.getenv("TUSHARE_TOKEN")
        if not token:
            raise RuntimeError("DATA_PROVIDER=tushare requires TUSHARE_TOKEN.")
        try:
            import tushare as ts  # type: ignore
        except ImportError as exc:
            raise RuntimeError("DATA_PROVIDER=tushare requires installing tushare.") from exc
        self.ts = ts
        self.pro = ts.pro_api(token)
        self.quality_notes = [
            f"行情数据优先来自 Tushare Pro，复权方式 {_price_adjust()}，包含日线 OHLC、成交量、成交额和换手率。",
            "V1 Tushare 适配器暂未接入逐股主力资金、北向、融资和筹码；相关字段按中性值处理。",
        ]

    def get_history(self, stock: StockConfig, end_date: date, lookback_days: int) -> List[PriceBar]:
        start_date = (end_date - timedelta(days=max(lookback_days * 3, 380))).strftime("%Y%m%d")
        end = end_date.strftime("%Y%m%d")
        try:
            frame = self.ts.pro_bar(ts_code=stock.symbol, start_date=start_date, end_date=end, adj=_tushare_adjust(), adjfactor=False)
            if frame is None or len(frame) == 0:
                frame = self.pro.daily(ts_code=stock.symbol, start_date=start_date, end_date=end)
        except Exception as exc:
            raise RuntimeError(_sanitize_provider_error("Tushare daily", exc)) from exc
        if frame is None or len(frame) == 0:
            raise RuntimeError(f"Tushare returned no daily bars for {stock.symbol}.")
        try:
            basics = self.pro.daily_basic(ts_code=stock.symbol, start_date=start_date, end_date=end, fields="ts_code,trade_date,turnover_rate")
            if basics is not None and len(basics) > 0:
                frame = frame.merge(basics[["trade_date", "turnover_rate"]], on="trade_date", how="left")
        except Exception as exc:
            self.quality_notes.append(f"{stock.name}（{stock.symbol}）Tushare daily_basic 暂不可用：{_sanitize_provider_error('Tushare daily_basic', exc)}")
            frame["turnover_rate"] = 0.0
        rows = frame.sort_values("trade_date").tail(lookback_days).to_dict("records")
        bars = [_bar_from_tushare_row(row) for row in rows]
        if len(bars) < min(60, lookback_days):
            raise RuntimeError(f"Tushare returned only {len(bars)} bars for {stock.symbol}; at least 60 are required.")
        return bars

    def get_news(self, stocks: List[StockConfig], report_date: date) -> List[NewsItem]:
        return []


class EastmoneyDirectDataProvider:
    """Direct Eastmoney historical kline provider without AkShare wrapper."""

    def __init__(self) -> None:
        try:
            import requests  # type: ignore
        except ImportError as exc:
            raise RuntimeError("DATA_PROVIDER=eastmoney requires installing requests.") from exc
        self.requests = requests
        self.quality_notes = [
            f"行情数据来自东方财富历史 K 线接口直连，复权方式 {_price_adjust()}，包含日线 OHLCV、成交额、涨跌幅、振幅和换手率。",
            "V1 东方财富直连适配器暂未接入逐股主力资金、北向、融资和筹码；相关字段按中性值处理。",
        ]

    def get_history(self, stock: StockConfig, end_date: date, lookback_days: int) -> List[PriceBar]:
        start_date = (end_date - timedelta(days=max(lookback_days * 3, 380))).strftime("%Y%m%d")
        end = end_date.strftime("%Y%m%d")
        try:
            response = self.requests.get(
                "https://push2his.eastmoney.com/api/qt/stock/kline/get",
                params={
                    "secid": _eastmoney_secid(stock.symbol),
                    "fields1": "f1,f2,f3,f4,f5,f6",
                    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                    "klt": "101",
                    "fqt": _eastmoney_fqt(),
                    "beg": start_date,
                    "end": end,
                },
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise RuntimeError(_sanitize_provider_error("Eastmoney", exc)) from exc
        klines = payload.get("data", {}).get("klines", []) if isinstance(payload, dict) else []
        if not klines:
            raise RuntimeError(f"Eastmoney returned no daily bars for {stock.symbol}.")
        bars = [_bar_from_eastmoney_kline(item) for item in klines[-lookback_days:]]
        if len(bars) < min(60, lookback_days):
            raise RuntimeError(f"Eastmoney returned only {len(bars)} bars for {stock.symbol}; at least 60 are required.")
        return bars

    def get_news(self, stocks: List[StockConfig], report_date: date) -> List[NewsItem]:
        return []


class MultiSourceDataProvider:
    """Fallback chain across configured market data providers."""

    def __init__(self, chain: Optional[str] = None) -> None:
        names = [item.strip() for item in (chain or os.getenv("MARKET_DATA_CHAIN", "eastmoney,akshare")).split(",") if item.strip()]
        self.providers = []
        self.quality_notes = ["多数据源模式已启用，按配置顺序尝试：" + " -> ".join(names)]
        for name in names:
            try:
                provider = _single_provider_from_name(name)
                self.providers.append((name, provider))
                self.quality_notes.extend(getattr(provider, "quality_notes", []))
            except Exception as exc:
                self.quality_notes.append(f"{name} 数据源未启用：{exc}")
        if not self.providers:
            raise RuntimeError("No market data providers are available in DATA_PROVIDER=multi.")

    def get_history(self, stock: StockConfig, end_date: date, lookback_days: int) -> List[PriceBar]:
        errors = []
        for name, provider in self.providers:
            try:
                bars = provider.get_history(stock, end_date, lookback_days)
                self.quality_notes.append(f"{stock.name}（{stock.symbol}）行情使用 {name} 数据源。")
                return bars
            except Exception as exc:
                error = _sanitize_provider_error(name, exc)
                errors.append(f"{name}: {error}")
                self.quality_notes.append(f"{stock.name}（{stock.symbol}）{name} 数据源失败，已尝试降级：{error}")
        raise RuntimeError("; ".join(errors))

    def get_news(self, stocks: List[StockConfig], report_date: date) -> List[NewsItem]:
        for _name, provider in self.providers:
            try:
                items = provider.get_news(stocks, report_date)
            except Exception:
                continue
            if items:
                return items
        return [NewsItem("新闻源暂未返回内容", "公司", "中性", "弱", "所有已配置新闻源均未返回有效内容。")]


def _classify_news_category(title: str, summary: str, stock: StockConfig) -> str:
    text = f"{title} {summary}"
    if any(keyword in text for keyword in ["政策", "发改委", "工信部", "财政部", "央行", "证监会", "国务院", "监管", "补贴", "规划"]):
        return "政策"
    if stock.sector in text or any(keyword in text for keyword in ["行业", "产业", "算力", "光通信", "光纤", "通信", "AI", "数据中心"]):
        return "行业"
    return "公司"


def _classify_sentiment(text: str) -> str:
    if any(keyword in text for keyword in ["增长", "中标", "突破", "利好", "上调", "合作", "签约", "扩产"]):
        return "利好"
    if any(keyword in text for keyword in ["下滑", "处罚", "减持", "亏损", "风险", "问询", "诉讼"]):
        return "利空"
    return "中性"


def _dedupe_news(items: List[NewsItem], limit: int = 9) -> List[NewsItem]:
    seen = set()
    result = []
    for item in items:
        key = item.title.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def _strip_exchange(symbol: str) -> str:
    return symbol.split(".")[0]


def _eastmoney_secid(symbol: str) -> str:
    code = _strip_exchange(symbol)
    if symbol.endswith(".SH") or code.startswith("6"):
        return f"1.{code}"
    return f"0.{code}"


def _price_adjust() -> str:
    value = os.getenv("PRICE_ADJUST", "qfq").strip().lower()
    return value if value in {"qfq", "hfq", "none"} else "qfq"


def _akshare_adjust() -> str:
    adjust = _price_adjust()
    return "" if adjust == "none" else adjust


def _tushare_adjust() -> Optional[str]:
    adjust = _price_adjust()
    return None if adjust == "none" else adjust


def _eastmoney_fqt() -> str:
    return {"none": "0", "qfq": "1", "hfq": "2"}[_price_adjust()]


def _sanitize_provider_error(source: str, exc: Exception) -> str:
    message = str(exc).replace(os.getenv("TUSHARE_TOKEN", ""), "[redacted]") if os.getenv("TUSHARE_TOKEN") else str(exc)
    lowered = message.lower()
    if any(keyword in message for keyword in ["积分", "权限", "抱歉", "访问该接口的权限", "每分钟最多访问"]):
        return f"{source} 权限/积分/频率限制，已降级到下一数据源"
    if any(keyword in lowered for keyword in ["permission", "quota", "rate limit", "limit", "forbidden", "unauthorized"]):
        return f"{source} 权限/额度/频率限制，已降级到下一数据源"
    if any(keyword in lowered for keyword in ["max retries", "connectionpool", "timed out", "timeout", "could not resolve", "connection refused"]):
        return f"{source} 网络连接失败或超时，已跳过该字段"
    return message[:240]


def _value(row: Dict[str, Any], names: List[str], default: Any = 0.0) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return default


def _float(row: Dict[str, Any], names: List[str], default: float = 0.0) -> float:
    value = _value(row, names, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _date(row: Dict[str, Any]) -> date:
    value = _value(row, ["日期", "date"])
    if hasattr(value, "date"):
        return value.date()
    return date.fromisoformat(str(value)[:10])


def _trade_date(value: Any) -> date:
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    return date.fromisoformat(text[:10])


def _bar_from_akshare_row(row: Dict[str, Any]) -> PriceBar:
    close = _float(row, ["收盘", "收盘价", "close"])
    open_price = _float(row, ["开盘", "open"], close)
    high = _float(row, ["最高", "high"], close)
    low = _float(row, ["最低", "low"], close)
    pct_change = _float(row, ["涨跌幅"], 0.0) / 100
    return PriceBar(
        date=_date(row),
        open=open_price,
        high=high,
        low=low,
        close=close,
        amount=_float(row, ["成交额", "amount"], 0.0),
        turnover_rate=_float(row, ["换手率"], 0.0) / 100,
        main_net_inflow=0.0,
        northbound_net_inflow=0.0,
        large_order_ratio=0.0,
        margin_balance=1.0,
        profit_ratio=0.5,
        average_cost=close,
        chip_width_90=1.0,
        sector_return=pct_change,
        market_return=pct_change,
    )


def _bar_from_tushare_row(row: Dict[str, Any]) -> PriceBar:
    close = _float(row, ["close"])
    pct_change = _float(row, ["pct_chg"], 0.0) / 100
    return PriceBar(
        date=_trade_date(_value(row, ["trade_date"])),
        open=_float(row, ["open"], close),
        high=_float(row, ["high"], close),
        low=_float(row, ["low"], close),
        close=close,
        amount=_float(row, ["amount"], 0.0) * 1000,
        turnover_rate=_float(row, ["turnover_rate"], 0.0) / 100,
        main_net_inflow=0.0,
        northbound_net_inflow=0.0,
        large_order_ratio=0.0,
        margin_balance=1.0,
        profit_ratio=0.5,
        average_cost=close,
        chip_width_90=1.0,
        sector_return=pct_change,
        market_return=pct_change,
    )


def _bar_from_eastmoney_kline(kline: str) -> PriceBar:
    parts = kline.split(",")
    if len(parts) < 11:
        raise RuntimeError(f"Invalid Eastmoney kline row: {kline}")
    close = float(parts[2])
    pct_change = float(parts[8]) / 100
    return PriceBar(
        date=date.fromisoformat(parts[0]),
        open=float(parts[1]),
        close=close,
        high=float(parts[3]),
        low=float(parts[4]),
        amount=float(parts[6]),
        turnover_rate=float(parts[10]) / 100,
        main_net_inflow=0.0,
        northbound_net_inflow=0.0,
        large_order_ratio=0.0,
        margin_balance=1.0,
        profit_ratio=0.5,
        average_cost=close,
        chip_width_90=1.0,
        sector_return=pct_change,
        market_return=pct_change,
    )


def _single_provider_from_name(name: str):
    if name == "sample":
        return SampleDataProvider()
    if name == "akshare":
        return AkShareDataProvider()
    if name == "tushare":
        return TushareDataProvider()
    if name == "eastmoney":
        return EastmoneyDirectDataProvider()
    raise ValueError(f"Unsupported provider in V1: {name}")


def provider_from_name(name: str):
    if name == "multi":
        return MultiSourceDataProvider()
    return _single_provider_from_name(name)
