"""
階段 E1～E3：SqliteSaver、同 thread 多輪 invoke、checkpoint 歷史與 time travel 概念。

- **E1**：`compile(checkpointer=SqliteSaver(...))`。
- **E2**：同一 `thread_id`，第二輪只傳新 `HumanMessage`，`add_messages` 合併。
- **E3**：`get_state_history` 列出檢查點；`get_state(checkpoint_id)` 驗證；
  選用 **`--replay`** 示範官方 **Replay**（`invoke(None, config)`，會再呼叫一次模型）。

執行後會在專案根目錄 `data/langgraph_checkpoints.sqlite` 建立或更新 SQLite 檔。

官方參考：[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、
[Time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)。
"""

from __future__ import annotations

import argparse
import sys

import path_setup

path_setup.add_src_to_path()

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from langgraph_learning.agent_logging import configure_agent_logging, get_agent_logger
from langgraph_learning.graphs.agent_graph import (
    DEFAULT_RECURSION_LIMIT,
    build_agent_graph,
    _text_from_ai_message,
)

load_dotenv()
configure_agent_logging()
_logger = get_agent_logger("practice_06_checkpoint")

_CHECKPOINT_DB = Path(__file__).resolve().parent / "data" / "langgraph_checkpoints.sqlite"


def _short_checkpoint_id(config: dict) -> str:
    cid = config.get("configurable", {}).get("checkpoint_id") or ""
    return f"{cid[:8]}…" if len(cid) > 8 else cid or "?"


def _print_state_history_summary(history: list) -> None:
    """E3：檢查點由新到舊（官方：get_state_history 第一筆為最近）。"""
    print("— E3：get_state_history（每個 super-step 邊界一筆）—")
    for i, snap in enumerate(history):
        md = snap.metadata or {}
        step = md.get("step", "?")
        source = md.get("source", "?")
        msgs = snap.values.get("messages", []) if isinstance(snap.values, dict) else []
        cid = _short_checkpoint_id(snap.config)
        nxt = snap.next if snap.next else "()"
        print(
            f"  [{i:2d}] step={step!s:>3} source={source!s:8} "
            f"n_msgs={len(msgs):2d} next={nxt!s} checkpoint_id={cid}"
        )


def _e3_verify_get_state(app, config: dict, history: list) -> None:
    """用同一個 checkpoint_id 再查一次 get_state，應與該筆 StateSnapshot 一致。"""
    if not history:
        return
    latest = history[0]
    cid = latest.config.get("configurable", {}).get("checkpoint_id")
    if not cid:
        return
    cfg_with_id = {
        "configurable": {
            **config["configurable"],
            "checkpoint_id": cid,
        },
        "recursion_limit": config.get("recursion_limit", DEFAULT_RECURSION_LIMIT),
    }
    again = app.get_state(cfg_with_id)
    n0 = len(latest.values.get("messages", [])) if isinstance(latest.values, dict) else 0
    n1 = len(again.values.get("messages", [])) if isinstance(again.values, dict) else 0
    if n0 == n1:
        print(
            f"E3：get_state(thread_id + checkpoint_id) 與歷史最新一筆訊息則數一致（{n0}）。"
        )
    else:
        print(f"警告：get_state 與 history[0] 訊息則數不一致：{n0} vs {n1}")


def _e3_optional_replay(app, history: list) -> None:
    """Replay：在「即將執行 call_model、且已有 3 則訊息」的檢查點重播（會再跑一次模型）。"""
    target = next(
        (
            s
            for s in history
            if s.next == ("call_model",)
            and isinstance(s.values, dict)
            and len(s.values.get("messages", [])) == 3
        ),
        None,
    )
    if target is None:
        print("E3 --replay：找不到 next==('call_model',) 且 n_msgs==3 的檢查點，略過。")
        return
    print(
        "— E3（選用）Replay：invoke(None, checkpoint) 將重新執行 call_model —"
    )
    result = app.invoke(None, target.config)
    last = result["messages"][-1]
    assert isinstance(last, AIMessage)
    print("  重播後最後一則 AI：", _text_from_ai_message(last)[:200])


def main() -> None:
    parser = argparse.ArgumentParser(description="E1–E3 checkpoint 練習")
    parser.add_argument(
        "--replay",
        action="store_true",
        help="E3 選用：示範 Replay（會多一次模型呼叫，可能消耗配額）",
    )
    args = parser.parse_args()

    _CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)

    thread_id = "practice_06_e3-02"
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": DEFAULT_RECURSION_LIMIT,
    }

    with SqliteSaver.from_conn_string(str(_CHECKPOINT_DB)) as checkpointer:
        app = build_agent_graph(checkpointer=checkpointer)

        _logger.info(
            "E1/E2/E3: SqliteSaver；thread_id=%s；db=%s",
            thread_id,
            _CHECKPOINT_DB,
        )

        result1 = app.invoke(
            {
                "messages": [
                    HumanMessage(
                        content=(
                            "請只回覆「收到」。接下來請記住：我的今日代號是 **Gamma-42**。"
                        )
                    )
                ]
            },
            config=config,
        )
        n1 = len(result1["messages"])
        last1 = result1["messages"][-1]
        assert isinstance(last1, AIMessage)

        print("— 第一輪 invoke 結束 —")
        print(f"  訊息總則數：{n1}")
        print("  最後一則 AI：", _text_from_ai_message(last1)[:200])
        print()

        result2 = app.invoke(
            {
                "messages": [
                    HumanMessage(
                        content="我剛請你記住的今日代號是什麼？只回答代號本身，不要其他說明。"
                    )
                ]
            },
            config=config,
        )
        n2 = len(result2["messages"])
        last2 = result2["messages"][-1]
        assert isinstance(last2, AIMessage)

        print("— 第二輪 invoke 結束（應載入上一輪 checkpoint）—")
        print(f"  訊息總則數：{n2}（應大於第一輪的 {n1}）")
        print(f"  SQLite：{_CHECKPOINT_DB}")
        print(f"  thread_id：{thread_id}")
        print("  最後一則 AI：", _text_from_ai_message(last2))
        if n2 <= n1:
            print(
                "  警告：訊息則數未增加，請檢查 thread_id 與 checkpointer。"
            )
        else:
            print("  E2 OK：訊息歷史已累加。")
        print()

        # ---------- E3（須在 same checkpointer / app 內）----------
        history = list(app.get_state_history(config))
        _print_state_history_summary(history)
        print()
        _e3_verify_get_state(app, config, history)
        print()

        if args.replay:
            _e3_optional_replay(app, history)

    print()
    print(
        "E3 OK：已列出 get_state_history，並以 get_state(checkpoint_id) 對照最新檢查點。"
    )
    if not args.replay:
        print(
            "     若要試官方 Replay，可執行：py -3.11 practice_06_checkpoint_memory.py --replay"
        )


if __name__ == "__main__":
    main()
