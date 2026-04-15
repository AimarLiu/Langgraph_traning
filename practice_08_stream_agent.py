"""
階段 G1～G2：LangGraph `stream` 與不同 `stream_mode` 的觀察。

- **G1**：`stream_mode="updates"`，每個 chunk 對應「某節點完成後」的狀態更新（可看節點順序）。
- **G2**：`stream_mode="messages"`（LLM／節點訊息流）與 `stream_mode="custom"`（節點內 `get_stream_writer()`）；
  亦可用 `both` 同時訂閱 `updates` + `messages`。

`custom` 模式預設圖不會發事件；本腳本在 `--mode custom` 時會暫時包裝 `call_model`，
於進入模型前寫入一筆示範自訂事件（僅教學用）。
"""

from __future__ import annotations

import argparse
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
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage

from langgraph_learning.agent_logging import configure_agent_logging, get_agent_logger
from langgraph_learning.graphs.agent_graph import (
    DEFAULT_RECURSION_LIMIT,
    AgentState,
    _text_from_ai_message,
    build_agent_graph,
    call_model as _call_model_orig,
)
from langgraph_learning.graphs import agent_graph as _agent_graph_mod

load_dotenv()
configure_agent_logging()
_logger = get_agent_logger("practice_08_stream")


def _new_stream_state() -> dict[str, Any]:
    """追蹤 messages 串流：依 id 累加 AIMessageChunk，並記錄節點回傳的完整 AIMessage。"""
    return {"chunk_acc": {}, "last_ai_msg": None}


def _summarize_updates(node_updates: dict[str, Any]) -> str:
    parts: list[str] = []
    messages = node_updates.get("messages")
    if isinstance(messages, list):
        parts.append(f"messages_delta={len(messages)}")
        if messages and isinstance(messages[-1], AIMessage):
            ai = messages[-1]
            if ai.tool_calls:
                names = [c.get("name", "?") for c in ai.tool_calls]
                parts.append(f"tool_calls={names}")
            else:
                parts.append("tool_calls=[]")
    logs = node_updates.get("approval_logs")
    if isinstance(logs, list):
        parts.append(f"approval_logs_delta={len(logs)}")
    return ", ".join(parts) if parts else "（無可辨識欄位更新）"


def _preview_message(msg: BaseMessage) -> str:
    typ = type(msg).__name__
    c = getattr(msg, "content", None)
    if isinstance(c, str):
        snippet = c.replace("\n", " ")[:80]
        return f"{typ} content={snippet!r}"
    if isinstance(c, list):
        return f"{typ} content=<{len(c)} blocks>"
    return f"{typ} content={c!r}"


def _print_updates_chunk(i: int, chunk: dict[str, Any], stream_state: dict[str, Any]) -> None:
    for node_name, node_updates in chunk.items():
        if isinstance(node_updates, dict):
            summary = _summarize_updates(node_updates)
            _logger.debug("[%03d] updates | node=%-12s | %s", i, node_name, summary)
            msgs = node_updates.get("messages")
            if isinstance(msgs, list) and msgs:
                last = msgs[-1]
                # 節點寫回 state 的通常是完整 AIMessage，不是串流 Chunk
                if isinstance(last, AIMessage) and not isinstance(last, AIMessageChunk):
                    stream_state["last_ai_msg"] = last
        else:
            _logger.debug(
                "[%03d] updates | node=%-12s | type=%s",
                i,
                node_name,
                type(node_updates).__name__,
            )


def _print_messages_chunk(i: int, chunk: Any, stream_state: dict[str, Any]) -> None:
    # 單一 mode="messages" 時，chunk 通常為 (message, metadata)
    if isinstance(chunk, tuple) and len(chunk) == 2:
        msg, meta = chunk
        if isinstance(msg, BaseMessage):
            meta_s = meta if isinstance(meta, dict) else {}
            node = meta_s.get("langgraph_node") or meta_s.get("node") or "?"

            if isinstance(msg, AIMessageChunk):
                # AIMessageChunk 需用 + 累加；不可當成完整 AIMessage
                key = msg.id if msg.id else "__noid__"
                acc: dict[str, AIMessageChunk] = stream_state["chunk_acc"]
                acc[key] = msg if key not in acc else acc[key] + msg
                merged = acc[key]
                full_text = _text_from_ai_message(merged)
                tail = full_text[-100:] if len(full_text) > 100 else full_text
                pos = getattr(msg, "chunk_position", None)
                extra = f" chunk_position={pos!r}" if pos else ""
                _logger.debug(
                    "[%03d] messages | node=%-12s | AIMessageChunk id=%r len=%d%s | tail=%r",
                    i,
                    str(node),
                    key,
                    len(full_text),
                    extra,
                    tail,
                )
            elif isinstance(msg, AIMessage):
                stream_state["last_ai_msg"] = msg
                _logger.debug(
                    "[%03d] messages | node=%-12s | AIMessage(final) | %s",
                    i,
                    str(node),
                    _preview_message(msg),
                )
            else:
                _logger.debug(
                    "[%03d] messages | node=%-12s | %s",
                    i,
                    str(node),
                    _preview_message(msg),
                )
        else:
            _logger.debug("[%03d] messages | 非預期 tuple 內容：%s", i, type(msg).__name__)
    else:
        _logger.debug("[%03d] messages | 非預期 chunk 型別：%s", i, type(chunk).__name__)


def _print_custom_chunk(i: int, chunk: Any) -> None:
    _logger.debug("[%03d] custom   | %r", i, chunk)


