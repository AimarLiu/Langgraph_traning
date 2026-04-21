"""Minimal BM25 keyword retrieval utilities (tokenize + index + top-k).

This module is intentionally small and dependency-light so it can be reused by:
- hybrid retrieval (vector + BM25)
- standalone keyword-only retrieval
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

import xxhash
from langchain_core.documents import Document


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def tokenize_for_bm25(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")]


def default_doc_key(doc: Document) -> str:
    meta = doc.metadata or {}
    source = (meta.get("source") or "").strip()
    slug = (meta.get("slug") or "").strip()
    content = (doc.page_content or "").strip()
    h = xxhash.xxh64_hexdigest(content)
    return f"{source}::{slug}::{h}"


@dataclass(frozen=True)
class BM25Index:
    docs: list[Document]
    doc_keys: list[str]
    tf: list[Counter[str]]
    doc_len: list[int]
    avgdl: float
    idf: dict[str, float]
    k1: float
    b: float


_BM25_CACHE: dict[str, BM25Index] = {}


def build_bm25_index_from_chroma(
    vectorstore: Any,
    *,
    cache_key: str | None = None,
    doc_key: Any = default_doc_key,
) -> BM25Index:
    """Build a BM25 index from all documents in a Chroma-backed LangChain vectorstore."""
    key = cache_key or ""
    if key:
        cached = _BM25_CACHE.get(key)
        if cached is not None:
            return cached

    raw = vectorstore.get(include=["documents", "metadatas"])
    documents = raw.get("documents") or []
    metadatas = raw.get("metadatas") or []

    docs: list[Document] = []
    doc_keys: list[str] = []
    tf: list[Counter[str]] = []
    doc_len: list[int] = []

    for text, meta in zip(documents, metadatas, strict=False):
        if not text:
            continue
        doc = Document(page_content=text, metadata=meta or {})
        docs.append(doc)
        doc_keys.append(doc_key(doc))
        tokens = tokenize_for_bm25(text)
        tf.append(Counter(tokens))
        doc_len.append(len(tokens))

    n = len(docs)
    if n == 0:
        idx = BM25Index(
            docs=[],
            doc_keys=[],
            tf=[],
            doc_len=[],
            avgdl=0.0,
            idf={},
            k1=1.5,
            b=0.75,
        )
        if key:
            _BM25_CACHE[key] = idx
        return idx

    avgdl = sum(doc_len) / n

    df: Counter[str] = Counter()
    for freqs in tf:
        df.update(freqs.keys())

    idf: dict[str, float] = {}
    for term, dfi in df.items():
        # BM25Okapi smoothing via +1 inside log; stable for very common terms.
        idf[term] = math.log((n - dfi + 0.5) / (dfi + 0.5) + 1.0)

    idx = BM25Index(
        docs=docs,
        doc_keys=doc_keys,
        tf=tf,
        doc_len=doc_len,
        avgdl=avgdl,
        idf=idf,
        k1=1.5,
        b=0.75,
    )
    if key:
        _BM25_CACHE[key] = idx
    return idx


def bm25_top_k(
    idx: BM25Index,
    query: str,
    *,
    top_k: int,
) -> list[tuple[Document, float, str]]:
    """Return top-k docs by BM25 score for a query."""
    tokens = tokenize_for_bm25(query)
    if not tokens or not idx.docs:
        return []

    scores: list[tuple[int, float]] = []
    for i, freqs in enumerate(idx.tf):
        dl = idx.doc_len[i]
        score = 0.0
        for t in tokens:
            term_tf = freqs.get(t, 0)
            if term_tf <= 0:
                continue
            idf = idx.idf.get(t, 0.0)
            denom = term_tf + idx.k1 * (1.0 - idx.b + idx.b * (dl / (idx.avgdl or 1.0)))
            score += idf * (term_tf * (idx.k1 + 1.0)) / (denom or 1.0)
        if score > 0.0:
            scores.append((i, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    out: list[tuple[Document, float, str]] = []
    for i, s in scores[:top_k]:
        out.append((idx.docs[i], s, idx.doc_keys[i]))
    return out


def keyword_search_chroma_collection(
    vectorstore: Any,
    query: str,
    *,
    top_k: int,
    cache_key: str | None = None,
    doc_key: Any = default_doc_key,
) -> list[tuple[Document, float, str]]:
    """Convenience: build (cached) BM25 index + return top-k hits."""
    idx = build_bm25_index_from_chroma(vectorstore, cache_key=cache_key, doc_key=doc_key)
    return bm25_top_k(idx, query, top_k=top_k)
