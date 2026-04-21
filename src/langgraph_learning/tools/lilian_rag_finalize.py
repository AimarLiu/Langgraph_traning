"""N1-P5: finalize Lilian RAG with an LLM answer + citations.

Key constraint: only the provided `final_docs` (typically `final_top_k`) should be
shown to the model as evidence.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field


_DEFAULT_ANSWER_MODEL = "gemini-3-flash-preview"


class _FinalizeAnswer(BaseModel):
    answer: str = Field(description="Final answer grounded in the numbered evidence passages.")
    used_evidence_ids: list[int] = Field(
        default_factory=list,
        description="1-based evidence ids ([1], [2], ...) that the answer relies on.",
    )


def resolve_lilian_answer_model(explicit: str | None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    load_dotenv()
    return (os.getenv("LILIAN_ANSWER_MODEL") or "").strip() or _DEFAULT_ANSWER_MODEL


def _truncate(text: str, max_chars: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[:max_chars] + "\n\n[...truncated...]"


def build_numbered_evidence(final_docs: list[Document], *, max_chars_per_doc: int) -> str:
    parts: list[str] = []
    for i, doc in enumerate(final_docs, start=1):
        meta = doc.metadata or {}
        title = meta.get("title", "")
        slug = meta.get("slug", "")
        source = meta.get("source", "")
        header = f"[{i}] title={title!r} slug={slug!r} source={source!r}"
        body = _truncate(doc.page_content or "", max_chars_per_doc)
        parts.append(f"{header}\n{body}")
    return "\n\n---\n\n".join(parts)


def generate_answer_with_citations(
    query: str,
    final_docs: list[Document],
    *,
    model: str,
    max_chars_per_doc: int = 2400,
) -> tuple[str, list[dict[str, Any]], list[int]]:
    """Return (answer, citations, used_ids)."""
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 GOOGLE_API_KEY，無法生成答案。")

    q = (query or "").strip()
    if not q:
        raise ValueError("query 不可為空")
    if not final_docs:
        raise ValueError("final_docs 不可為空")

    evidence = build_numbered_evidence(final_docs, max_chars_per_doc=max_chars_per_doc)

    llm = ChatGoogleGenerativeAI(model=model, api_key=api_key, temperature=0.2)
    structured = llm.with_structured_output(_FinalizeAnswer)

    prompt = (
        "You are answering using ONLY the evidence passages below.\n"
        "Rules:\n"
        "- If the evidence is insufficient, say so explicitly.\n"
        "- Do not invent facts not supported by evidence.\n"
        "- Use Traditional Chinese (zh-TW).\n"
        "- In your answer text, cite evidence like [1], [2] matching the numbered passages.\n"
        "- Also return used_evidence_ids as integers (1..N).\n\n"
        f"QUESTION:\n{q}\n\n"
        f"EVIDENCE:\n{evidence}\n"
    )

    out: _FinalizeAnswer = structured.invoke(prompt)  # type: ignore[assignment]
    used_ids = [int(x) for x in (out.used_evidence_ids or []) if isinstance(x, int)]

    # Normalize ids to valid range; if model omitted ids, fall back to all passages.
    n = len(final_docs)
    used_ids = [i for i in used_ids if 1 <= i <= n]
    if not used_ids:
        used_ids = list(range(1, n + 1))

    citations: list[dict[str, Any]] = []
    for i in used_ids:
        doc = final_docs[i - 1]
        meta = dict(doc.metadata or {})
        citations.append(
            {
                "id": i,
                "title": meta.get("title", ""),
                "slug": meta.get("slug", ""),
                "source": meta.get("source", ""),
                "snippet": _truncate(doc.page_content or "", 400),
                "scores": {
                    "rerank_score": meta.get("rerank_score"),
                    "hybrid_score": meta.get("hybrid_score"),
                    "vector_raw": meta.get("vector_raw"),
                    "keyword_raw": meta.get("keyword_raw"),
                    "vector_norm": meta.get("vector_norm"),
                    "keyword_norm": meta.get("keyword_norm"),
                },
            }
        )

    return out.answer.strip(), citations, used_ids
