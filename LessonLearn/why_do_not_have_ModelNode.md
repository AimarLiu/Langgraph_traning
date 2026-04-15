# 有 `ToolNode`，那有沒有 `ModelNode`？

## 結論

在 **LangGraph** 裡**沒有**和 `ToolNode` 對仗、名叫 **`ModelNode`** 的預建類別（在常見版本的 `langgraph` 套件中也不會看到這個名稱）。

---

## 為什麼有 `ToolNode` 卻沒有 `ModelNode`？

### `ToolNode` 在做什麼

- 工具呼叫的**流程形狀**相對固定：依最後一則 `AIMessage` 的 **`tool_calls`** → 執行對應工具 → 產生 **`ToolMessage`**。
- 因此官方把它包成一個**可重複使用的節點**（`langgraph.prebuilt.ToolNode`），減少大家重複寫同一套邏輯。

### 「叫模型」這一步為何通常不包成 `ModelNode`

- 實務上差異很大：要不要 **`bind_tools`**、訊息列表怎麼組、要不要 **streaming**、要不要自訂 **prompt / 回呼 / 結構化輸出** 等，每個專案都不同。
- 常見做法是：自己寫一個**函式當節點**（例如專案裡的 `call_model`），或使用 **`create_react_agent` / `create_agent`** 等高階 API，由框架幫你接好 LLM 與工具迴圈。

### 一句話

**沒有名叫 `ModelNode` 的預建類別**；**「模型節點」在概念上就是你自訂的 node，或由高階 agent 幫你產生的那一步**，而不是與 `ToolNode` 成對的另一個官方類別。

---

## 和本專案練習的對應

| 概念 | 本專案中的寫法 |
|------|----------------|
| 工具執行節點 | `ToolNode(_tools)` 或手寫 `run_tools`（見 `practice_04_agent_graph.py` 註解） |
| 呼叫模型的節點 | 自訂 **`call_model(state)`** |

---

*僅為概念整理，API 名稱以你安裝的 `langgraph` 版本文件為準。*
