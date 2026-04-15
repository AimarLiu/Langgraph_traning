"""I2：LLM structured output 意圖分類 + 條件路由（閒聊／查價／申訴）。"""

from __future__ import annotations

import json
import sys

import path_setup

path_setup.add_src_to_path()

from langgraph_learning.pipelines.i2_intent_router import (
    IntentClassification,
    build_i2_intent_router_graph,
    classify_intent_structured,
)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


def _empty_state(user_message: str) -> dict:
    return {
        "user_message": user_message,
        "intent": "",
        "intent_reason": "",
        "question": "",
        "market_snapshot": {},
        "final_response": "",
        "errors": [],
    }


def _print_structured(title: str, parsed: IntentClassification) -> None:
    print(title)
    # parsed.model_dump() will output JSON format that you specify in IntentClassification
    print(json.dumps(parsed.model_dump(), ensure_ascii=False, indent=2))


def main() -> None:
    samples = [
        "今天天氣不錯，聊兩句吧",
        "ETH 現在價格與 USD 換 THB 匯率多少？",
        "我要申訴：上週訂單延遲且客服態度很差",
    ]

    print("=== I2：僅分類模型（structured output）===\n")
    for msg in samples:
        parsed = classify_intent_structured(msg)
        _print_structured(f"輸入：{msg!r}", parsed)
        print()

    app = build_i2_intent_router_graph()

    print("--- stream_mode=updates（第一則）：節點完成順序 ---\n")
    for i, chunk in enumerate(
        app.stream(
            _empty_state(samples[0]),
            stream_mode="updates",
            config={"recursion_limit": 12},
        )
    ):
        print(f"[{i}] {chunk!r}")
    print()

    print("--- 完整 invoke（查價分支會再打市場 API）---\n")
    for msg in samples:
        out = app.invoke(_empty_state(msg), config={"recursion_limit": 12})
        print("---")
        print(f"intent={out.get('intent')!r}")
        print(f"intent_reason={out.get('intent_reason')!r}")
        print(out.get("final_response", ""))
        print()

    valid: set[str] = {"chat", "price", "complaint"}
    for msg in samples:
        p = classify_intent_structured(msg)
        assert p.intent in valid
    print("I2 OK：分類為 LLM structured output；可查 intent_reason 與 stream 節點順序。")


if __name__ == "__main__":
    main()
