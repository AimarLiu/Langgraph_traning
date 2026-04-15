from __future__ import annotations

from typing import Any

from fastapi import FastAPI


def get_graph(app: FastAPI) -> Any:
    """取得 FastAPI app.state 中的已編譯圖。"""
    return app.state.graph

