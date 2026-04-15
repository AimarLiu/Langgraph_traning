"""J2／J3：Lilian Weng Chroma 檢索工具（query → similarity_search → 字串片段）。"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from langgraph_learning.tools.lilian_chroma_store import (
    open_lilian_chroma_vectorstore,
    resolve_chroma_persist_dir,
)

# 供 `practice_11_rag_tool.py` 或自訂圖在初始 messages 放入 SystemMessage，與 J3「依據標示」對齊。
LILIAN_RAG_SYSTEM_PROMPT = """你是任務助理，可呼叫多種工具。

**內部知識庫（Lilian Weng 部落格向量索引）**
- 當使用者詢問的主題**可能出現在已索引文章**（例如強化學習、代理人、安全對齊、深度學習相關教學），請先呼叫 `search_lilian_weng_knowledge` 取得片段，再依片段作答。
- 若問題只需即時市場數據（例如 ETH 幣價、USD→THB 匯率），請使用對應市場工具，**不要**為了滿足格式而強制呼叫內部知識庫。

**引用與誠實性**
- 若答案依賴檢索片段，請在文末以「**依據**」小節列出：你使用的 `[編號]` 與對應 title、slug（若有）、source（與工具回傳標頭一致）。
- 若工具回傳未找到相近片段、或僅有錯誤訊息而無可用正文，請明確說「文件未載明」或「索引中無相關內容」，**不要臆測**技術細節。"""


def _format_hits(docs: list[Any]) -> str:
    parts: list[str] = []
    for i, doc in enumerate(docs, start=1):
        meta = getattr(doc, "metadata", {}) or {}
        title = meta.get("title", "")
        source = meta.get("source", "")
        slug = meta.get("slug", "")
        header = f"[{i}] title={title!r} slug={slug!r} source={source!r}"
        body = (getattr(doc, "page_content", "") or "").strip()
        parts.append(f"{header}\n{body}")
    return "\n\n---\n\n".join(parts)


@tool
def search_lilian_weng_knowledge(query: str, top_k: int = 4) -> str:
    """在 Lilian Weng 部落格向量索引中做語意檢索（內部知識庫）。

    當使用者問題可能由已索引文章回答時應優先使用；即時價格／匯率請改用市場類工具。

    使用前須先執行 J1 建立 Chroma。回傳每則含 `[n] title=… slug=… source=…` 與正文，供最終回答在「依據」中對應引用。
    """
    q = (query or "").strip()
    if not q:
        return json.dumps({"error": "query 不可為空"}, ensure_ascii=False)

    persist = resolve_chroma_persist_dir()
    if not persist.exists():
        return json.dumps(
            {
                "error": "找不到 Chroma 資料目錄",
                "hint": f"請先執行 J1 建索引；預期路徑: {persist}",
            },
            ensure_ascii=False,
        )

    try:
        k = int(top_k)
    except (TypeError, ValueError):
        k = 4
    k = max(1, min(k, 12))
    try:
        vs = open_lilian_chroma_vectorstore()
        docs = vs.similarity_search(q, k=k)
    except Exception as exc:  # noqa: BLE001
        return json.dumps(
            {"error": "檢索失敗", "detail": str(exc)},
            ensure_ascii=False,
        )

    if not docs:
        return json.dumps(
            {"message": "未找到相近片段", "query": q},
            ensure_ascii=False,
        )

    return _format_hits(docs)
