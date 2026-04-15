"""
階段 F1～F2：在 `run_tools` 前中斷，並以 `invoke(None)` 或 `Command` 恢復。

- **F1**：`interrupt_before=['run_tools']` + checkpointer；模型若請求工具，圖在進入 `ToolNode` 前暫停。
- **F2**：從外部恢復執行：
  - **核准**：官方對「靜態斷點」建議用 **`invoke(None, config)`** 繼續（等同放行下一節點）。
  - **拒絕**：以 **`Command(update=..., goto=END)`** 改寫最後一則 `AIMessage`（移除 `tool_calls`）並直接結束，不呼叫外部 API。
  - **改參**：以 **`Command(update=...)`** 替換 `AIMessage` 的 `tool_calls`（示範改 `symbol`），再 **`invoke(None)`** 讓工具用新參數執行。

節點內 `interrupt()` 的配對則是 **`Command(resume=...)`**（本腳本未使用；見官方文件）。

`--f1-only` 僅示範 F1，不進行第二段恢復（省一次模型／工具呼叫）。

執行後會在 `data/langgraph_hitl.sqlite` 建立或更新 SQLite 檔。

官方參考：[Human-in-the-loop](https://docs.langchain.com/oss/python/langgraph/interrupts)
"""

from __future__ import annotations

import argparse
import copy
import sys
import uuid
from datetime import datetime, timezone
from typing import Literal

import path_setup

path_setup.add_src_to_path()

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.messages.modifier import RemoveMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END
from langgraph.types import Command

from langgraph_learning.agent_logging import configure_agent_logging, get_agent_logger
from langgraph_learning.graphs.agent_graph import (
    DEFAULT_RECURSION_LIMIT,
    build_agent_graph,
    _text_from_ai_message,
)

load_dotenv()
configure_agent_logging()
_logger = get_agent_logger("practice_07_interrupt")

_HITL_DB = Path(__file__).resolve().parent / "data" / "langgraph_hitl.sqlite"

ResumeMode = Literal["approve", "reject", "edit"]


def _has_tool_messages(messages: list) -> bool:
    return any(isinstance(m, ToolMessage) for m in messages)


def _last_ai(messages: list) -> AIMessage:
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            return m
    raise ValueError("找不到 AIMessage")


def _build_approval_record(*, decision: str, actor: str, note: str) -> dict[str, str]:
    return {
        "decision": decision,
        "actor": actor,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "note": note,
    }


def _append_approval_record(app, config: dict, record: dict[str, str]) -> None:
    app.invoke(Command(update={"approval_logs": [record]}), config)


def _print_f1_banner(
    *,
    hitl_db: Path,
    thread_id: str,
    messages: list,
    snap_next: tuple[str, ...] | None,
) -> None:
    print("— F1：interrupt 在 run_tools 之前 —")
    print(f"  SQLite：{hitl_db}")
    print(f"  thread_id：{thread_id}")
    print(f"  invoke 回傳的訊息則數：{len(messages)}")
    print(f"  get_state().next：{snap_next!r}")
    print()

    last = _last_ai(messages)
    if last.tool_calls:
        names = [c["name"] for c in last.tool_calls]
        print(f"  最後一則為 AIMessage，已請求工具：{names}")
        print("  （此時圖已暫停，工具尚未執行。）")
    else:
        print("  注意：模型未發出 tool_calls，請改提示或重跑。")

    if _has_tool_messages(messages):
        print("  警告：已出現 ToolMessage，代表工具可能已執行，請檢查 interrupt_before。")
    else:
        print("  F1 OK：尚無 ToolMessage，高風險工具未在未核准情況下執行。")

    print()
    print("  自我檢查：next 應為 ('run_tools',)，表示下一個待跑節點為 run_tools。")
    print()


def _f2_approve(app, config: dict) -> dict:
    """官方：靜態斷點恢復使用 `invoke(None)`。"""
    return app.invoke(None, config)


def _f2_reject(app, config: dict, last_ai: AIMessage) -> dict:
    """以 `Command(update, goto=END)` 撤銷工具請求並結束圖。"""
    if not last_ai.id:
        raise ValueError(
            "最後一則 AIMessage 缺少 id，無法使用 RemoveMessage；請改用支援 message id 的模型。"
        )
    rid = last_ai.id
    replacement = AIMessage(
        content="（使用者已拒絕執行工具，未呼叫任何外部 API。）",
        tool_calls=[],
        id=rid,
    )
    return app.invoke(
        Command(
            update={"messages": [RemoveMessage(id=rid), replacement]},
            goto=END,
        ),
        config,
    )


