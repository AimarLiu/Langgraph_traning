"""I1：子圖拆分最小可跑範例（研究 -> 回覆）。"""

from __future__ import annotations

import path_setup

path_setup.add_src_to_path()

from langgraph_learning.pipelines.i1_subgraphs import build_i1_outer_graph


def main() -> None:
    app = build_i1_outer_graph()
    out = app.invoke(
        {
            "question": "請摘要 USD/THB 與 ETHUSDT 最新資料",
            "intent": "market_summary",
            "market_snapshot": {},
            "final_response": "",
            "errors": [],
        },
        config={"recursion_limit": 8},
    )
    print("=== I1 子圖拆分示範 ===")
    print("market_snapshot:")
    for k, v in sorted(out["market_snapshot"].items()):
        print(f"  - {k}: {v}")
    if out["errors"]:
        print("errors:")
        for err in out["errors"]:
            print(f"  - {err}")
    print("\nfinal_response:")
    print(out["final_response"])
    assert out["market_snapshot"] or out["errors"], "需要有資料或錯誤資訊"
    assert "問題：" in out["final_response"]
    print("\nI1 OK：研究子圖與回覆子圖可由外層圖組合執行。")


if __name__ == "__main__":
    main()
