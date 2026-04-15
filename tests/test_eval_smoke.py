from __future__ import annotations

import asyncio
from pathlib import Path

import practice_15_eval_smoke as eval_smoke


def test_load_cases_reads_golden_dataset() -> None:
    cases = eval_smoke._load_cases(eval_smoke.DATASET_PATH)

    assert len(cases) >= 10
    assert cases[0].case_id
    assert cases[0].user_input is not None


def test_check_case_pass_and_fail() -> None:
    case = eval_smoke.GoldenCase(
        case_id="TEST-001",
        category="unit",
        user_input="hello",
        must_include=["LangGraph"],
        must_not_include=["forbidden"],
        note="",
    )

    ok, failures = eval_smoke._check_case(case, "LangGraph is useful.")
    assert ok is True
    assert failures == []

    ok, failures = eval_smoke._check_case(case, "this includes forbidden")
    assert ok is False
    assert len(failures) >= 2


def test_run_smoke_without_model_by_monkeypatch(monkeypatch, tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(
        """
[
  {
    "id": "T-001",
    "category": "offline",
    "input": "ping",
    "must_include": ["ok"],
    "must_not_include": ["error"],
    "note": "offline smoke"
  }
]
""".strip(),
        encoding="utf-8",
    )
    # return a dummy object
    monkeypatch.setattr(eval_smoke, "build_agent_graph", lambda: object())

    async def _fake_ainvoke_answer(app, *, case, thread_prefix):  # noqa: ANN001
        _ = app, case, thread_prefix
        return "ok"

    monkeypatch.setattr(eval_smoke, "_ainvoke_answer", _fake_ainvoke_answer)

    exit_code = asyncio.run(
        eval_smoke.run_smoke(dataset_path=dataset_path, limit=None, only_case_id=None)
    )

    assert exit_code == 0
