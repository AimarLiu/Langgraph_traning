"""I2：意圖分類（LLM structured output）+ 條件路由（閒聊／查價／申訴）。"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Literal, NotRequired, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from langgraph_learning.pipelines.i1_subgraphs import (
    build_compose_subgraph,
    build_research_subgraph,
)
from langgraph_learning.pipelines.i2_branches.chat_reply import build_chat_response
from langgraph_learning.pipelines.i2_branches.complaint_reply import (
    build_complaint_response,
)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

IntentLabel = Literal["chat", "price", "complaint"]


class IntentClassification(BaseModel):
    """分類器輸出：供 `with_structured_output` 綁定。"""

    intent: IntentLabel = Field(
        description=(
            "chat：閒聊、打招呼、與價格／申訴無關的一般對話；"
            "price：查價、匯率、加密貨幣或商品價格等；"
            "complaint：申訴、投訴、客訴、退費爭議、服務不滿等。"
        )
    )
    brief_reason: str = Field(description="繁體中文，一句話說明為何歸此類。")


_CLASSIFIER_SYSTEM = """你是客服對話的「意圖分類器」，只輸出結構化欄位，不要與使用者聊天。
規則：
- chat：純閒聊、問候、閒話、與價格數字／匯率／申訴無關的內容。
- price：詢問價格、匯率、幣價、多少錢、USD/THB、ETH 等市場數字相關。
- complaint：表達不滿、要申訴／投訴／客訴、退費、服務品質問題等。
若同時出現多種信號，申訴優先於查價，查價優先於閒聊。"""

#它可以自動記住函數的調用結果，當傳入相同參數時，直接返回快取結果，而不需要再次計算。
@lru_cache(maxsize=1)
def _structured_intent_runnable():
    """建立並快取 `ChatGoogleGenerativeAI.with_structured_output(IntentClassification)`。"""
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit("缺少環境變數 GOOGLE_API_KEY（請在 .env 設定）")
    model = os.getenv("I2_INTENT_MODEL", "gemini-3-flash-preview")
    llm = ChatGoogleGenerativeAI(model=model, api_key=api_key)
    # Bind the schema and activate structured output
    return llm.with_structured_output(IntentClassification)


def classify_intent_structured(user_message: str) -> IntentClassification:
    """單獨呼叫分類模型（方便腳本預覽 structured output，不必跑完整圖）。"""
    structured = _structured_intent_runnable()
    text = (user_message or "").strip() or "（空白）"
    out = structured.invoke(
        [
            SystemMessage(content=_CLASSIFIER_SYSTEM),
            HumanMessage(content=text),
        ]
    )
    if not isinstance(out, IntentClassification):
        raise TypeError(f"預期 IntentClassification，得到 {type(out)}")
    return out


class I2GraphState(TypedDict):
    """與 I1 子圖對齊的欄位 + 使用者原文，供條件路由與查價鏈共用。"""

    user_message: str
    intent: NotRequired[str]
    intent_reason: NotRequired[str]
    question: NotRequired[str]
    market_snapshot: NotRequired[dict[str, str]]
    final_response: NotRequired[str]
    errors: NotRequired[list[str]]


def _node_classify(state: I2GraphState) -> dict[str, str]:
    parsed = classify_intent_structured(str(state.get("user_message", "")))
    return {"intent": parsed.intent, "intent_reason": parsed.brief_reason}


def _node_chat(state: I2GraphState) -> dict[str, str]:
    reply = build_chat_response(str(state.get("user_message", "")))
    return {"final_response": reply}


def _node_complaint(state: I2GraphState) -> dict[str, str]:
    reply = build_complaint_response(str(state.get("user_message", "")))
    return {"final_response": reply}


def _node_prepare_price(state: I2GraphState) -> dict:
    """對齊 I1 研究子圖所需欄位。"""
    return {
        "question": str(state.get("user_message", "")).strip() or "（無具體問題）",
        "intent": "price_lookup",
        "market_snapshot": {},
        "errors": list(state.get("errors", [])),
    }


def _route_after_classify(state: I2GraphState) -> str:
    intent = str(state.get("intent", "chat"))
    if intent == "price":
        return "prepare_price"
    if intent == "complaint":
        return "complaint_reply"
    return "chat_reply"


def build_i2_intent_router_graph():
    """外層圖：分類後條件路由；查價鏈重用 I1 研究 + 回覆子圖。"""
    research = build_research_subgraph()
    compose = build_compose_subgraph()

    g = StateGraph(I2GraphState)
    g.add_node("classify", _node_classify)
    g.add_node("chat_reply", _node_chat)
    g.add_node("complaint_reply", _node_complaint)
    g.add_node("prepare_price", _node_prepare_price)
    g.add_node("research", research)
    g.add_node("compose", compose)

    g.add_edge(START, "classify")
    g.add_conditional_edges(
        "classify",
        _route_after_classify,
        {
            "chat_reply": "chat_reply",
            "complaint_reply": "complaint_reply",
            "prepare_price": "prepare_price",
        },
    )
    g.add_edge("chat_reply", END)
    g.add_edge("complaint_reply", END)
    g.add_edge("prepare_price", "research")
    g.add_edge("research", "compose")
    g.add_edge("compose", END)

    return g.compile()
