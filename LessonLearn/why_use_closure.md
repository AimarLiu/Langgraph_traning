# 為什麼把 `call_model` 寫在 `build_agent_graph` 裡面？（閉包）

## 結論

在 `build_agent_graph` 裡用 `def call_model(...)`，是 Python 的**巢狀函式／閉包（closure）**：讓節點函式能**自動帶上「這次建圖」才決定的物件**（主要是已 `bind_tools` 的 `llm_bound`），同時維持 LangGraph 節點慣用的 **`(state) -> 更新 dict`** 簽名。

對應程式：`src/langgraph_learning/graphs/agent_graph.py` 的 `build_agent_graph`。

---

## 為什麼要這樣寫？

### 1. 綁定當次的 LLM 與工具

`build_agent_graph` 會依參數組出：

- `tool_list`：這次要給代理用的工具
- `llm_bound = llm.bind_tools(tool_list)`：已綁定工具的 runnable
- `node_tools = ToolNode(tool_list)`：執行工具的另一個節點

`call_model` 內部呼叫的是 **`llm_bound.invoke(...)`**，而不是模組層那個未綁工具的 `llm`。若把 `call_model` 寫成**模組頂層函式**，就必須額外傳入 `llm_bound`（或工具清單），或改用**全域可變狀態**，都不如閉包直觀。

### 2. 符合 LangGraph 節點介面

`g.add_node("call_model", call_model)` 預期的是「吃 `state`、回傳狀態更新」的 callable。用閉包把 `llm_bound`「藏」在外層，節點仍只要一個 `state` 參數，不必改框架約定的形狀。

### 3. 每次 `build_agent_graph(...)` 各有一份

不同呼叫若傳入不同 `tools`，會得到不同的 `llm_bound` 與 `ToolNode`；巢狀定義的 `call_model` 各自**閉包到自己的 `llm_bound`**，不會跨實例互相覆蓋。

---

## 閉包大致「抓到」什麼？

在 `call_model` 本體裡會用到：

| 類型 | 說明 |
|------|------|
| **外層區域（每次建圖不同）** | `llm_bound`（以及與其一致的 `tool_list` 概念） |
| **模組層** | `preprocess_messages_for_model`、`_logger`、`MODEL_FILTER_EXCLUDE_TYPES`、`MAX_MODEL_TOKENS` 等 |

其中**最值得用閉包保存**的，是隨 `build_agent_graph(tools=...)` 變動的 **`llm_bound`**。

---

## 替代寫法（語意相同）

也可以把 `call_model` 寫成**頂層函式**，例如：

```python
def call_model(state: AgentState, llm_bound: Runnable) -> dict[str, Any]:
    ...
```

註冊節點時用 `functools.partial(call_model, llm_bound=llm_bound)` 先綁好再 `add_node`。效果與巢狀 `def` 閉包相同，只是風格不同。

---

## 一句話

**`call_model` 放在 `build_agent_graph` 裡，是為了閉包住當次的 `llm_bound`（與工具），節點介面仍是 `state` 單參數，且每次建圖互不影響。**

## 再一句
> 兩種做法都說得通：閉包／partial 比較清楚表達「這張圖專用這份 llm_bound」；模組層全域 則在「整個程式永遠只有一組工具／一個綁定」時寫起來最短，但要小心多實例或測試時互相影響。
---

*僅為概念整理；實際行為以你專案中的 `agent_graph.py` 與安裝的 `langgraph` 版本為準。*
