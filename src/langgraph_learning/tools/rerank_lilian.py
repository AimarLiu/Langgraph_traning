"""Optional reranker for Lilian RAG chunks (N1-P4).

This module is intentionally isolated so reranking can be enabled only when needed.

Default backend: Gemini pointwise scoring (0-100) using `ChatGoogleGenerativeAI` +
`with_structured_output` (same family of APIs already used elsewhere in this repo).
"""

from __future__ import annotations

import os
from typing import Any, Iterable

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field


_DEFAULT_RERANK_MODEL = "gemini-3-flash-preview"


class _RerankScore(BaseModel):
    relevance_0_100: int = Field(
        ge=0,
        le=100,
        description="How relevant the passage is to answering the query (0-100).",
    )
    brief_reason: str = Field(
        default="",
        description="One short sentence explaining the score.",
    )


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    v = raw.strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    return default


def resolve_lilian_rerank_enabled(explicit: bool | None) -> bool:
    """Resolve whether reranking is enabled.

    Precedence:
    - explicit True/False wins if not None
    - else fall back to env `LILIAN_RERANK_ENABLED`
    """
    if explicit is not None:
        return bool(explicit)
    load_dotenv()
    return _env_bool("LILIAN_RERANK_ENABLED", default=False)


def resolve_lilian_rerank_model(explicit: str | None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    load_dotenv()
    return (os.getenv("LILIAN_RERANK_MODEL") or "").strip() or _DEFAULT_RERANK_MODEL


def _truncate(text: str, max_chars: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[:max_chars] + "\n\n[...truncated for rerank...]"


def rerank_documents_gemini_pointwise(
    query: str,
    docs: Iterable[Document],
    *,
    model: str,
    max_doc_chars: int = 1600,
) -> list[Document]:
    """Rerank documents by invoking a small structured LLM scorer per document."""
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 GOOGLE_API_KEY，無法執行 rerank。")

    q = (query or "").strip()
    if not q:
        raise ValueError("query 不可為空")

    llm = ChatGoogleGenerativeAI(model=model, api_key=api_key, temperature=0.0)
    scorer = llm.with_structured_output(_RerankScore)

    scored: list[tuple[Document, int, str]] = []
    for doc in docs:
        passage = _truncate(doc.page_content or "", max_doc_chars)
        prompt = (
            "You are a retrieval judge.\n"
            "Score how useful the passage is for answering the QUERY.\n"
            "Be strict: unrelated passages should get low scores.\n\n"
            f"QUERY:\n{q}\n\n"
            f"PASSAGE:\n{passage}\n"
        )
        out: _RerankScore = scorer.invoke(prompt)  # type: ignore[assignment]
        scored.append((doc, int(out.relevance_0_100), (out.brief_reason or "").strip()))

    scored.sort(key=lambda x: x[1], reverse=True)
    reranked: list[Document] = []
    for doc, score, reason in scored:
        meta = dict(doc.metadata or {})
        meta["rerank_score"] = int(score)
        if reason:
            meta["rerank_reason"] = reason
        doc.metadata = meta
        reranked.append(doc)
    return reranked
