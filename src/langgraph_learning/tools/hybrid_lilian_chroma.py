"""Hybrid retrieval helpers for Lilian Weng Chroma (BM25 + vector).

This module is split out from `rag_lilian.py` so hybrid logic can be reused without
pulling in the LangChain `@tool` wrapper.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document

from langgraph_learning.tools.bm25_keyword import (
    default_doc_key,
    keyword_search_chroma_collection,
)


@dataclass(frozen=True)
class HybridHit:
    doc: Document
    keyword_raw: float | None
    vector_raw: float | None
    keyword_norm: float
    vector_norm: float
    hybrid_score: float


def minmax_normalize(values: list[float | None]) -> list[float]:
    present = [v for v in values if v is not None]
    if not present:
        return [0.0 for _ in values]
    vmin = min(present)
    vmax = max(present)
    if math.isclose(vmin, vmax):
        return [1.0 if v is not None else 0.0 for v in values]
    return [((v - vmin) / (vmax - vmin)) if v is not None else 0.0 for v in values]


def hybrid_search_lilian_chroma(
    vectorstore: Any,
    query: str,
    *,
    keyword_top_k: int,
    vector_top_k: int,
    hybrid_top_n: int,
    weight_vector: float,
    weight_keyword: float,
    bm25_cache_key: str,
    doc_key: Any = default_doc_key,
) -> list[Document]:
    """N1-P1~P3: BM25 keyword + vector -> dedupe -> min-max normalize -> weighted sort."""
    keyword_hits = keyword_search_chroma_collection(
        vectorstore,
        query,
        top_k=keyword_top_k,
        cache_key=bm25_cache_key,
        doc_key=doc_key,
    )

    vector_hits = vectorstore.similarity_search_with_score(query, k=vector_top_k)
    # Chroma 返回通常是距離（越小越相近）；轉成「越大越好」方便 normalize。
    vector_scored: list[tuple[Document, float | None, str]] = []
    for doc, dist in vector_hits:
        try:
            raw = -float(dist)
        except (TypeError, ValueError):
            raw = None
        vector_scored.append((doc, raw, doc_key(doc)))

    merged: dict[str, dict[str, Any]] = {}
    for doc, s, key in keyword_hits:
        item = merged.get(key)
        if item is None:
            merged[key] = {"doc": doc, "keyword_raw": float(s), "vector_raw": None}
        else:
            item["keyword_raw"] = max(item.get("keyword_raw") or 0.0, float(s))

    for doc, s, key in vector_scored:
        item = merged.get(key)
        if item is None:
            merged[key] = {"doc": doc, "keyword_raw": None, "vector_raw": s}
        else:
            cur = item.get("vector_raw")
            if cur is None or (s is not None and s > cur):
                item["vector_raw"] = s

    items = list(merged.values())
    kw_raws = [it.get("keyword_raw") for it in items]
    vec_raws = [it.get("vector_raw") for it in items]
    kw_norms = minmax_normalize(kw_raws)
    vec_norms = minmax_normalize(vec_raws)

    hits: list[HybridHit] = []
    for it, kn, vn in zip(items, kw_norms, vec_norms, strict=False):
        hybrid = float(weight_vector) * float(vn) + float(weight_keyword) * float(kn)
        hits.append(
            HybridHit(
                doc=it["doc"],
                keyword_raw=it.get("keyword_raw"),
                vector_raw=it.get("vector_raw"),
                keyword_norm=float(kn),
                vector_norm=float(vn),
                hybrid_score=float(hybrid),
            )
        )

    hits.sort(key=lambda h: h.hybrid_score, reverse=True)
    hits = hits[:hybrid_top_n]

    docs_out: list[Document] = []
    for h in hits:
        d = h.doc
        meta = dict(d.metadata or {})
        meta["keyword_raw"] = h.keyword_raw
        meta["vector_raw"] = h.vector_raw
        meta["keyword_norm"] = round(h.keyword_norm, 6)
        meta["vector_norm"] = round(h.vector_norm, 6)
        meta["hybrid_score"] = round(h.hybrid_score, 6)
        d.metadata = meta
        docs_out.append(d)

    return docs_out
