"""J2／J3：RAG 檢索工具 + 代理（Chroma similarity_search；系統提示驅動依據標示）。"""

from __future__ import annotations

import os
import sys

import path_setup

path_setup.add_src_to_path()

from dotenv import load_dotenv

load_dotenv()

# RAG 需要保留 Human / AI / Tool 多輪內容；若 trim 過短會看不到檢索結果
try:
    _cur = int((os.getenv("MODEL_MAX_TOKENS") or "0").strip() or "0")
except ValueError:
    _cur = 0
if _cur < 2048:
    os.environ["MODEL_MAX_TOKENS"] = "12000"

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from langgraph_learning.graphs.agent_graph import (
    DEFAULT_RECURSION_LIMIT,
    build_agent_graph,
    _text_from_ai_message,
)
from langgraph_learning.tools import (
    DEFAULT_MARKET_TOOLS,
    LILIAN_RAG_SYSTEM_PROMPT,
    search_lilian_weng_knowledge,
)


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    tools = [*DEFAULT_MARKET_TOOLS, search_lilian_weng_knowledge]
    app = build_agent_graph(tools=tools)

    # J3：依賴 LILIAN_RAG_SYSTEM_PROMPT 約束「何時檢索」與「依據」格式；使用者問題不必再重複長指令。
    question = (
        "請用繁體中文簡要說明：什麼是 reinforcement learning 裡的 reward hacking？"
    )

    result = app.invoke(
        {
            "messages": [
                SystemMessage(content=LILIAN_RAG_SYSTEM_PROMPT),
                HumanMessage(content=question),
            ]
        },
        config={"recursion_limit": DEFAULT_RECURSION_LIMIT},
    )
    last = result["messages"][-1]
    assert isinstance(last, AIMessage)
    print("=== J2／J3 RAG 代理 ===\n")
    print(_text_from_ai_message(last))
    print(
        "\nJ3 OK：系統提示引導內部知識問題先檢索；"
        "最終回答應含「依據」與 [n]/title/slug/source（無則應表明文件未載明）。"
    )


if __name__ == "__main__":
    main()
