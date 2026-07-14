from __future__ import annotations

from typing import List

from ..metrics import classify_trend
from ..models import DecisionResult, ReportType, ResearchResult, StockMetrics


def pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def ratio(value: float) -> str:
    return f"{value:.2f}x"


NO_MARKET_DATA = "- 真实行情数据暂缺；本模块不生成量价判断，请查看数据质量说明。"


class DecisionAgent:
    """Explains what the research result means."""

    def run(self, research: ResearchResult) -> DecisionResult:
        stocks = research.stocks
        stance_score = sum(self._stock_score(stock) for stock in stocks)
        stance = "偏多" if stance_score > 1 else "偏空" if stance_score < -1 else "震荡"
        confidence = min(90, max(45, 60 + abs(stance_score) * 8))
        risks = self._risks(stocks)
        catalysts = self._catalysts(stocks, research)
        actions = self._actions(stocks, stance)
        sections = self._sections(research, stance, confidence, risks, catalysts, actions)
        return DecisionResult(
            report_type=research.report_type,
            report_date=research.report_date,
            summary=f"{research.report_date.isoformat()} 综合判断：{stance}，置信度 {confidence} 分。",
            confidence=confidence,
            stance=stance,
            risks=risks,
            catalysts=catalysts,
            actions=actions,
            sections=sections,
        )

    def _stock_score(self, stock: StockMetrics) -> int:
        score = 0
        score += 1 if stock.pct_change > 0 else -1
        score += 1 if stock.main_fund_strength > 0.05 else -1 if stock.main_fund_strength < -0.05 else 0
        score += 1 if stock.ma_alignment.startswith("多头") else -1 if stock.ma_alignment.startswith("空头") else 0
        return score

    def _risks(self, stocks: List[StockMetrics]) -> List[str]:
        risks = []
        for stock in stocks:
            if stock.rsi_percentile > 90:
                risks.append(f"{stock.name} RSI 位于 {stock.rsi_percentile:.0f} 分位，短线有过热风险。")
            if stock.amount_ratio > 1.5 and stock.pct_change < 0:
                risks.append(f"{stock.name} 放量下跌，需防范资金出逃。")
            if stock.ma10_deviation < -0.03:
                risks.append(f"{stock.name} 跌破 10 日均线超过 3%，技术支撑转弱。")
        return risks or ["未出现多维度共振的高等级风险信号。"]

    def _catalysts(self, stocks: List[StockMetrics], research: ResearchResult) -> List[str]:
        catalysts = []
        for news in research.news:
            if news.sentiment == "利好":
                catalysts.append(f"{news.category}：{news.title}（影响 {news.impact}）。")
        for stock in stocks:
            if stock.main_fund_strength > 0.05 and stock.amount_ratio > 1.3:
                catalysts.append(f"{stock.name} 资金流入配合放量，短线情绪偏强。")
        return catalysts or ["暂无强催化，重点观察资金和板块联动是否延续。"]

    def _actions(self, stocks: List[StockMetrics], stance: str) -> List[str]:
        actions = []
        for stock in stocks:
            trend = classify_trend(stock)
            if trend in {"强多", "弱多"} and stock.rsi_percentile < 90:
                actions.append(f"{stock.name}：维持关注，若放量突破前高可上调策略。")
            elif trend in {"弱空", "强空"}:
                actions.append(f"{stock.name}：降低进攻性，等待缩量企稳或资金回流。")
            else:
                actions.append(f"{stock.name}：按震荡处理，围绕 5/10 日线观察承接。")
        if stance == "偏空":
            actions.append("组合层面优先控制仓位，避免追高。")
        return actions

    def _stock_lines(self, stocks: List[StockMetrics]) -> str:
        if not stocks:
            return NO_MARKET_DATA
        return "\n".join(
            [
                f"- {s.name}：收盘 {s.close:.2f}，涨跌幅 {pct(s.pct_change)}，量比 {ratio(s.amount_ratio)}（{s.labels['量比']}），趋势 {s.labels['趋势评级']}。"
                for s in stocks
            ]
        )

    def _sections(
        self,
        research: ResearchResult,
        stance: str,
        confidence: int,
        risks: List[str],
        catalysts: List[str],
        actions: List[str],
    ) -> dict[str, str]:
        stocks = research.stocks
        stock_lines = self._stock_lines(stocks)
        news_lines = "\n".join([f"- {item.sentiment}/{item.impact}：{item.title}。{item.summary}" for item in research.news])
        stock_names = "、".join([stock.name for stock in stocks]) or "当前股票池"
        key_levels = NO_MARKET_DATA if not stocks else "\n".join(
            [
                f"- {s.name}：S1 约 {s.close * 0.97:.2f}，S2 约 {s.close * 0.94:.2f}；R1 约 {s.close * 1.03:.2f}，R2 约 {s.close * 1.06:.2f}。"
                for s in stocks
            ]
        )
        threshold_lines = "\n".join(
            [
                f"- {p.name}：{p.stock_type}，阈值系数 {p.threshold_multiplier:.1f}，资金阈值系数 {p.funding_multiplier:.1f}，Beta {p.beta_250d:.2f}。"
                for p in research.thresholds.values()
            ]
        )
        return {
            "market_transmission": "- 纳斯达克金龙、A50、海外 AI 链示例数据暂未接入真实行情。\n- 当前按持仓自身历史指标和样例新闻生成盘前判断。",
            "news_summary": news_lines,
            "funding_preview": "\n".join([f"- {s.name}：主力资金强度 {pct(s.main_fund_strength)}，融资变动率 {pct(s.margin_change_rate)}。" for s in stocks]) or NO_MARKET_DATA,
            "key_levels": key_levels,
            "daily_outlook": f"- 当日判断：{stance}，置信度 {confidence} 分。\n" + ("\n".join([f"- {item}" for item in actions]) or NO_MARKET_DATA),
            "morning_volume": "\n".join([f"- {s.name}：开盘量能代理值量比 {ratio(s.amount_ratio)}，换手率倍数 {ratio(s.turnover_ratio)}。" for s in stocks]) or NO_MARKET_DATA,
            "fund_flow_check": "\n".join([f"- {s.name}：主力资金强度 {pct(s.main_fund_strength)}，大单占比偏离 {pct(s.large_order_deviation)}。" for s in stocks]) or NO_MARKET_DATA,
            "sector_check": "\n".join([f"- {s.name}：相对板块 {pct(s.sector_excess_return)}，相对大盘 {pct(s.market_excess_return)}。" for s in stocks]) or NO_MARKET_DATA,
            "technical_check": "\n".join([f"- {s.name}：均线 {s.ma_alignment}，布林位置 {s.bollinger_position:.2f}，RSI {s.rsi_percentile:.0f} 分位。" for s in stocks]) or NO_MARKET_DATA,
            "strategy_update": "\n".join([f"- {item}" for item in actions]) or NO_MARKET_DATA,
            "price_volume_review": stock_lines,
            "technical_review": "\n".join([f"- {s.name}：{s.ma_alignment}，RSI {s.rsi_percentile:.0f} 分位，MACD 柱强度 {s.macd_bar_strength:.2f}，布林 {s.labels['布林']}。" for s in stocks]) or NO_MARKET_DATA,
            "funding_review": "\n".join([f"- {s.name}：主力 {pct(s.main_fund_strength)}，北向偏离 {s.northbound_deviation:.2f}，融资 {pct(s.margin_change_rate)}。" for s in stocks]) or NO_MARKET_DATA,
            "chip_review": "\n".join([f"- {s.name}：获利盘 5 日变化 {pct(s.profit_ratio_change_5d)}，成本偏离 {pct(s.cost_deviation)}，筹码集中度 {s.chip_concentration_ratio:.2f}。" for s in stocks]) or NO_MARKET_DATA,
            "sector_comparison": "\n".join([f"- {s.name}：较板块 {pct(s.sector_excess_return)}，较沪深 300 代理 {pct(s.market_excess_return)}。" for s in stocks]) or NO_MARKET_DATA,
            "trend_rating": "\n".join([f"- {s.name}：{s.labels['趋势评级']}。自适应校准：{research.thresholds[s.symbol].stock_type}。" for s in stocks]) or NO_MARKET_DATA,
            "tomorrow_levels": key_levels,
            "policy_intel": self._news_section(research.news, {"政策"}, f"未发现与 {stock_names} 直接相关的政策新闻；不把无来源政策传闻纳入判断。"),
            "industry_intel": self._news_section(research.news, {"行业", "海外"}, f"未发现与 {stock_names} 所属板块直接相关的新增行业新闻；行业面先按盘面强弱和后续公告验证。"),
            "company_intel": self._news_section(research.news, {"公司"}, f"未发现 {stock_names} 的新增公司新闻；后续应优先补充交易所公告/巨潮公告源。"),
            "sentiment_intel": "\n".join([f"- {s.name}：量能 {s.labels['量比']}，RSI {s.labels['RSI']}，趋势 {s.labels['趋势评级']}。" for s in stocks]) or NO_MARKET_DATA,
            "next_day_preview": f"- 次日基准情景：{stance}。\n" + "\n".join([f"- {risk}" for risk in risks]),
            "threshold_profiles": threshold_lines,
            "data_quality": self._data_quality_summary(research.data_quality),
        }

    def _news_section(self, news, categories: set[str], fallback: str) -> str:
        lines = [f"- {item.title}：{item.summary}" for item in news if item.category in categories]
        return "\n".join(lines[:4]) if lines else f"- {fallback}"

    def _data_quality_summary(self, notes: List[str]) -> str:
        if not notes:
            return "- 数据源未返回额外质量说明。"
        quote_notes = [item for item in notes if "行情使用" in item]
        quote_missing = [item for item in notes if "行情数据暂缺" in item]
        missing_notes = [
            item
            for item in notes
            if any(keyword in item for keyword in ["暂缺", "未返回", "权限", "频率", "超时", "失败"])
            and "行情使用" not in item
            and "行情数据暂缺" not in item
        ]
        lines = []
        if quote_notes:
            compact = []
            for item in quote_notes:
                compact.append(item.replace("行情使用 ", "使用 ").replace(" 数据源。", ""))
            lines.append("基础行情：" + "；".join(compact[:4]) + "。")
        elif quote_missing:
            lines.append("基础行情：" + "；".join([_short_quality_note(item) for item in quote_missing[:2]]) + "。")
        else:
            lines.append("基础行情：未确认真实行情源，需查看运行日志。")
        if missing_notes:
            missing_text = "；".join([_quality_bucket(item) for item in missing_notes])
            lines.append(f"可选增强字段：{_unique_join(missing_text.split('；'))} 受接口权限/返回情况影响，已保留已有行情判断。")
        else:
            lines.append("可选增强字段：当前未记录阻塞性缺口。")
        return "\n".join([f"- {line}" for line in lines[:4]])


def _quality_bucket(note: str) -> str:
    if "主力资金" in note:
        return "主力资金"
    if "融资" in note:
        return "融资融券"
    if "筹码" in note:
        return "筹码"
    if "板块" in note:
        return "板块基准"
    if "新闻" in note or "公告" in note:
        return "新闻公告"
    return "部分字段"


def _unique_join(items: List[str]) -> str:
    result = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return "、".join(result[:5]) or "部分字段"


def _short_quality_note(note: str) -> str:
    return note.split("：", 1)[0] if len(note) > 80 else note
