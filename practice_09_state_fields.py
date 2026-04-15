"""H2/H3：reducer 與訊息裁剪 最小可跑範例（離線）。

示範：
- 列表：`Annotated[..., operator.add]` — 多次 partial update 會串接，不會被後一次整段覆寫。
- 字典：`Annotated[..., merge_pending_tool_args]` — 自訂合併（淺合併），避免後一次只帶部分鍵時抹掉前一次。
- 訊息裁剪（H3）：只保留最近 N 則訊息（可選保留 system），控制 token 與成本。

執行（專案根目錄）::

    py -3.11 practice_09_state_fields.py
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph


def merge_pending_tool_args(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
) -> dict[str, Any]:
    """淺合併兩次 partial update 的 pending_tool_args（後寫覆蓋同鍵）。"""
    if left is None:
        left = {}
    if right is None:
        right = {}
    # The ** operator is used to unpack a dictionary into key-value pairs
    # Merging two Python dictionaries (dict1, dict2) creates a new dictionary containing keys and values from both.
    # In Python 3.9+, use the union operator merged = dict1 | dict2. 
    # For older versions, use dictionary unpacking merged = {**dict1, **dict2} or dict1.update(dict2)
    # return {**left, **right}
    return left | right


def trim_messages(
    messages: list[object],
    *,
    keep_last: int,
    keep_system: bool = True,
) -> list[object]:
    """H3：只保留最近 N 則（可選保留第一則 system）。"""
    if keep_last <= 0:
        base: list[object] = []
    else:
        base = messages[-keep_last:]

    if keep_system and messages and isinstance(messages[0], SystemMessage):
        sys_msg = messages[0]
        if base and base[0] is sys_msg:
            return base
        return [sys_msg, *base]
    return base


class H2DemoState(TypedDict):
    """僅用於本練習；主代理圖見 agent_graph.AgentState。"""

    audit_events: Annotated[list[dict[str, Any]], operator.add]
    pending_tool_args: Annotated[dict[str, Any], merge_pending_tool_args]


def node_emit_a(state: H2DemoState) -> dict[str, Any]:
    return {
        "audit_events": [{"step": "a", "detail": "first partial"}],
        "pending_tool_args": {"tool_name": "search", "locale": "zh-TW"},
    }


def node_emit_b(state: H2DemoState) -> dict[str, Any]:
    return {
        "audit_events": [{"step": "b", "detail": "second partial"}],
        # 只補一個鍵，若無 reducer 則整欄可能被替換；有 merge 則與前一步合併
        "pending_tool_args": {"query": "weather"},
    }


def build_h2_demo_graph():
    g = StateGraph(H2DemoState)
    g.add_node("emit_a", node_emit_a)
    g.add_node("emit_b", node_emit_b)
    g.add_edge(START, "emit_a")
    g.add_edge("emit_a", "emit_b")
    g.add_edge("emit_b", END)
    return g.compile()


def run_h3_demo() -> None:
    msgs: list[object] = [
        SystemMessage(content="你是個簡潔的助理。"),
        HumanMessage(content="m1"),
        HumanMessage(content="m2"),
        HumanMessage(content="m3"),
        HumanMessage(content="m4"),
    ]
    trimmed = trim_messages(msgs, keep_last=2, keep_system=True)
    assert isinstance(trimmed[0], SystemMessage)
    assert len(trimmed) == 3
    assert isinstance(trimmed[-1], HumanMessage) and trimmed[-1].content == "m4"
    assert isinstance(trimmed[-2], HumanMessage) and trimmed[-2].content == "m3"

    trimmed2 = trim_messages(msgs, keep_last=2, keep_system=False)
    assert len(trimmed2) == 2
    assert isinstance(trimmed2[0], HumanMessage) and trimmed2[0].content == "m3"
    assert isinstance(trimmed2[1], HumanMessage) and trimmed2[1].content == "m4"

    print("\n=== H3 訊息裁剪示範 ===")
    print(f"原始 messages={len(msgs)}；keep_last=2, keep_system=True → {len(trimmed)}")
    print("保留內容：", [type(m).__name__ for m in trimmed])
    print("斷言通過：system（可選）+ 最近 N 則保留。")


def main() -> None:
    graph = build_h2_demo_graph()
    out = graph.invoke(
        {"audit_events": [], "pending_tool_args": {}},
        config={"recursion_limit": 10},
    )
    print("=== H2 reducer 示範（序列兩節點各回傳 partial）===")
    print("audit_events（operator.add 串接）:")
    for ev in out["audit_events"]:
        print(f"  {ev}")
    print("pending_tool_args（merge_pending_tool_args 淺合併）:")
    for k, v in sorted(out["pending_tool_args"].items()):
        print(f"  {k}: {v!r}")
    assert len(out["audit_events"]) == 2
    assert out["pending_tool_args"]["tool_name"] == "search"
    assert out["pending_tool_args"]["query"] == "weather"
    print("\n斷言通過：列表已串接、字典已合併。")
    run_h3_demo()


if __name__ == "__main__":
    main()
