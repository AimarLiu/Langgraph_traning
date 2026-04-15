"""
LangGraph 任務代理：call_model + ToolNode + tools_condition。

工具來自 `langgraph_learning.tools`。
"""

from __future__ import annotations

import os
import operator
import sys
from typing import Annotated, Any, NotRequired, Sequence, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    filter_messages,
    trim_messages,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langgraph_learning.agent_logging import configure_agent_logging, get_agent_logger
from langgraph_learning.tools import DEFAULT_MARKET_TOOLS

DEFAULT_RECURSION_LIMIT = 12

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

load_dotenv()
configure_agent_logging()
_logger = get_agent_logger("graphs.agent_graph")

_api_key = os.getenv("GOOGLE_API_KEY")
if not _api_key:
    raise SystemExit("缺少環境變數 GOOGLE_API_KEY（請在 .env 設定）")

_MODEL = "gemini-3-flash-preview"

llm = ChatGoogleGenerativeAI(model=_MODEL, api_key=_api_key)

def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    v = raw.strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    _logger.warning("%s=%r 非合法布林值，改用預設 %s", name, raw, default)
    return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        _logger.warning("%s=%r 非合法整數，改用預設 %s", name, raw, default)
        return default


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    items = tuple(p.strip().lower() for p in raw.split(",") if p.strip())
    return items


def _normalize_exclude_types(items: tuple[str, ...]) -> tuple[str, ...]:
    """將 .env 設定標準化為 filter_messages 可接受的 type 字串。"""
    mapping = {
        "human": "human",
        "humanmessage": "human",
        "ai": "ai",
        "aimessage": "ai",
        "system": "system",
        "systemmessage": "system",
        "tool": "tool",
        "toolmessage": "tool",
    }
    out: list[str] = []
    for item in items:
        key = item.strip().lower()
        if not key:
            continue
        normalized = mapping.get(key, key)
        out.append(normalized)
    return tuple(out)


MAX_MODEL_TOKENS = _env_int("MODEL_MAX_TOKENS", 20)
MODEL_TRIM_STRATEGY = os.getenv("MODEL_TRIM_STRATEGY", "last").strip().lower() or "last"
MODEL_TRIM_INCLUDE_SYSTEM = _env_bool("MODEL_TRIM_INCLUDE_SYSTEM", True)
MODEL_TRIM_START_ON_RAW = os.getenv("MODEL_TRIM_START_ON", "human").strip().lower()
MODEL_TRIM_START_ON: str | None = MODEL_TRIM_START_ON_RAW or None
MODEL_FILTER_EXCLUDE_TYPES = _normalize_exclude_types(
    _env_csv("MODEL_EXCLUDE_TYPES", ())
)

if MODEL_TRIM_STRATEGY not in {"first", "last"}:
    _logger.warning(
        "MODEL_TRIM_STRATEGY=%r 非法，改用 'last'",
        MODEL_TRIM_STRATEGY,
    )
    MODEL_TRIM_STRATEGY = "last"


class AgentState(TypedDict):
    """圖的共享狀態。"""

    messages: Annotated[list[BaseMessage], add_messages]
    approval_logs: Annotated[list[dict[str, str]], operator.add]
    user_id: NotRequired[str]
    locale: NotRequired[str]
    pending_tool_args: NotRequired[dict[str, Any]]


def preprocess_messages_for_model(
    messages: list[BaseMessage],
) -> list[BaseMessage]:
    """H4 pipeline：先 filter，再 trim，控制模型上下文。

    - filter：控制哪些訊息可進模型（預設不排除，避免破壞工具迴圈）。
    - trim：用 token 規則保留最近上下文（預設 `strategy='last'`）。
    - token_counter 目前用 `len` 當教學單位；若要更準可改模型 tokenizer。
    """
    exclude_types = MODEL_FILTER_EXCLUDE_TYPES or None
    filtered = filter_messages(messages, exclude_types=exclude_types)
    trimmed = trim_messages(
        filtered,
        max_tokens=MAX_MODEL_TOKENS,
        token_counter=len,
        strategy=MODEL_TRIM_STRATEGY,
        include_system=MODEL_TRIM_INCLUDE_SYSTEM,
        start_on=MODEL_TRIM_START_ON,
    )
    # The list() constructor takes an iterable as an argument
    return list(trimmed)


