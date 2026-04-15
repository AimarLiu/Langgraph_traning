from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="使用者本輪訊息")
    thread_id: str | None = Field(
        default=None,
        description="對話 thread_id（可改由 header X-Thread-Id 提供；空字串會在路由層視為未提供）",
    )
    user_id: str | None = Field(
        default=None,
        description="可選使用者識別（可改由 header X-User-Id 提供；空字串會在路由層視為未提供）",
    )


class ChatResponse(BaseModel):
    reply: str = Field(..., description="本輪代理最後一則 AI 文字（無 tool_calls 時）")
    thread_id: str = Field(..., description="本輪實際使用的 thread_id")
    user_id: str | None = Field(default=None, description="本輪實際使用的 user_id（可為空）")
    config_source: Literal["header", "body", "mixed"] = Field(
        ...,
        description="thread_id / user_id 來源，用於除錯與審計",
    )


class HealthResponse(BaseModel):
    """L3：僅含可對外暴露的欄位，不含任何金鑰或金鑰片段。"""

    status: Literal["ok", "degraded"] = Field(
        ...,
        description="ok：行程與設定載入正常；degraded：服務在跑但缺少聊天所需設定（例如未設定 GOOGLE_API_KEY）",
    )
    google_api_key_configured: bool = Field(
        ...,
        description="是否已設定 GOOGLE_API_KEY（不暴露內容）",
    )
    langsmith_tracing: bool = Field(..., description="LANGSMITH_TRACING 是否為真")
    langsmith_api_key_configured: bool = Field(
        ...,
        description="是否已設定 LANGSMITH_API_KEY（不暴露內容）",
    )
    langsmith_project: str | None = Field(
        default=None,
        description="LANGSMITH_PROJECT（專案名稱，一般非密文）",
    )
    checkpoint_db: str = Field(
        ...,
        description="checkpoint SQLite 相對路徑（LANGGRAPH_CHECKPOINT_DB）",
    )