def _f2_edit_symbol(app, config: dict, last_ai: AIMessage, new_symbol: str) -> dict:
    """改寫 tool_calls 參數後，以 `invoke(None)` 讓 `run_tools` 執行。"""
    if not last_ai.tool_calls:
        raise ValueError("沒有 tool_calls 可修改。")
    if not last_ai.id:
        raise ValueError("最後一則 AIMessage 缺少 id，無法穩定替換。")

    rid = last_ai.id
    new_calls = copy.deepcopy(last_ai.tool_calls)
    for c in new_calls:
        if c.get("name") == "get_eth_usdt_price_binance":
            args = dict(c.get("args") or {})
            args["symbol"] = new_symbol
            c["args"] = args

    replacement = AIMessage(
        content=last_ai.content,
        tool_calls=new_calls,
        id=rid,
    )
    app.invoke(
        Command(update={"messages": [RemoveMessage(id=rid), replacement]}),
        config,
    )
    return app.invoke(None, config)


def _print_f2_result(title: str, result: dict) -> None:
    print(f"— F2：{title} —")
    msgs = result["messages"]
    print(f"  訊息總則數：{len(msgs)}")
    print(f"  訊息類型序列：{[type(m).__name__ for m in msgs]}")
    last = msgs[-1]
    if isinstance(last, AIMessage):
        print("  最後一則 AI 預覽：", _text_from_ai_message(last)[:200])
    logs = result.get("approval_logs", [])
    if logs:
        print("  最新審批紀錄：", logs[-1])
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="F1–F2 HITL interrupt 練習")
    parser.add_argument(
        "--resume",
        choices=("approve", "reject", "edit"),
        default="approve",
        help="F2：核准執行工具／拒絕並結束／改查 BTCUSDT 再執行",
    )
    parser.add_argument(
        "--f1-only",
        action="store_true",
        help="只做 F1（停在 run_tools 前），不進行 F2 恢復",
    )
    args = parser.parse_args()

    _HITL_DB.parent.mkdir(parents=True, exist_ok=True)
    thread_id = f"practice_07_{uuid.uuid4().hex[:12]}"
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": DEFAULT_RECURSION_LIMIT,
    }

    with SqliteSaver.from_conn_string(str(_HITL_DB)) as checkpointer:
        app = build_agent_graph(
            checkpointer=checkpointer,
            interrupt_before=["run_tools"],
        )
        _logger.info(
            "F1: interrupt_before=['run_tools']；thread_id=%s；db=%s",
            thread_id,
            _HITL_DB,
        )

        result = app.invoke(
            {
                "messages": [
                    HumanMessage(
                        content=(
                            "請用工具查詢 ETH 對 USDT 的現貨價格，只要簡短數字與單位說明。"
                        )
                    )
                ]
            },
            config=config,
        )

        messages = result["messages"]
        snap = app.get_state(config)

        _print_f1_banner(
            hitl_db=_HITL_DB,
            thread_id=thread_id,
            messages=messages,
            snap_next=snap.next,
        )

        if args.f1_only:
            preview = _text_from_ai_message(_last_ai(messages))
            if preview:
                print("  最後一則 AI 文字預覽：", preview[:200])
            print("（已使用 --f1-only，略過 F2。）")
            return

        last_ai = _last_ai(messages)
        resume: ResumeMode = args.resume

        actor = "reviewer_demo"
        if resume == "approve":
            _append_approval_record(
                app,
                config,
                _build_approval_record(
                    decision="approved",
                    actor=actor,
                    note="核准工具呼叫，照原參數執行。",
                ),
            )
            _logger.info("F2: invoke(None) 核准，繼續 run_tools")
            final = _f2_approve(app, config)
            _print_f2_result("核准（invoke None）", final)
        elif resume == "reject":
            _append_approval_record(
                app,
                config,
                _build_approval_record(
                    decision="rejected",
                    actor=actor,
                    note="拒絕工具呼叫，直接結束流程。",
                ),
            )
            _logger.info("F2: Command(update, goto=END) 拒絕")
            final = _f2_reject(app, config, last_ai)
            _print_f2_result("拒絕（Command update + goto END）", final)
        else:
            _append_approval_record(
                app,
                config,
                _build_approval_record(
                    decision="edited_then_approved",
                    actor=actor,
                    note="人工改寫 symbol 後核准執行。",
                ),
            )
            _logger.info("F2: 改為 BTCUSDT 後 invoke(None)")
            final = _f2_edit_symbol(app, config, last_ai, "BTCUSDT")
            _print_f2_result("改參後核准（Command update + invoke None）", final)

    print("F2/F3 說明：")
    print("  - 靜態 interrupt_before 與節點內 interrupt() 不同；恢復「放行」請優先參考官方 `invoke(None)`。")
    print("  - 改寫 state 的 `Command(update=...)` 可作為「拒絕／改參」的輸入（見本腳本）。")
    print("  - 節點內 `interrupt()` 的配對則為 `Command(resume=...)`（本腳本未示範）。")
    print("  - F3：每次決策都會追加一筆 approval_logs（decision / actor / approved_at / note）。")


if __name__ == "__main__":
    main()
