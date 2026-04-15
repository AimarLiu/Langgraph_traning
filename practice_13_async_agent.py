"""
第三課表 K1：一輪對話改為 `await graph.ainvoke(...)`，並與同步 `invoke` 對照。

- 圖：`build_agent_graph()`（`src/langgraph_learning/graphs/agent_graph.py`）
- K2：市場工具已具 **async** 實作（httpx AsyncClient），`ainvoke` 時工具節點走非同步 I/O；見 `tools/market.py`。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import path_setup

path_setup.add_src_to_path()

from langchain_core.messages import AIMessage, HumanMessage

from langgraph_learning.graphs.agent_graph import DEFAULT_RECURSION_LIMIT, build_agent_graph

# 與 `agent_graph.main()` 相同任務，便於對照同步／非同步路徑行為
_USER_PROMPT = (
    "請透過 Binance 查詢 ETH 對 USDT 的現價，並用繁體中文簡短說明。"
)


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


def _assert_final_ai(msgs: list[Any], label: str) -> AIMessage:
    last = msgs[-1]
    assert isinstance(last, AIMessage), f"{label}: 最後一則應為 AIMessage"
    assert not last.tool_calls, f"{label}: 完成時最後一則 AI 不應再帶 tool_calls"
    return last


async def demo_concurrent_ainvoke(app: Any) -> None:
    """可選示範：用 asyncio.gather 同時排程兩個 ainvoke，並對照連續兩次 await。

    預期：若節點內多為同步 I/O（例如同步 LLM invoke），牆鐘時間未必明顯縮短；
    在 API 服務中仍值得用 async 圖，讓事件迴圈能穿插處理其他 coroutine。
    """
    cfg = {"recursion_limit": DEFAULT_RECURSION_LIMIT}
    # 輕量提示，降低取消註解時的花費（仍會呼叫模型）
    seq_a = {"messages": [HumanMessage(content="只回覆一個字：甲，不要說明。")]}
    seq_b = {"messages": [HumanMessage(content="只回覆一個字：乙，不要說明。")]}
    par_a = {"messages": [HumanMessage(content="只回覆一個字：丙，不要說明。")]}
    par_b = {"messages": [HumanMessage(content="只回覆一個字：丁，不要說明。")]}

    t0 = time.perf_counter()
    await app.ainvoke(seq_a, config=cfg)
    await app.ainvoke(seq_b, config=cfg)
    t_sequential = time.perf_counter() - t0

    t0 = time.perf_counter()
    await asyncio.gather(
        app.ainvoke(par_a, config=cfg),
        app.ainvoke(par_b, config=cfg),
    )
    t_gather = time.perf_counter() - t0

    print("\n--- 可選示範：連續兩次 ainvoke vs asyncio.gather（兩輪並發）---")
    print(f"連續 await 牆鐘：{t_sequential:.2f}s")
    print(f"gather 牆鐘：  {t_gather:.2f}s")
    print(
        "（若兩者接近，多半表示圖內仍以同步呼叫為主；並發效益在「多請求共用事件迴圈」時較明顯。）"
    )


async def main() -> None:
    app = build_agent_graph()
    state = {
        "messages": [HumanMessage(content=_USER_PROMPT)],
    }
    config = {"recursion_limit": DEFAULT_RECURSION_LIMIT}

    sync_out = app.invoke(state, config=config)
    sync_msgs = sync_out["messages"]
    sync_last = _assert_final_ai(sync_msgs, "invoke")

    async_out = await app.ainvoke(state, config=config)
    async_msgs = async_out["messages"]
    async_last = _assert_final_ai(async_msgs, "ainvoke")

    # 結構對齊：訊息則數應相同（同一輸入、無 checkpoint 下兩次獨立執行）
    if len(sync_msgs) != len(async_msgs):
        print(
            "注意：invoke 與 ainvoke 的訊息則數不同（模型／工具路徑可能非完全確定性）："
            f" invoke={len(sync_msgs)} ainvoke={len(async_msgs)}"
        )
    else:
        print(f"K1 OK：invoke / ainvoke 訊息則數一致（{len(sync_msgs)}）。")

    print("\n--- invoke 最後一則 AI ---")
    print(_text_from_ai_message(sync_last))
    print("\n--- ainvoke 最後一則 AI ---")
    print(_text_from_ai_message(async_last))

    # 可選示範：取消下一行註解會再跑 4 次模型路徑（約兩倍於「兩輪並發」的費用意識請自行斟酌）
    # await demo_concurrent_ainvoke(app)


if __name__ == "__main__":
    asyncio.run(main())