def build_agent_graph(
    *,
    checkpointer: BaseCheckpointSaver | None = None,
    interrupt_before: list[str] | None = None,
    interrupt_after: list[str] | None = None,
    tools: Sequence[Any] | None = None,
):
    """編譯代理圖。

    傳入 **checkpointer**（例如 `SqliteSaver`）時，需搭配
    `config["configurable"]["thread_id"]` 使用，狀態會寫入 checkpoint。

    **常駐服務（long-running service，例如 FastAPI）**：checkpointer 與本函式回傳的已編譯圖宜在 **進程生命週期內
    建立一次並重用**，請求內只傳 `config`；勿每請求重新 ``compile``。說明見
    ``Docs/checkpointer_in_services.md``（第三課表 K3）。

    **interrupt_before** / **interrupt_after**：在指定節點名稱的前或後暫停（Human-in-the-loop）。
    例如 ``interrupt_before=['run_tools']`` 可在實際執行工具前中斷，此時 state 內通常已有
    帶 `tool_calls` 的 `AIMessage`，但尚無 `ToolMessage`。

    **tools**：自訂工具清單；預設為 `DEFAULT_MARKET_TOOLS`（與舊版行為一致）。
    """
    tool_list = list(tools) if tools is not None else list(DEFAULT_MARKET_TOOLS)
    llm_bound = llm.bind_tools(tool_list)
    node_tools = ToolNode(tool_list)

    async def call_model(state: AgentState) -> dict[str, Any]:
        n = len(state["messages"])
        _logger.info("call_model: 輸入訊息則數=%s", n)
        filtered_count = len(
            filter_messages(
                state["messages"],
                exclude_types=(MODEL_FILTER_EXCLUDE_TYPES or None),
            )
        )
        model_messages = preprocess_messages_for_model(state["messages"])
        if filtered_count != n:
            _logger.info(
                "call_model: 訊息過濾 %s → %s（exclude_types=%s）",
                n,
                filtered_count,
                list(MODEL_FILTER_EXCLUDE_TYPES),
            )
        if len(model_messages) != filtered_count:
            _logger.info(
                "call_model: 訊息裁剪 %s → %s（max_tokens=%s）",
                filtered_count,
                len(model_messages),
                MAX_MODEL_TOKENS,
            )
        # L4（現行）：模型節點改為 async，降低 API 等待期間對 event loop 的阻塞。
        ai = await llm_bound.ainvoke(model_messages)
        # L4 對照（舊版同步寫法，保留參考）：
        # ai = llm_bound.invoke(model_messages)
        assert isinstance(ai, AIMessage)
        if ai.tool_calls:
            names = [c["name"] for c in ai.tool_calls]
            _logger.info("call_model: 模型請求工具 %s", names)
        else:
            _logger.info("call_model: 無 tool_calls，將結束或已完成")
        return {"messages": [ai]}

    g = StateGraph(AgentState)
    g.add_node("call_model", call_model)
    g.add_node("run_tools", node_tools)
    g.add_edge(START, "call_model")
    g.add_conditional_edges(
        "call_model",
        tools_condition,
        {"tools": "run_tools", "__end__": END},
    )
    g.add_edge("run_tools", "call_model")
    return g.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before,
        interrupt_after=interrupt_after,
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


def _smoke_b1() -> None:
    _ = StateGraph(AgentState)
    left = [HumanMessage(content="hi")]
    right = [HumanMessage(content=" again")]
    merged = add_messages(left, right)
    assert len(merged) == 2
    assert merged[0].content == "hi"
    assert merged[1].content == " again"


def main() -> None:
    _smoke_b1()
    print("B1 OK: AgentState + add_messages smoke 通過。")

    app = build_agent_graph()
    _logger.info(
        "graph.invoke 開始: recursion_limit=%s",
        DEFAULT_RECURSION_LIMIT,
    )
    result = app.invoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "請透過 Binance 查詢 ETH 對 USDT 的現價，並用繁體中文簡短說明。"
                    )
                )
            ]
        },
        config={"recursion_limit": DEFAULT_RECURSION_LIMIT},
    )
    msgs = result["messages"]
    _logger.info("graph.invoke 結束: 訊息總則數=%s", len(msgs))
    for i, m in enumerate(msgs):
        typ = type(m).__name__
        extra = ""
        if isinstance(m, AIMessage) and m.tool_calls:
            extra = f" tool_calls={[c['name'] for c in m.tool_calls]}"
        _logger.debug("  [%s] %s%s", i, typ, extra)

    last = msgs[-1]
    assert isinstance(last, AIMessage)
    print(
        f"C2 OK（recursion_limit={DEFAULT_RECURSION_LIMIT}），最後一則 AI 回覆："
    )
    print(_text_from_ai_message(last))


if __name__ == "__main__":
    main()


# -----------------------------------------------------------------------------
# 參考保留：手寫「工具節點」與自訂條件邊（教學對照，未執行）
# -----------------------------------------------------------------------------
# 以下等同於目前的 ToolNode + tools_condition，若你想完全自己掌控錯誤字串或
# 特殊路由，可改回使用這些函式並在 build_agent_graph 裡改 add_node / 條件邊。
#
# import json
# from typing import Literal
# from langchain_core.messages import ToolMessage
#
# _NAME_TO_TOOL = {t.name: t for t in _tools}
#
#
# def run_tools_manual(state: AgentState) -> dict[str, Any]:
#     """手動版：讀取最後一則 AIMessage 的 tool_calls，invoke 工具，回傳 ToolMessage。"""
#     last = state["messages"][-1]
#     if not isinstance(last, AIMessage) or not last.tool_calls:
#         return {"messages": []}
#     tool_messages: list[ToolMessage] = []
#     for call in last.tool_calls:
#         name = call["name"]
#         tid = call["id"]
#         args = call.get("args") or {}
#         tool_fn = _NAME_TO_TOOL.get(name)
#         if tool_fn is None:
#             content = json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
#         else:
#             content = tool_fn.invoke(args)
#         tool_messages.append(ToolMessage(content=content, tool_call_id=tid))
#     return {"messages": tool_messages}
#
#
# def route_after_model(state: AgentState) -> Literal["run_tools", "__end__"]:
#     """手動版條件邊（對照 tools_condition）：有 tool_calls → run_tools，否則 END。"""
#     last = state["messages"][-1]
#     if isinstance(last, AIMessage) and last.tool_calls:
#         return "run_tools"
#     return END
#
# # build_agent_graph 內改為：
# #   g.add_node("run_tools", run_tools_manual)
# #   g.add_conditional_edges("call_model", route_after_model, {"run_tools": "run_tools", END: END})
