"""
第三課表 L1：FastAPI app 組裝位置（集中於 `src/api/`）。

圖與節點行為見 `src/langgraph_learning/graphs/agent_graph.py`；市場工具 async 見 K2。

L1/L2 必做標註（同步／async 邊界）：
① **路由**：`POST /chat` 為 async handler，內層使用 **`await graph.ainvoke`**。
② **`call_model` 節點**：仍為 **`llm_bound.invoke`（同步）**；若未來做 L4 才改為 async。
③ **`ToolNode`（`run_tools`）**：對具 coroutine 的工具會走 **`ainvoke`**（K2）。

L2 已補上：`thread_id`（與可選 `user_id`）由 header/body 映射到
`config["configurable"]`，並在 lifespan 掛上 checkpointer。

L3：`GET /health` 透過 `api.settings.ApiSettings` 讀 `.env`，回傳僅非敏感摘要；
checkpoint 路徑與 `LANGGRAPH_CHECKPOINT_DB` 對齊。

L4：`call_model` 已改為 `await llm_bound.ainvoke(...)`（舊同步 `invoke` 保留註解於
`src/langgraph_learning/graphs/agent_graph.py` 供對照）。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from api.routes.chat import router as chat_router
from api.routes.health import router as health_router
from api.settings import get_settings
from langgraph_learning.graphs.agent_graph import build_agent_graph


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # 常駐服務：進程內編譯一次、請求重用（對照 Docs/checkpointer_in_services.md、K3）。
    checkpoint_path = Path(get_settings().checkpoint_db)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
        app.state.graph = build_agent_graph(checkpointer=checkpointer)
        yield


def create_app() -> FastAPI:
    app = FastAPI(title="LangGraph API", lifespan=_lifespan)
    app.include_router(chat_router)
    app.include_router(health_router)
    return app


app = create_app()