def _print_both_chunk(
    i: int,
    chunk: tuple[str, Any],
    stream_state: dict[str, Any],
) -> None:
    # stream_mode 為 list 時，yield (mode, payload)
    if not (isinstance(chunk, tuple) and len(chunk) == 2):
        _logger.debug("[%03d] both     | 非預期：%s", i, type(chunk).__name__)
        return
    mode, payload = chunk[0], chunk[1]
    if mode == "updates" and isinstance(payload, dict):
        _print_updates_chunk(i, payload, stream_state)
    elif mode == "messages":
        _print_messages_chunk(i, payload, stream_state)
    elif mode == "custom":
        _print_custom_chunk(i, payload)
    else:
        _logger.debug(
            "[%03d] both     | mode=%r payload_type=%s",
            i,
            mode,
            type(payload).__name__,
        )


def _stream_fluently(chunk: Any, fluency_state: dict[str, Any]) -> None:
    """以終端機增量輸出 AI 串流文字，模擬聊天逐步回覆。"""
    if not (isinstance(chunk, tuple) and len(chunk) == 2):
        return
    msg, _meta = chunk
    if not isinstance(msg, AIMessageChunk):
        return

    key = msg.id or "__noid__"
    acc: dict[str, AIMessageChunk] = fluency_state["chunk_acc"]
    printed_len: dict[str, int] = fluency_state["printed_len"]
    acc[key] = msg if key not in acc else acc[key] + msg

    full_text = _text_from_ai_message(acc[key])
    prev = printed_len.get(key, 0)
    if len(full_text) > prev:
        delta = full_text[prev:]
        # 直接輸出到 stdout，不加換行，營造流暢回覆感
        print(delta, end="", flush=True)
        printed_len[key] = len(full_text)
        fluency_state["active_key"] = key


def _call_model_with_custom_hook(state: AgentState) -> dict[str, Any]:
    try:
        from langgraph.config import get_stream_writer

        w = get_stream_writer()
        w({"g2_demo": "call_model_before_llm", "n_msgs": len(state.get("messages", []))})
    except Exception:
        pass
    return _call_model_orig(state)


def main() -> None:
    parser = argparse.ArgumentParser(description="G1/G2：LangGraph stream 模式練習")
    parser.add_argument(
        "--mode",
        choices=("updates", "messages", "both", "custom", "fluently"),
        default="updates",
        help="G1=updates；G2=messages / both / custom；fluently=即時增量輸出",
    )
    args = parser.parse_args()

    if args.mode == "custom":
        _agent_graph_mod.call_model = _call_model_with_custom_hook

    try:
        app = build_agent_graph()
    finally:
        if args.mode == "custom":
            _agent_graph_mod.call_model = _call_model_orig

    config = {"recursion_limit": DEFAULT_RECURSION_LIMIT}
    inputs: AgentState = {
        "messages": [
            HumanMessage(
                content="請用工具查詢 ETHUSDT 現價，最後用繁體中文一句話回答。"
                #content="你對ZEC大零幣有十麼看法,我覺得它是彼特幣的優化,有可能取代彼特幣嗎?"
            )
        ],
        "approval_logs": [],
        "user_id": "demo_user_001",
        "locale": "zh-TW",
        "pending_tool_args": {},
    }

    if args.mode == "updates":
        stream_mode: Any = "updates"
    elif args.mode == "messages":
        stream_mode = "messages"
    elif args.mode == "both":
        stream_mode = ["updates", "messages"]
    elif args.mode == "fluently":
        stream_mode = "messages"
    else:
        stream_mode = "custom"

    if args.mode != "fluently":
        _logger.debug("— G stream mode=%r —", stream_mode)
        _logger.debug("recursion_limit=%s", DEFAULT_RECURSION_LIMIT)
    if args.mode == "custom":
        _logger.debug("（custom：已用包裝版 call_model 發出一筆示範事件）")
    if args.mode == "fluently":
        print("AI：", end="", flush=True)

    stream_state = _new_stream_state()
    fluency_state: dict[str, Any] = {"chunk_acc": {}, "printed_len": {}, "active_key": None}
    for i, chunk in enumerate(
        app.stream(inputs, config=config, stream_mode=stream_mode),
        1,
    ):
        if args.mode == "updates":
            if isinstance(chunk, dict):
                _print_updates_chunk(i, chunk, stream_state)
            else:
                _logger.debug("[%03d] updates | 非預期 chunk：%s", i, type(chunk).__name__)
        elif args.mode == "messages":
            _print_messages_chunk(i, chunk, stream_state)
        elif args.mode == "both":
            _print_both_chunk(i, chunk, stream_state)
        elif args.mode == "fluently":
            _stream_fluently(chunk, fluency_state)
        else:
            _print_custom_chunk(i, chunk)

    if args.mode == "fluently":
        print()
        return

    final_ai = stream_state["last_ai_msg"]
    if isinstance(final_ai, AIMessage) and not isinstance(final_ai, AIMessageChunk):
        _logger.debug(
            "最後完整 AIMessage（來自節點輸出）：%s",
            _text_from_ai_message(final_ai)[:200],
        )
    elif stream_state["chunk_acc"]:
        best = max(
            stream_state["chunk_acc"].values(),
            key=lambda c: len(_text_from_ai_message(c)),
        )
        _logger.debug(
            "最後合併的 AIMessageChunk（僅串流、無完整 AIMessage 時）：%s",
            _text_from_ai_message(best)[:200],
        )
    else:
        _logger.debug("未取得最後 AI 文字（可能僅有工具訊息，或呼叫失敗）。")


if __name__ == "__main__":
    main()
