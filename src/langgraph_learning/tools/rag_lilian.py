"""J2／J3：Lilian Weng Chroma 檢索工具（query → similarity_search → 字串片段）。"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from langgraph_learning.agent_logging import get_agent_logger, is_agent_logging_enabled
from langgraph_learning.tools.bm25_keyword import default_doc_key
from langgraph_learning.tools.hybrid_lilian_chroma import hybrid_search_lilian_chroma
from langgraph_learning.tools.lilian_chroma_store import (
    open_lilian_chroma_vectorstore,
    resolve_chroma_persist_dir,
)
from langgraph_learning.tools.rerank_lilian import (
    rerank_documents_gemini_pointwise,
    resolve_lilian_rerank_enabled,
    resolve_lilian_rerank_model,
)
from langgraph_learning.tools.lilian_rag_finalize import (
    generate_answer_with_citations,
    resolve_lilian_answer_model,
)

# 供 `practice_11_rag_tool.py` 或自訂圖在初始 messages 放入 SystemMessage，與 J3「依據標示」對齊。
_LOG = get_agent_logger("rag_lilian.obs")


def _query_obs_fields(query: str) -> dict[str, Any]:
    q = (query or "").strip()
    cap = 120
    preview = q[:cap] + ("…" if len(q) > cap else "")
    return {"query_preview": preview, "query_len": len(q)}


def _doc_rows_for_obs(docs: list[Any], *, limit: int | None = 50) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    slice_docs = docs if limit is None else docs[:limit]
    for i, doc in enumerate(slice_docs, start=1):
        meta = getattr(doc, "metadata", {}) or {}
        rows.append(
            {
                "rank": i,
                "doc_key": default_doc_key(doc),
                "title": (meta.get("title") or "")[:240],
                "slug": (meta.get("slug") or "")[:240],
                "source": (meta.get("source") or "")[:240],
                "hybrid_score": meta.get("hybrid_score"),
                "vector_norm": meta.get("vector_norm"),
                "keyword_norm": meta.get("keyword_norm"),
                "rerank_score": meta.get("rerank_score"),
            }
        )
    return rows


def _emit_lilian_rag_pipeline_obs(
    *,
    query: str,
    mode: str,
    retrieve: dict[str, Any],
    hybrid_scored_docs: list[dict[str, Any]] | None,
    rerank_scored_docs: list[dict[str, Any]] | None,
    final_docs: list[dict[str, Any]],
) -> None:
    """N1-P6: query → retrieve → hybrid_score → rerank_score → final_docs (log + LangSmith)."""
    payload: dict[str, Any] = {
        **_query_obs_fields(query),
        "mode": mode,
        "retrieve": retrieve,
        "hybrid_score": hybrid_scored_docs,
        "rerank_score": rerank_scored_docs,
        "final_docs": final_docs,
    }
    if is_agent_logging_enabled():
        _LOG.info("lilian_rag_pipeline %s", json.dumps(payload, ensure_ascii=False))
    try:
        from langsmith.run_helpers import get_current_run_tree, set_run_metadata

        if get_current_run_tree() is not None:
            set_run_metadata(lilian_rag_pipeline=payload)
    except Exception:  # noqa: BLE001
        pass


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
        rerank = meta.get("rerank_score", None)
        hybrid_score = meta.get("hybrid_score", None)
        vec_norm = meta.get("vector_norm", None)
        kw_norm = meta.get("keyword_norm", None)

        header = f"[{i}] title={title!r} slug={slug!r} source={source!r}"
        if rerank is not None:
            header += f" rerank={rerank!r}"
        if hybrid_score is not None:
            header += (
                f" hybrid={hybrid_score} "
                f"(vec_norm={vec_norm}, kw_norm={kw_norm})"
            )
        body = (getattr(doc, "page_content", "") or "").strip()
        parts.append(f"{header}\n{body}")
    return "\n\n---\n\n".join(parts)


@tool
def search_lilian_weng_knowledge(
    query: str,
    top_k: int = 4,
    mode: str = "vector",
    keyword_top_k: int = 10,
    vector_top_k: int = 10,
    hybrid_top_n: int = 20,
    weight_vector: float = 0.6,
    weight_keyword: float = 0.4,
    rerank: bool | None = None,
    rerank_model: str | None = None,
    final_top_k: int = 5,
    finalize_answer: bool = False,
    answer_model: str | None = None,
    max_evidence_chars_per_doc: int = 2400,
) -> str:
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
        m = (mode or "").strip().lower()
        rerank_on = resolve_lilian_rerank_enabled(rerank)
        rerank_model_resolved = resolve_lilian_rerank_model(rerank_model)
        answer_model_resolved = resolve_lilian_answer_model(answer_model)
        try:
            fk = int(final_top_k)
        except (TypeError, ValueError):
            fk = 5
        fk = max(1, min(fk, 12))
        try:
            max_doc_chars = int(max_evidence_chars_per_doc)
        except (TypeError, ValueError):
            max_doc_chars = 2400
        max_doc_chars = max(200, min(max_doc_chars, 8000))

        if m in ("vector", "semantic", "dense", ""):
            docs_vec = vs.similarity_search(q, k=k)
            if not docs_vec:
                _emit_lilian_rag_pipeline_obs(
                    query=q,
                    mode="vector",
                    retrieve={"branch": "vector", "top_k": k, "hit_count": 0},
                    hybrid_scored_docs=None,
                    rerank_scored_docs=None,
                    final_docs=[],
                )
                return json.dumps(
                    {"message": "未找到相近片段", "query": q},
                    ensure_ascii=False,
                )
            if rerank_on:
                docs_after_rerank = rerank_documents_gemini_pointwise(
                    q, docs_vec, model=rerank_model_resolved
                )
                docs = docs_after_rerank[:fk]
                rerank_rows = _doc_rows_for_obs(docs_after_rerank)
            else:
                docs = docs_vec[:fk]
                rerank_rows = None
            _emit_lilian_rag_pipeline_obs(
                query=q,
                mode="vector",
                retrieve={"branch": "vector", "top_k": k, "hit_count": len(docs_vec)},
                hybrid_scored_docs=None,
                rerank_scored_docs=rerank_rows,
                final_docs=_doc_rows_for_obs(docs, limit=None),
            )
            if finalize_answer:
                answer, citations, used_ids = generate_answer_with_citations(
                    q,
                    docs,
                    model=answer_model_resolved,
                    max_chars_per_doc=max_doc_chars,
                )
                return json.dumps(
                    {
                        "mode": "vector",
                        "query": q,
                        "evidence_text": _format_hits(docs),
                        "answer": answer,
                        "citations": citations,
                        "used_evidence_ids": used_ids,
                    },
                    ensure_ascii=False,
                )
            return _format_hits(docs)

        if m != "hybrid":
            return json.dumps(
                {"error": "不支援的 mode", "mode": mode, "supported": ["vector", "hybrid"]},
                ensure_ascii=False,
            )

        # N1-P1~P3: hybrid = keyword(BM25) + vector(Chroma) -> dedupe -> normalize -> weighted sort
        kk = max(1, min(int(keyword_top_k), 50))
        vk = max(1, min(int(vector_top_k), 50))
        tn = max(1, min(int(hybrid_top_n), 50))
        wv = float(weight_vector)
        wk = float(weight_keyword)

        persist_dir = str(resolve_chroma_persist_dir().resolve())
        collection = getattr(vs, "_collection_name", "") or "default"
        cache_key = f"{persist_dir}::{collection}"

        docs_hybrid = hybrid_search_lilian_chroma(
            vs,
            q,
            keyword_top_k=kk,
            vector_top_k=vk,
            hybrid_top_n=tn,
            weight_vector=wv,
            weight_keyword=wk,
            bm25_cache_key=cache_key,
        )

        if not docs_hybrid:
            _emit_lilian_rag_pipeline_obs(
                query=q,
                mode="hybrid",
                retrieve={
                    "branch": "hybrid",
                    "keyword_top_k": kk,
                    "vector_top_k": vk,
                    "hybrid_top_n": tn,
                    "weight_vector": wv,
                    "weight_keyword": wk,
                    "merged_count": 0,
                },
                hybrid_scored_docs=[],
                rerank_scored_docs=None,
                final_docs=[],
            )
            return json.dumps(
                {"message": "未找到相近片段", "query": q, "mode": "hybrid"},
                ensure_ascii=False,
            )

        hybrid_rows = _doc_rows_for_obs(docs_hybrid)
        if rerank_on:
            docs_after_rerank = rerank_documents_gemini_pointwise(
                q, docs_hybrid, model=rerank_model_resolved
            )
            docs_out = docs_after_rerank[:fk]
            rerank_rows = _doc_rows_for_obs(docs_after_rerank)
        else:
            docs_out = docs_hybrid[:fk]
            rerank_rows = None

        _emit_lilian_rag_pipeline_obs(
            query=q,
            mode="hybrid",
            retrieve={
                "branch": "hybrid",
                "keyword_top_k": kk,
                "vector_top_k": vk,
                "hybrid_top_n": tn,
                "weight_vector": wv,
                "weight_keyword": wk,
                "merged_count": len(docs_hybrid),
            },
            hybrid_scored_docs=hybrid_rows,
            rerank_scored_docs=rerank_rows,
            final_docs=_doc_rows_for_obs(docs_out, limit=None),
        )

        if finalize_answer:
            answer, citations, used_ids = generate_answer_with_citations(
                q,
                docs_out,
                model=answer_model_resolved,
                max_chars_per_doc=max_doc_chars,
            )
            return json.dumps(
                {
                    "mode": "hybrid",
                    "query": q,
                    "evidence_text": _format_hits(docs_out),
                    "answer": answer,
                    "citations": citations,
                    "used_evidence_ids": used_ids,
                },
                ensure_ascii=False,
            )
        return _format_hits(docs_out)
    except Exception as exc:  # noqa: BLE001
        return json.dumps(
            {"error": "檢索失敗", "detail": str(exc)},
            ensure_ascii=False,
        )

    return json.dumps(
        {"error": "檢索失敗（未知）", "detail": "unexpected control flow"},
        ensure_ascii=False,
    )
