"""I1：子圖拆分示範（研究子圖 + 回覆子圖）。"""

from __future__ import annotations

import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from langgraph_learning.tools.market import (
    get_eth_usdt_price_binance,
    get_usd_thb_exchange_rate,
)


class I1State(TypedDict):
    """外層圖共享狀態（貼近實務命名）。"""

    question: str
    intent: str
    market_snapshot: dict[str, str]
    final_response: str
    errors: list[str]


class ResearchState(TypedDict):
    """查資料子圖狀態。"""

    question: str
    intent: str
    market_snapshot: dict[str, str]
    errors: list[str]


class ComposeState(TypedDict):
    """寫回覆子圖狀態。"""

    question: str
    intent: str
    market_snapshot: dict[str, str]
    final_response: str
    errors: list[str]


def _research_fetch_market(
    state: ResearchState,
) -> dict[str, dict[str, str] | list[str]]:
    """研究子圖：查匯率與幣價，整理成 market_snapshot / errors。"""
    market_snapshot: dict[str, str] = {}
    errors: list[str] = list(state.get("errors", []))

    fx_raw = get_usd_thb_exchange_rate.invoke({"to_currency": "THB"})
    price_raw = get_eth_usdt_price_binance.invoke({"symbol": "ETHUSDT"})

    try:
        fx_data = json.loads(fx_raw)
        if "error" in fx_data:
            errors.append(f"USD/THB 查詢失敗：{fx_data['error']}")
        else:
            market_snapshot["usd_thb"] = str(fx_data.get("usd_to_thb", "unknown"))
            market_snapshot["fx_date"] = str(fx_data.get("date", "unknown"))
    except json.JSONDecodeError:
        errors.append(f"USD/THB 回傳非 JSON：{fx_raw}")

    try:
        price_data = json.loads(price_raw)
        if "error" in price_data:
            errors.append(f"ETHUSDT 查詢失敗：{price_data['error']}")
        else:
            market_snapshot["eth_usdt"] = str(price_data.get("price_usdt", "unknown"))
            market_snapshot["eth_source"] = str(price_data.get("source", "unknown"))
    except json.JSONDecodeError:
        errors.append(f"ETHUSDT 回傳非 JSON：{price_raw}")

    return {"market_snapshot": market_snapshot, "errors": errors}


def _compose_answer(state: ComposeState) -> dict[str, str]:
    """回覆子圖：只讀 snapshot/errors，組合最終回覆。"""
    snapshot = state["market_snapshot"]
    lines = [f"意圖：{state['intent']}", f"問題：{state['question']}", "市場摘要："]
    if snapshot:
        if "usd_thb" in snapshot:
            lines.append(
                f"- USD/THB={snapshot['usd_thb']}（date={snapshot.get('fx_date', 'unknown')}）"
            )
        if "eth_usdt" in snapshot:
            lines.append(
                f"- ETHUSDT={snapshot['eth_usdt']}（source={snapshot.get('eth_source', 'unknown')}）"
            )
    else:
        lines.append("- 無可用市場資料")

    if state["errors"]:
        lines.append("錯誤摘要：")
        for err in state["errors"]:
            lines.append(f"- {err}")

    lines.append("結論：以上為即時查詢結果（示範 I1 子圖拆分）。")
    return {"final_response": "\n".join(lines)}


def build_research_subgraph():
    g = StateGraph(ResearchState)
    g.add_node("fetch_market", _research_fetch_market)
    g.add_edge(START, "fetch_market")
    g.add_edge("fetch_market", END)
    return g.compile()


def build_compose_subgraph():
    g = StateGraph(ComposeState)
    g.add_node("compose", _compose_answer)
    g.add_edge(START, "compose")
    g.add_edge("compose", END)
    return g.compile()


def build_i1_outer_graph():
    """外層圖：依序呼叫研究子圖與回覆子圖。"""
    research_graph = build_research_subgraph()
    compose_graph = build_compose_subgraph()

    g = StateGraph(I1State)
    g.add_node("research", research_graph)
    g.add_node("compose", compose_graph)
    g.add_edge(START, "research")
    g.add_edge("research", "compose")
    g.add_edge("compose", END)
    return g.compile()
