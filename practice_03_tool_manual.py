"""
practice_03：手動一輪「模型 → tool_calls → 執行工具 → ToolMessage → 模型再答」

對應 TODO 階段 A2–A3；**工具實作**已集中於 `src/langgraph_learning/tools/market.py`（C2）。
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import path_setup

path_setup.add_src_to_path()

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from langgraph_learning.tools import DEFAULT_MARKET_TOOLS

load_dotenv()

_api_key = os.getenv("GOOGLE_API_KEY")
if not _api_key:
    raise SystemExit("缺少環境變數 GOOGLE_API_KEY（請在 .env 設定）")

_MODEL = "gemini-3-flash-preview"


def _text_from_ai_message(msg: AIMessage) -> str:
    c: Any = msg.content
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts: list[str] = []
        for block in c:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts) if parts else str(c)
    return str(c)


def main() -> None:
    llm = ChatGoogleGenerativeAI(model=_MODEL, api_key=_api_key)
    tools = list(DEFAULT_MARKET_TOOLS)
    llm_with_tools = llm.bind_tools(tools)

    messages: list[Any] = [
        HumanMessage(
            content="請透過 Binance 查詢 ETH 對 USDT 的現價，並用繁體中文簡短說明。"
        )
    ]

    ai = llm_with_tools.invoke(messages)
    assert isinstance(ai, AIMessage)
    messages.append(ai)

    if not ai.tool_calls:
        print("(模型未呼叫工具，直接回答)")
        print(_text_from_ai_message(ai))
        return

    name_to_tool = {t.name: t for t in tools}
    for call in ai.tool_calls:
        name = call["name"]
        tid = call["id"]
        args = call.get("args") or {}
        tool_fn = name_to_tool.get(name)
        if tool_fn is None:
            out = json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
        else:
            out = tool_fn.invoke(args)
        messages.append(ToolMessage(content=out, tool_call_id=tid))

    ai2 = llm_with_tools.invoke(messages)
    assert isinstance(ai2, AIMessage)
    print(_text_from_ai_message(ai2))


if __name__ == "__main__":
    main()
