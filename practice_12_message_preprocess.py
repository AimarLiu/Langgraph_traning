"""H4：官方 filter/trim 訊息前處理最小可跑範例（離線）。

目標：
1) 先用 filter_messages 去掉不需要的訊息（例如 tool）
2) 再用 trim_messages 依 token 規則保留最近上下文
3) 示範 include_system/start_on 等常見選項

執行：
    py -3.11 practice_12_message_preprocess.py
"""

from __future__ import annotations

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    filter_messages,
    trim_messages,
)


def _show(title: str, messages: list) -> None:
    print(f"\n=== {title}（{len(messages)} 則）===")
    for i, m in enumerate(messages):
        role = type(m).__name__
        content = str(getattr(m, "content", ""))
        print(f"{i:02d} {role}: {content}")


def build_sample_messages() -> list:
    return [
        SystemMessage(content="你是繁中助理，回答要精簡。"),
        HumanMessage(content="先查 ETH 價格"),
        AIMessage(content="我要呼叫工具。"),
        ToolMessage(content='{"price":"3500"}', tool_call_id="call_1"),
        HumanMessage(content="再比較 BTC"),
        AIMessage(content="我再呼叫工具。"),
        ToolMessage(content='{"price":"62000"}', tool_call_id="call_2"),
        HumanMessage(content="最後請摘要"),
    ]


def pipeline_filter_then_trim(messages: list) -> list:
    # Step 1: 先移除 tool 結果，讓模型上下文以人類/AI 對話為主
    filtered = filter_messages(messages, exclude_types=(ToolMessage,))

    # Step 2: 用 token 規則裁剪
    # 這裡用 token_counter=len 當教學替代（每則訊息視為 1 token 單位）
    # 實務可改成模型 tokenizer 或 llm 物件。
    trimmed = trim_messages(
        filtered,
        max_tokens=4,
        token_counter=len,
        strategy="last",
        include_system=True,
        start_on="human",
    )
    return trimmed


def main() -> None:
    messages = build_sample_messages()
    _show("原始訊息", messages)

    preprocessed = pipeline_filter_then_trim(messages)
    _show("H4 前處理後", preprocessed)

    # 斷言 1：tool 訊息應被濾掉
    assert all(not isinstance(m, ToolMessage) for m in preprocessed)
    # 斷言 2：保留 system（若原本有）
    assert isinstance(preprocessed[0], SystemMessage)
    # 斷言 3：只留最近上下文（以 max_tokens=4 + include_system=True）
    assert len(preprocessed) <= 5
    assert isinstance(preprocessed[-1], HumanMessage)
    assert preprocessed[-1].content == "最後請摘要"

    print("\nH4 OK：filter_messages + trim_messages pipeline 可用。")


if __name__ == "__main__":
    main()
