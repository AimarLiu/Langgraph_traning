"""N1-P7 smoke (low-token mode): compare vector vs hybrid (no rerank).

Design goals:
- Keep retrieval comparison on sampled cases.
- Strictly limit expensive `finalize_answer=True` calls to avoid 429/token exhaustion.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import statistics
import sys
from pathlib import Path
from typing import Any, TypedDict

import path_setup

path_setup.add_src_to_path()

from dotenv import load_dotenv

load_dotenv()

from langgraph_learning.agent_logging import configure_agent_logging

configure_agent_logging()

from langchain_core.documents import Document
from langgraph_learning.tools.hybrid_lilian_chroma import hybrid_search_lilian_chroma
from langgraph_learning.tools.lilian_chroma_store import (
    open_lilian_chroma_vectorstore,
    resolve_chroma_persist_dir,
)
from langgraph_learning.tools.lilian_rag_finalize import (
    generate_answer_with_citations,
    resolve_lilian_answer_model,
)


DATASET_PATH = Path("evaluation/datasets/n1_rag_golden_cases.json")
_CITATION_RE = re.compile(r"\[\d+\]")


class GoldenCase(TypedDict):
    id: str
    query: str
    expected_retrieval_keywords: list[str]
    expected_answer_keywords: list[str]


class RetrievalEvalRow(TypedDict):
    case_id: str
    hit: bool
    error: str | None
    docs: list[Document]


class AnswerEvalRow(TypedDict):
    answer_quality: float
    answer_keyword_hit_rate: float
    citation_count: int
    has_inline_citation: bool
    error: str | None
    answer_preview: str


def _normalize_text(text: str) -> str:
    return (text or "").strip().lower()


def _load_cases(path: Path) -> list[GoldenCase]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError(f"golden set 格式錯誤：{path}")
    cases: list[GoldenCase] = []
    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"golden set 第 {idx} 筆格式錯誤")
        case = GoldenCase(
            id=str(item.get("id") or f"case-{idx:02d}"),
            query=str(item.get("query") or "").strip(),
            expected_retrieval_keywords=[str(x) for x in item.get("expected_retrieval_keywords", [])],
            expected_answer_keywords=[str(x) for x in item.get("expected_answer_keywords", [])],
        )
        if not case["query"]:
            raise ValueError(f"golden set 第 {idx} 筆缺少 query")
        cases.append(case)
    return cases


def _retrieve_docs(
    vectorstore: Any,
    query: str,
    *,
    mode: str,
) -> list[Document]:
    if mode == "vector":
        return list(vectorstore.similarity_search(query, k=3))

    persist_dir = str(resolve_chroma_persist_dir().resolve())
    collection = getattr(vectorstore, "_collection_name", "") or "default"
    cache_key = f"{persist_dir}::{collection}"
    return hybrid_search_lilian_chroma(
        vectorstore,
        query,
        keyword_top_k=3,
        vector_top_k=3,
        hybrid_top_n=3,
        weight_vector=0.6,
        weight_keyword=0.4,
        bm25_cache_key=cache_key,
    )


def _docs_blob(docs: list[Document]) -> str:
    chunks: list[str] = []
    for d in docs:
        meta = d.metadata or {}
        chunks.extend(
            [
                str(meta.get("title") or ""),
                str(meta.get("slug") or ""),
                str(meta.get("source") or ""),
                str(d.page_content or ""),
            ]
        )
    return _normalize_text(" ".join(chunks))


def _has_retrieval_keyword(docs: list[Document], keywords: list[str]) -> bool:
    blob = _docs_blob(docs)
    if not keywords:
        return bool(blob)
    return any(_normalize_text(k) in blob for k in keywords if k)


def _evaluate_retrieval(
    case: GoldenCase,
    *,
    mode: str,
    vectorstore: Any,
) -> RetrievalEvalRow:
    try:
        docs = _retrieve_docs(vectorstore, case["query"], mode=mode)
    except Exception as exc:  # noqa: BLE001
        return RetrievalEvalRow(case_id=case["id"], hit=False, error=str(exc), docs=[])
    hit = _has_retrieval_keyword(docs, case["expected_retrieval_keywords"])
    return RetrievalEvalRow(case_id=case["id"], hit=hit, error=None, docs=docs)


def _rate_answer_quality(
    answer: str,
    citations: list[dict[str, Any]],
    expected_answer_keywords: list[str],
) -> tuple[float, float, bool]:
    answer_l = _normalize_text(answer)
    expects = [_normalize_text(k) for k in expected_answer_keywords if k]
    if expects:
        matched = sum(1 for k in expects if k in answer_l)
        keyword_hit_rate = matched / len(expects)
    else:
        keyword_hit_rate = 0.0
    has_inline_citation = bool(_CITATION_RE.search(answer or ""))
    citation_presence = 1.0 if citations else 0.0
    inline_signal = 1.0 if has_inline_citation else 0.0
    quality = 0.6 * keyword_hit_rate + 0.2 * citation_presence + 0.2 * inline_signal
    return quality, keyword_hit_rate, has_inline_citation


def _evaluate_answer(
    case: GoldenCase,
    *,
    docs: list[Document],
    answer_model: str,
) -> AnswerEvalRow:
    try:
        answer, citations, _ = generate_answer_with_citations(
            case["query"],
            docs[:3],
            model=answer_model,
            max_chars_per_doc=1200,
        )
    except Exception as exc:  # noqa: BLE001
        return AnswerEvalRow(
            answer_quality=0.0,
            answer_keyword_hit_rate=0.0,
            citation_count=0,
            has_inline_citation=False,
            error=str(exc),
            answer_preview="",
        )
    quality, hit_rate, has_inline = _rate_answer_quality(answer, citations, case["expected_answer_keywords"])
    preview = answer[:160] + ("..." if len(answer) > 160 else "")
    return AnswerEvalRow(
        answer_quality=quality,
        answer_keyword_hit_rate=hit_rate,
        citation_count=len(citations),
        has_inline_citation=has_inline,
        error=None,
        answer_preview=preview,
    )


def _print_retrieval_summary(mode_name: str, rows: list[RetrievalEvalRow]) -> None:
    n = len(rows)
    if n == 0:
        print(f"\n[{mode_name}] no retrieval rows.")
        return
    hits = sum(1 for r in rows if r["hit"])
    errors = sum(1 for r in rows if r["error"])
    print(f"\n[{mode_name} | retrieval]")
    print(f"- hit_rate: {hits}/{n} ({hits / n:.1%})")
    print(f"- error_count: {errors}")


def _print_answer_summary(mode_name: str, rows: list[AnswerEvalRow]) -> None:
    n = len(rows)
    if n == 0:
        print(f"\n[{mode_name}] no finalized answers.")
        return
    quality_avg = statistics.fmean(r["answer_quality"] for r in rows)
    keyword_hit_avg = statistics.fmean(r["answer_keyword_hit_rate"] for r in rows)
    citation_avg = statistics.fmean(r["citation_count"] for r in rows)
    inline_rate = statistics.fmean(1.0 if r["has_inline_citation"] else 0.0 for r in rows)
    errors = sum(1 for r in rows if r["error"])
    print(f"\n[{mode_name} | answer]")
    print(f"- finalized_answers: {n}")
    print(f"- avg_answer_quality: {quality_avg:.3f} (0~1)")
    print(f"- avg_answer_keyword_hit_rate: {keyword_hit_avg:.3f}")
    print(f"- avg_citation_count: {citation_avg:.2f}")
    print(f"- inline_citation_rate: {inline_rate:.1%}")
    print(f"- error_count: {errors}")


def _ensure_model_max_tokens() -> None:
    try:
        cur = int((os.getenv("MODEL_MAX_TOKENS") or "0").strip() or "0")
    except ValueError:
        cur = 0
    if cur < 2048:
        os.environ["MODEL_MAX_TOKENS"] = "12000"


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    parser = argparse.ArgumentParser(
        description="N1-P7 low-token smoke: vector vs hybrid(no rerank), retrieval-first with limited finalize"
    )
    parser.add_argument("--dataset-path", type=Path, default=DATASET_PATH)
    parser.add_argument("--sample-size", type=int, default=3)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument(
        "--answer-per-mode",
        type=int,
        default=1,
        help="finalized answer count per mode for comparison (default: 1)",
    )
    parser.add_argument(
        "--max-finalize-calls",
        type=int,
        default=3,
        help="hard cap for total finalize_answer calls across modes (default: 3)",
    )
    parser.add_argument("--show-answer-preview", action="store_true")
    args = parser.parse_args()

    _ensure_model_max_tokens()
    cases = _load_cases(args.dataset_path)
    if len(cases) < 10:
        raise ValueError("N1-P7 需要至少 10 題 golden set。")

    sample_size = max(1, min(int(args.sample_size), len(cases)))
    rng = random.Random(args.random_seed)
    sampled = rng.sample(cases, sample_size)
    answer_per_mode = max(0, int(args.answer_per_mode))
    finalize_budget = max(0, int(args.max_finalize_calls))
    answer_cases = sampled[:answer_per_mode]
    answer_model = resolve_lilian_answer_model(None)
    vectorstore = open_lilian_chroma_vectorstore()

    print("=== N1-P7 Smoke (low-token) ===")
    print("- compare: vector vs hybrid (no rerank)")
    print("- retrieval docs: top 3 each mode")
    print("- finalize docs: final_top_k=3")
    print(f"- total_cases: {len(cases)}")
    print(f"- sampled_cases: {sample_size} (seed={args.random_seed})")
    print("- sampled_ids: " + ", ".join(case["id"] for case in sampled))
    print(f"- answer_per_mode: {answer_per_mode}")
    print(f"- max_finalize_calls: {finalize_budget}")

    vector_retrieval_rows: list[RetrievalEvalRow] = []
    hybrid_retrieval_rows: list[RetrievalEvalRow] = []
    for idx, case in enumerate(sampled, start=1):
        print(f"\n[{idx}/{sample_size}] retrieval | {case['id']} | query={case['query']!r}")
        v = _evaluate_retrieval(case, mode="vector", vectorstore=vectorstore)
        h = _evaluate_retrieval(case, mode="hybrid", vectorstore=vectorstore)
        vector_retrieval_rows.append(v)
        hybrid_retrieval_rows.append(h)
        print(f"- vector_hit={v['hit']} err={'yes' if v['error'] else 'no'}")
        print(f"- hybrid_hit={h['hit']} err={'yes' if h['error'] else 'no'}")

    vector_answer_rows: list[AnswerEvalRow] = []
    hybrid_answer_rows: list[AnswerEvalRow] = []
    calls_used = 0
    vector_by_case = {r["case_id"]: r for r in vector_retrieval_rows}
    hybrid_by_case = {r["case_id"]: r for r in hybrid_retrieval_rows}
    for case in answer_cases:
        if calls_used >= finalize_budget:
            break
        print(f"\n[answer-compare] {case['id']} | query={case['query']!r}")

        if calls_used < finalize_budget:
            v_docs = vector_by_case.get(case["id"], {"docs": []})["docs"]
            v_ans = _evaluate_answer(case, docs=v_docs, answer_model=answer_model)
            vector_answer_rows.append(v_ans)
            calls_used += 1
            print(
                "- vector_answer: "
                f"quality={v_ans['answer_quality']:.3f} "
                f"citations={v_ans['citation_count']} err={'yes' if v_ans['error'] else 'no'}"
            )
            if args.show_answer_preview:
                print(f"  preview={v_ans['answer_preview']!r}")

        if calls_used < finalize_budget:
            h_docs = hybrid_by_case.get(case["id"], {"docs": []})["docs"]
            h_ans = _evaluate_answer(case, docs=h_docs, answer_model=answer_model)
            hybrid_answer_rows.append(h_ans)
            calls_used += 1
            print(
                "- hybrid_answer: "
                f"quality={h_ans['answer_quality']:.3f} "
                f"citations={h_ans['citation_count']} err={'yes' if h_ans['error'] else 'no'}"
            )
            if args.show_answer_preview:
                print(f"  preview={h_ans['answer_preview']!r}")

    _print_retrieval_summary("vector", vector_retrieval_rows)
    _print_retrieval_summary("hybrid", hybrid_retrieval_rows)
    _print_answer_summary("vector", vector_answer_rows)
    _print_answer_summary("hybrid", hybrid_answer_rows)

    v_hit = statistics.fmean(1.0 if r["hit"] else 0.0 for r in vector_retrieval_rows)
    h_hit = statistics.fmean(1.0 if r["hit"] else 0.0 for r in hybrid_retrieval_rows)
    print("\n[delta: hybrid - vector | retrieval]")
    print(f"- hit_rate_delta: {h_hit - v_hit:+.3f}")

    if vector_answer_rows and hybrid_answer_rows:
        v_quality = statistics.fmean(r["answer_quality"] for r in vector_answer_rows)
        h_quality = statistics.fmean(r["answer_quality"] for r in hybrid_answer_rows)
        print("[delta: hybrid - vector | answer]")
        print(f"- answer_quality_delta: {h_quality - v_quality:+.3f}")
    print(f"\nOK: completed with finalize calls {calls_used}/{finalize_budget}.")


if __name__ == "__main__":
    main()

