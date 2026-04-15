from __future__ import annotations

from typing import Annotated
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from langchain_core.messages import AIMessage, HumanMessage

from api.schemas import ChatRequest, ChatResponse
from api.state import get_graph
from langgraph_learning.graphs.agent_graph import DEFAULT_RECURSION_LIMIT

router = APIRouter(tags=["chat"])


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


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    x_thread_id: Annotated[str | None, Header(alias="X-Thread-Id")] = None,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> ChatResponse:
    # ① 路由層：此處為 async，並 await 圖的 ainvoke（非同步圖 API）。
    graph = get_graph(request.app)
    thread_id, user_id, config_source = _resolve_request_identity(
        body_thread_id=body.thread_id,
        body_user_id=body.user_id,
        header_thread_id=x_thread_id,
        header_user_id=x_user_id,
    )
    try:
        out = await graph.ainvoke(
            {"messages": [HumanMessage(content=body.message)]},
            config={
                "recursion_limit": DEFAULT_RECURSION_LIMIT,
                # L2 對應：X-Thread-Id / body.thread_id、X-User-Id / body.user_id
                # → config["configurable"]["thread_id" / "user_id"]（供 checkpoint 定址與審計）。
                "configurable": {
                    "thread_id": thread_id,
                    **({"user_id": user_id} if user_id else {}),
                },
            },
        )
    except Exception as exc:  # noqa: BLE001 — 教學用：避免裸 API 例外直接回傳客戶端細節
        raise HTTPException(status_code=502, detail="代理執行失敗") from exc

    msgs = out.get("messages") or []
    if not msgs:
        raise HTTPException(status_code=500, detail="圖未回傳任何訊息")
    last = msgs[-1]
    if not isinstance(last, AIMessage):
        raise HTTPException(
            status_code=500,
            detail=f"最後一則非 AIMessage：{type(last).__name__}",
        )
    if last.tool_calls:
        raise HTTPException(
            status_code=500,
            detail="圖結束時最後一則 AI 仍帶 tool_calls（應已走完工具迴圈）",
        )
    # ② call_model 現為 async ainvoke（舊同步 invoke 已保留註解供對照）、
    # ③ ToolNode 對 async 工具走 ainvoke — 見 app.py 與 agent_graph.py 說明。
    return ChatResponse(
        reply=_text_from_ai_message(last),
        thread_id=thread_id,
        user_id=user_id,
        config_source=config_source,
    )


def _resolve_request_identity(
    *,
    body_thread_id: str | None,
    body_user_id: str | None,
    header_thread_id: str | None,
    header_user_id: str | None,
) -> tuple[str, str | None, str]:
    thread_id = (header_thread_id or body_thread_id or "").strip()
    user_id = (header_user_id or body_user_id or "").strip() or None
    if not thread_id:
        raise HTTPException(
            status_code=422,
            detail="缺少 thread_id：請在 header X-Thread-Id 或 body.thread_id 提供。",
        )

    has_header = bool((header_thread_id or "").strip() or (header_user_id or "").strip())
    has_body = bool((body_thread_id or "").strip() or (body_user_id or "").strip())
    if has_header and has_body:
        source = "mixed"
    elif has_header:
        source = "header"
    else:
        source = "body"
    return thread_id, user_id, source

