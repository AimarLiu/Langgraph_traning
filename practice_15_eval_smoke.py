"""
第三課表 M：M1/M2/M3 評測腳本。

模式：
1) smoke（M1/M3）：本機逐筆 ainvoke + 關鍵字規則比對
2) sync-dataset（M2）：將 golden json 同步到 LangSmith Dataset
3) langsmith-eval（M2）：用 LangSmith evaluate 跑規則評測
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Literal

import path_setup

path_setup.add_src_to_path()

from langchain_core.messages import AIMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langsmith import Client
from langsmith.evaluation import evaluate
from langsmith.utils import LangSmithNotFoundError
from pydantic import BaseModel, Field
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from langgraph_learning.graphs.agent_graph import DEFAULT_RECURSION_LIMIT, build_agent_graph

DATASET_PATH = Path("evaluation/datasets/m1_golden_cases.json")
DEFAULT_LANGSMITH_DATASET = "LangGraph_Learning_M1_Golden"
DEFAULT_JUDGE_MODEL = os.getenv("M2_JUDGE_MODEL", "gemini-3-flash-preview")
DEFAULT_JUDGE_TEMPLATE = os.getenv("M2_JUDGE_TEMPLATE", "lenient")
DEFAULT_JUDGE_DIMENSIONS = os.getenv(
    "M2_JUDGE_DIMENSIONS",
    "relevance,helpfulness,groundedness",
)
DEFAULT_RETRY_ATTEMPTS = int(os.getenv("M2_RETRY_ATTEMPTS", "3"))
DEFAULT_RETRY_MAX_WAIT_SECONDS = float(os.getenv("M2_RETRY_MAX_WAIT_SECONDS", "8"))
DEFAULT_FALLBACK_TO_KEYWORD_ON_JUDGE_ERROR = (
    os.getenv("M2_FALLBACK_TO_KEYWORD_ON_JUDGE_ERROR", "true").strip().lower()
    in {"1", "true", "yes", "on"}
)
_judge_chain: Any | None = None
ALLOWED_JUDGE_DIMENSIONS = ("relevance", "helpfulness", "groundedness")
_runtime_retry_attempts = DEFAULT_RETRY_ATTEMPTS
_runtime_retry_max_wait_seconds = DEFAULT_RETRY_MAX_WAIT_SECONDS
_runtime_fallback_to_keyword_on_judge_error = DEFAULT_FALLBACK_TO_KEYWORD_ON_JUDGE_ERROR
_runtime_judge_disabled = False
_runtime_judge_disable_reason = ""


@dataclass(slots=True)
class GoldenCase:
    case_id: str
    category: str
    user_input: str
    must_include: list[str]
    must_not_include: list[str]
    note: str


class JudgeBinaryResult(BaseModel):
    """LLM-as-judge 的結構化輸出（0/1 + reason）。"""

    score: Literal[0, 1] = Field(description="0=不通過，1=通過。")
    reason: str = Field(description="簡短評語，說明給分原因。")


def _text_from_ai_message(msg: AIMessage) -> str:
    content: Any = msg.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts) if parts else str(content)
    return str(content)


def _load_cases(dataset_path: Path) -> list[GoldenCase]:
    raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases: list[GoldenCase] = []
    for item in raw:
        cases.append(
            GoldenCase(
                case_id=str(item["id"]),
                category=str(item["category"]),
                user_input=str(item["input"]),
                must_include=[str(x) for x in item.get("must_include", [])],
                must_not_include=[str(x) for x in item.get("must_not_include", [])],
                note=str(item.get("note", "")),
            )
        )
    return cases


def _check_case(case: GoldenCase, answer: str) -> tuple[bool, list[str]]:
    failures: list[str] = []
    answer_lower = answer.lower()

    for keyword in case.must_include:
        if keyword.lower() not in answer_lower:
            failures.append(f"缺少關鍵字: {keyword}")

    for keyword in case.must_not_include:
        if keyword.lower() in answer_lower:
            failures.append(f"命中禁用關鍵字: {keyword}")

    return (len(failures) == 0), failures


def _get_judge_chain() -> Any:
    global _judge_chain
    if _judge_chain is not None:
        return _judge_chain
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 GOOGLE_API_KEY，無法啟用 LLM judge。")
    judge_llm = ChatGoogleGenerativeAI(model=DEFAULT_JUDGE_MODEL, api_key=api_key)
    _judge_chain = judge_llm.with_structured_output(JudgeBinaryResult)
    return _judge_chain


def _judge_rubric(dimension: str, template: str) -> str:
    if dimension == "relevance":
        if template == "strict":
            return (
                "嚴格標準：回答需明確回應使用者問題核心，且不得偏題。"
                "若大多是空泛敘述、迴避主題或僅重述問題，判 0。"
            )
        return (
            "寬鬆標準：回答與問題主題整體相關即可判 1；"
            "若明顯離題才判 0。"
        )
    if dimension == "helpfulness":
        if template == "strict":
            return (
                "嚴格標準：回答需具體、可執行、有明確資訊增量；"
                "若只有空泛鼓勵、過短且無可行建議，判 0。"
            )
        return (
            "寬鬆標準：回答對使用者有基本幫助即可判 1；"
            "只有明顯無助時判 0。"
        )
    if dimension == "groundedness":
        if template == "strict":
            return (
                "嚴格標準：回答不得捏造事實、數字或來源；"
                "若缺乏根據時應明確表達不確定。任何明顯幻覺判 0。"
            )
        return (
            "寬鬆標準：只要沒有明顯捏造或過度武斷即可判 1；"
            "有明顯幻覺或錯誤斷言才判 0。"
        )
    raise ValueError(f"不支援的 judge 維度: {dimension}")


def _build_judge_prompt(
    *,
    dimension: str,
    template: str,
    user_input: str,
    answer: str,
    category: str,
    must_include: Any,
    must_not_include: Any,
    note: str,
) -> str:
    rubric = _judge_rubric(dimension, template)
    return (
        "你是嚴謹的 LLM 評測員，請依指定維度做二元評分。\n"
        "只輸出結構化欄位：score(0或1) 與 reason。\n\n"
        f"[Dimension]\n{dimension}\n\n"
        f"[Template]\n{template}\n\n"
        f"[Rubric]\n{rubric}\n\n"
        f"[Category]\n{category}\n\n"
        f"[User Input]\n{user_input}\n\n"
        f"[Model Answer]\n{answer}\n\n"
        f"[Golden must_include]\n{must_include}\n\n"
        f"[Golden must_not_include]\n{must_not_include}\n\n"
        f"[Golden note]\n{note}\n"
    )


def _is_retryable_exception(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    keywords = (
        "429",
        "resource_exhausted",
        "rate limit",
        "quota",
        "timeout",
        "temporarily unavailable",
        "service unavailable",
    )
    return any(keyword in text for keyword in keywords)


def _run_with_retry(
    *,
    label: str,
    fn: Any,
    retry_attempts: int,
    retry_max_wait_seconds: float,
) -> Any:
    start = time.perf_counter()
    for attempt in Retrying(
        stop=stop_after_attempt(retry_attempts),
        wait=wait_exponential_jitter(initial=1, max=retry_max_wait_seconds),
        retry=retry_if_exception(_is_retryable_exception),
        reraise=True,
    ):
        with attempt:
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 - 交由 retry predicate 判斷
                if _is_retryable_exception(exc):
                    n = attempt.retry_state.attempt_number
                    print(f"[retry] {label} attempt={n} error={type(exc).__name__}")
                raise
    elapsed = time.perf_counter() - start
    raise RuntimeError(f"{label} 重試後仍失敗（{elapsed:.2f}s）")


async def _ainvoke_answer(app: Any, *, case: GoldenCase, thread_prefix: str) -> str:
    out = await app.ainvoke(
        {"messages": [HumanMessage(content=case.user_input)]},
        config={
            "recursion_limit": DEFAULT_RECURSION_LIMIT,
            "configurable": {
                "thread_id": f"{thread_prefix}-{case.case_id.lower()}",
            },
        },
    )
    messages = out.get("messages") or []
    if not messages or not isinstance(messages[-1], AIMessage):
        raise RuntimeError("最後一則訊息不是 AIMessage")
    return _text_from_ai_message(messages[-1])


async def run_smoke(
    *,
    dataset_path: Path,
    limit: int | None,
    only_case_id: str | None,
) -> int:
    app = build_agent_graph()
    cases = _load_cases(dataset_path)

    if only_case_id:
        cases = [c for c in cases if c.case_id == only_case_id]
        if not cases:
            print(f"找不到 case_id={only_case_id}", file=sys.stderr)
            return 2

    if limit is not None:
        cases = cases[:limit]

    if not cases:
        print("沒有可執行的測試案例。", file=sys.stderr)
        return 2

    passed = 0
    failed = 0
    print(f"開始執行 M1 smoke，共 {len(cases)} 筆案例。")

    for index, case in enumerate(cases, start=1):
        try:
            answer = await _ainvoke_answer(
                app,
                case=case,
                thread_prefix="m1-smoke",
            )
        except Exception as exc:  # noqa: BLE001 - 教學腳本：將錯誤轉成案例失敗輸出
            failed += 1
            print(f"[{index:02d}] {case.case_id} FAIL: {exc}")
            continue

        ok, reasons = _check_case(case, answer)
        if ok:
            passed += 1
            print(f"[{index:02d}] {case.case_id} PASS ({case.category})")
        else:
            failed += 1
            print(f"[{index:02d}] {case.case_id} FAIL ({case.category})")
            for reason in reasons:
                print(f"       - {reason}")
            print(f"       - 回覆摘要: {answer[:160].replace(chr(10), ' ')}")

    print("\n=== M1 smoke summary ===")
    print(f"PASS: {passed}")
    print(f"FAIL: {failed}")
    print(f"TOTAL: {len(cases)}")
    return 0 if failed == 0 else 1


def _ensure_langsmith_dataset(
    *,
    client: Client,
    dataset_name: str,
    force_recreate: bool,
) -> tuple[str, bool]:
    created = False
    try:
        ds = client.read_dataset(dataset_name=dataset_name)
        if force_recreate:
            client.delete_dataset(dataset_id=ds.id)
            ds = client.create_dataset(
                dataset_name=dataset_name,
                description="LangGraph Learning M1 golden dataset for regression",
                metadata={"source": "evaluation/datasets/m1_golden_cases.json"},
            )
            created = True
    except LangSmithNotFoundError:
        ds = client.create_dataset(
            dataset_name=dataset_name,
            description="LangGraph Learning M1 golden dataset for regression",
            metadata={"source": "evaluation/datasets/m1_golden_cases.json"},
        )
        created = True
    return str(ds.id), created


def _list_existing_case_ids(client: Client, *, dataset_id: str) -> set[str]:
    existing: set[str] = set()
    for example in client.list_examples(dataset_id=dataset_id, limit=500):
        metadata = example.metadata or {}
        case_id = metadata.get("case_id")
        if isinstance(case_id, str) and case_id.strip():
            existing.add(case_id.strip())
    return existing


def _reference_output(case: GoldenCase) -> dict[str, Any]:
    return {
        "must_include": case.must_include,
        "must_not_include": case.must_not_include,
        "category": case.category,
        "note": case.note,
    }


def sync_langsmith_dataset(
    *,
    dataset_path: Path,
    dataset_name: str,
    force_recreate: bool,
) -> int:
    cases = _load_cases(dataset_path)
    client = Client()
    dataset_id, created = _ensure_langsmith_dataset(
        client=client,
        dataset_name=dataset_name,
        force_recreate=force_recreate,
    )
    existing_case_ids = _list_existing_case_ids(client, dataset_id=dataset_id)

    inserted = 0
    skipped = 0
    for case in cases:
        if case.case_id in existing_case_ids:
            skipped += 1
            continue
        client.create_example(
            dataset_id=dataset_id,
            inputs={"input": case.user_input},
            outputs=_reference_output(case),
            metadata={
                "case_id": case.case_id,
                "category": case.category,
                "source": "m1_golden_cases",
            },
        )
        inserted += 1

    print(f"Dataset: {dataset_name}")
    print(f"Dataset ID: {dataset_id}")
    print(f"Created: {created}")
    print(f"Inserted examples: {inserted}")
    print(f"Skipped examples: {skipped}")
    print("同步完成。")
    return 0


def _keyword_rule_evaluator(
    outputs: dict[str, Any],
    reference_outputs: dict[str, Any],
) -> dict[str, Any]:
    answer = str(outputs.get("answer", ""))
    must_include = [str(x) for x in reference_outputs.get("must_include", [])]
    must_not_include = [str(x) for x in reference_outputs.get("must_not_include", [])]

    temp_case = GoldenCase(
        case_id="eval",
        category=str(reference_outputs.get("category", "unknown")),
        user_input="",
        must_include=must_include,
        must_not_include=must_not_include,
        note=str(reference_outputs.get("note", "")),
    )
    ok, failures = _check_case(temp_case, answer)
    return {
        "key": "keyword_rule",
        "score": 1.0 if ok else 0.0,
        "comment": "PASS" if ok else "; ".join(failures),
    }


def _make_llm_judge_evaluator(dimension: str, template: str):
    def _evaluator(
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        reference_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        global _runtime_judge_disabled, _runtime_judge_disable_reason
        if _runtime_judge_disabled:
            return {
                "key": f"llm_judge_{dimension}",
                "comment": f"SKIPPED: fallback mode enabled ({_runtime_judge_disable_reason})",
            }
        user_input = str(inputs.get("input", ""))
        answer = str(outputs.get("answer", ""))
        category = str(reference_outputs.get("category", "unknown"))
        must_include = reference_outputs.get("must_include", [])
        must_not_include = reference_outputs.get("must_not_include", [])
        note = str(reference_outputs.get("note", ""))

        prompt = _build_judge_prompt(
            dimension=dimension,
            template=template,
            user_input=user_input,
            answer=answer,
            category=category,
            must_include=must_include,
            must_not_include=must_not_include,
            note=note,
        )
        judge_chain = _get_judge_chain()
        result = _run_with_retry(
            label=f"llm_judge_{dimension}",
            fn=lambda: asyncio.run(judge_chain.ainvoke(prompt)),
            retry_attempts=_runtime_retry_attempts,
            retry_max_wait_seconds=_runtime_retry_max_wait_seconds,
        )
        if not isinstance(result, JudgeBinaryResult):
            err = RuntimeError("LLM judge 回傳格式錯誤（非 JudgeBinaryResult）")
            if _runtime_fallback_to_keyword_on_judge_error:
                _runtime_judge_disabled = True
                _runtime_judge_disable_reason = str(err)
                print(f"[fallback] 關閉後續 LLM judge：{_runtime_judge_disable_reason}")
                return {
                    "key": f"llm_judge_{dimension}",
                    "comment": f"SKIPPED: {_runtime_judge_disable_reason}",
                }
            raise err
        return {
            "key": f"llm_judge_{dimension}",
            "score": float(result.score),
            "comment": result.reason.strip(),
        }
        
    def _safe_wrapper(
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        reference_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        global _runtime_judge_disabled, _runtime_judge_disable_reason
        try:
            return _evaluator(inputs, outputs, reference_outputs)
        except Exception as exc:  # noqa: BLE001 - 保底模式：降級為 keyword-only
            if _runtime_fallback_to_keyword_on_judge_error:
                _runtime_judge_disabled = True
                _runtime_judge_disable_reason = f"{type(exc).__name__}: {exc}"
                print(f"[fallback] 關閉後續 LLM judge：{_runtime_judge_disable_reason}")
                return {
                    "key": f"llm_judge_{dimension}",
                    "comment": f"SKIPPED: {_runtime_judge_disable_reason}",
                }
            raise

    _safe_wrapper.__name__ = f"_llm_judge_{dimension}_evaluator"
    return _safe_wrapper


def run_langsmith_eval(
    *,
    dataset_name: str,
    experiment_prefix: str,
    max_concurrency: int,
    sample_size: int | None,
    random_seed: int,
    enable_llm_judge: bool,
    llm_judge_template: str,
    llm_judge_dimensions: list[str],
    retry_attempts: int,
    retry_max_wait_seconds: float,
    fallback_to_keyword_on_judge_error: bool,
) -> int:
    client = Client()
    app = build_agent_graph()
    global _runtime_retry_attempts, _runtime_retry_max_wait_seconds
    global _runtime_fallback_to_keyword_on_judge_error
    global _runtime_judge_disabled, _runtime_judge_disable_reason
    _runtime_retry_attempts = retry_attempts
    _runtime_retry_max_wait_seconds = retry_max_wait_seconds
    _runtime_fallback_to_keyword_on_judge_error = fallback_to_keyword_on_judge_error
    _runtime_judge_disabled = False
    _runtime_judge_disable_reason = ""

    def target(inputs: dict[str, Any]) -> dict[str, Any]:
        user_input = str(inputs.get("input", ""))
        case = GoldenCase(
            case_id="runtime",
            category="runtime",
            user_input=user_input,
            must_include=[],
            must_not_include=[],
            note="",
        )
        answer = _run_with_retry(
            label="target_inference",
            fn=lambda: asyncio.run(
                _ainvoke_answer(
                    app,
                    case=case,
                    thread_prefix="m2-langsmith",
                )
            ),
            retry_attempts=retry_attempts,
            retry_max_wait_seconds=retry_max_wait_seconds,
        )
        return {"answer": answer}

    eval_data: str | list[Any] = dataset_name
    if sample_size is not None:
        all_examples = list(client.list_examples(dataset_name=dataset_name, limit=500))
        if not all_examples:
            print(f"Dataset `{dataset_name}` 沒有 examples。", file=sys.stderr)
            return 2
        k = min(sample_size, len(all_examples))
        rng = random.Random(random_seed)
        sampled_examples = rng.sample(all_examples, k=k)
        eval_data = sampled_examples
        sampled_case_ids = [
            str((example.metadata or {}).get("case_id", "unknown"))
            for example in sampled_examples
        ]
        print(
            "LangSmith eval 抽樣模式："
            f" sample_size={k}/{len(all_examples)} seed={random_seed}"
        )
        print(f"抽樣 case_id: {', '.join(sampled_case_ids)}")

    evaluator_list: list[Any] = [_keyword_rule_evaluator]
    if enable_llm_judge:
        for dimension in llm_judge_dimensions:
            evaluator_list.append(_make_llm_judge_evaluator(dimension, llm_judge_template))
    print(f"啟用 evaluators: {', '.join(e.__name__ for e in evaluator_list)}")
    print(
        "重試設定："
        f" attempts={retry_attempts}, max_wait_seconds={retry_max_wait_seconds}"
    )
    print(f"保底模式：fallback_to_keyword_on_judge_error={fallback_to_keyword_on_judge_error}")

    results = evaluate(
        target,
        data=eval_data,
        evaluators=evaluator_list,
        experiment_prefix=experiment_prefix,
        description="M2: evaluate M1 golden cases with keyword + optional llm-judge",
        max_concurrency=max_concurrency,
        client=client,
        blocking=True,
    )

    print("LangSmith evaluate 完成。")
    print(f"Experiment: {results.experiment_name}")
    print(f"URL: {results.url}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M1/M2/M3 evaluation helpers")
    parser.add_argument(
        "--mode",
        choices=["smoke", "sync-dataset", "langsmith-eval"],
        default="smoke",
        help="smoke: 本機測試；sync-dataset: 同步到 LangSmith；langsmith-eval: 在 LangSmith 跑 evaluation",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET_PATH,
        help="golden dataset json path",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="run first N cases only",
    )
    parser.add_argument(
        "--case-id",
        type=str,
        default=None,
        help="run only one case id (e.g., M1-003)",
    )
    parser.add_argument(
        "--dataset-name",
        type=str,
        default=DEFAULT_LANGSMITH_DATASET,
        help="LangSmith dataset name",
    )
    parser.add_argument(
        "--force-recreate",
        action="store_true",
        help="recreate LangSmith dataset before sync",
    )
    parser.add_argument(
        "--experiment-prefix",
        type=str,
        default=f"M2-keyword-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        help="LangSmith experiment prefix",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=1,
        help="max concurrency for LangSmith evaluate",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="LangSmith eval 抽樣筆數（例如 3）。不填則跑整個 dataset。",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="抽樣種子（固定後可重現同一批案例）",
    )
    parser.add_argument(
        "--enable-llm-judge",
        action="store_true",
        help="啟用 LLM-as-judge（可選 relevance/helpfulness/groundedness）並與 keyword_rule 雙軌評測",
    )
    parser.add_argument(
        "--llm-judge-template",
        choices=["strict", "lenient"],
        default=DEFAULT_JUDGE_TEMPLATE,
        help="LLM judge 評分模板：strict（嚴格）或 lenient（寬鬆）",
    )
    parser.add_argument(
        "--llm-judge-dimensions",
        type=str,
        default=DEFAULT_JUDGE_DIMENSIONS,
        help="逗號分隔的評測維度：relevance,helpfulness,groundedness",
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=DEFAULT_RETRY_ATTEMPTS,
        help="429/暫時性錯誤重試次數（target 與 judge 共用）",
    )
    parser.add_argument(
        "--retry-max-wait-seconds",
        type=float,
        default=DEFAULT_RETRY_MAX_WAIT_SECONDS,
        help="指數退避單次最大等待秒數（target 與 judge 共用）",
    )
    parser.add_argument(
        "--no-fallback-on-judge-error",
        action="store_true",
        help="關閉保底模式（預設開啟）：judge 失敗時不自動降級為 keyword-only",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.mode == "smoke":
        exit_code = asyncio.run(
            run_smoke(
                dataset_path=args.dataset,
                limit=args.limit,
                only_case_id=args.case_id,
            )
        )
    elif args.mode == "sync-dataset":
        if not os.getenv("LANGSMITH_API_KEY"):
            print("缺少 LANGSMITH_API_KEY，請先設定 .env。", file=sys.stderr)
            raise SystemExit(2)
        exit_code = sync_langsmith_dataset(
            dataset_path=args.dataset,
            dataset_name=args.dataset_name,
            force_recreate=args.force_recreate,
        )
    else:
        if not os.getenv("LANGSMITH_API_KEY"):
            print("缺少 LANGSMITH_API_KEY，請先設定 .env。", file=sys.stderr)
            raise SystemExit(2)
        if args.sample_size is not None and args.sample_size < 1:
            print("--sample-size 必須 >= 1", file=sys.stderr)
            raise SystemExit(2)
        dims = [x.strip().lower() for x in args.llm_judge_dimensions.split(",") if x.strip()]
        invalid_dims = [d for d in dims if d not in ALLOWED_JUDGE_DIMENSIONS]
        if invalid_dims:
            print(
                f"不支援的 --llm-judge-dimensions: {', '.join(invalid_dims)}",
                file=sys.stderr,
            )
            raise SystemExit(2)
        if args.enable_llm_judge and not dims:
            print("啟用 --enable-llm-judge 時，至少要有一個 judge 維度。", file=sys.stderr)
            raise SystemExit(2)
        if args.retry_attempts < 1:
            print("--retry-attempts 必須 >= 1", file=sys.stderr)
            raise SystemExit(2)
        if args.retry_max_wait_seconds <= 0:
            print("--retry-max-wait-seconds 必須 > 0", file=sys.stderr)
            raise SystemExit(2)
        exit_code = run_langsmith_eval(
            dataset_name=args.dataset_name,
            experiment_prefix=args.experiment_prefix,
            max_concurrency=args.max_concurrency,
            sample_size=args.sample_size,
            random_seed=args.random_seed,
            enable_llm_judge=args.enable_llm_judge,
            llm_judge_template=args.llm_judge_template,
            llm_judge_dimensions=dims,
            retry_attempts=args.retry_attempts,
            retry_max_wait_seconds=args.retry_max_wait_seconds,
            fallback_to_keyword_on_judge_error=not args.no_fallback_on_judge_error,
        )

    raise SystemExit(exit_code)
