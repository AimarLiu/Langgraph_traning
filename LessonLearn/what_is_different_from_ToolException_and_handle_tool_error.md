# 工具錯誤：`回傳 _tool_error()` 字串` 與 `ToolException`／`handle_tool_error` 差在哪？

LangChain 的 **`StructuredTool`**（含 `@tool` 產生的工具）在「工具執行失敗」時，常見兩種風格。本專案市場工具（`src/langgraph_learning/tools/market.py`）採用的是**第一種**；第二種是文件與社群常見的 **`ToolException`** 搭配 **`handle_tool_error`**。兩者可以並存，不是二選一，但**責任邊界與 trace 長相**不同。

---

## 在解決同一個問題嗎？

都在處理：**工具呼叫後，要把什麼內容交回給模型（與框架）**，以及 **失敗時要不要讓整段圖「炸掉」**。

差別在於：失敗被記成「**一般成功的 tool 輸出字串**」，還是走「**工具例外管線**」變成帶 **`status="error"`** 的 `ToolMessage`（並可由 `handle_tool_error` 統一整形）。

---

## 做法一：在工具內回傳錯誤 JSON 字串（例如 `_tool_error()`）

**行為**：不 `raise`，最後 `return json.dumps({... "error": ...})`。

**框架怎麼看**：對 LangGraph `ToolNode`／LangChain 而言，這是一次**成功**的工具執行；產生的 `ToolMessage` **內容**就是你的 JSON 字串，通常 **`status` 仍是成功語意**（依版本預設為 `"success"` 或未標錯誤）。

**優點**

- 模型看到的格式**完全由你控制**（例如固定 `{"error": "...", "allowed": [...]}`），方便在 system prompt 裡規定「看到 `error` 就換策略／簡短回覆使用者」。
- 白名單、HTTP 4xx/5xx、逾時等**可預期**失敗，用同一套結構表達，**行為可預測**。

**缺點**

- 在 LangSmith 等 trace 裡，這類結果**不一定**會被標成「工具執行失敗」，較像「工具回了一段文字」；要區分「業務錯誤」與「程式 bug」較依賴**約定好的 JSON schema**。
- 若希望與「例外＝失敗」的監控／告警對齊，需要自己再包一層語意。

---

## 做法二：`raise ToolException(...)` + `StructuredTool(..., handle_tool_error=...)`

**行為**：在工具裡對「要交給模型／使用者的失敗」**丟出 `ToolException`**（或讓特定例外往外傳），由 **`handle_tool_error`** 決定最後變成什麼字串、是否隱藏堆疊等。

**框架怎麼看**：LangChain 會依設定把例外轉成 **`ToolMessage`**，且常見情況下會帶 **`status="error"`**，與「成功帶回內容」在結構上區分較清楚；LangGraph 的 `ToolNode` 也與這條錯誤路徑整合。

**`handle_tool_error` 常見形態（概念）**

- `True`：用預設方式把例外變成可讀訊息（細節依版本）。
- 字串模板：統一格式。
- **Callable**：自己把 `Exception` 轉成要給模型的字串（這裡可以**仍回傳與 `_tool_error()` 相同格式的 JSON**，等於只換「進入點」）。

**優點**

- **語意**：明確表達「這次工具呼叫失敗」，與監控、除錯、UI 顯示「錯誤」較一致。
- 可集中處理「**不要**把原始 stack trace 或敏感訊息直接餵給模型」。

**缺點**

- 若未自訂 callable，模型看到的字串格式**可能**與你原本的 JSON 不同，需在 prompt 裡重新約定，或在 `handle_tool_error` 裡**固定成 JSON**。
- 需分清：`ToolException` 適合「可預期、要讓模型知道失敗原因」的情境；**濫用**可能讓所有錯誤看起來一樣，反而難除錯。

---

## 對照表（複習用）

| 維度 | 回傳 `_tool_error()` 字串 | `ToolException` + `handle_tool_error` |
|------|---------------------------|--------------------------------------|
| 執行結果在框架眼中 | 多為「成功執行完工具」 | 走「錯誤處理」路徑，常對應 `ToolMessage` **error** 狀態 |
| 給模型的內容誰決定 | 工具內完全自定（JSON） | 預設依框架；可 **callable** 自定（也可輸出同款 JSON） |
| Trace／觀測 | 像一般 tool 輸出 | 較容易對齊「工具失敗」的觀測習慣 |
| 與本專案既有 prompt | 已假設 JSON 錯誤格式時，最直覺 | 需在例外路徑**維持相同字串格式**，或改 prompt |

---

## 實務上怎麼選？（與本專案）

1. **維持現有 `_tool_error()`** 在教學與可讀性上完全合理，尤其是**白名單、API 業務錯誤**。
2. 若想**對齊 ToolMessage 錯誤狀態與 trace**，可逐步改為：在錯誤路徑 **`raise ToolException(_tool_error(...))`**，並設定 **`handle_tool_error`** 為 callable，**原樣回傳** `ToolException` 的訊息（已是你的 JSON），這樣**模型輸入形狀不變**，框架語意較清楚。
3. **不要**認為必須二選一：**預期錯誤**用 JSON 或 `ToolException` 包同一串 JSON；**未預期 bug** 可交給 `handle_tool_error` 避免把 raw exception 餵給模型。

---

## 一句話整理

- **`_tool_error()`**：把錯誤當成**設計好的工具輸出**，簡單、穩定，但「失敗」在 trace 裡不那麼顯眼。  
- **`ToolException` + `handle_tool_error`**：把錯誤當成**工具失敗事件**來管，較利於觀測與安全預設；若要維持模型端格式，請在 **`handle_tool_error`**（或 `ToolException` 的訊息）裡**對齊你現有的 JSON 約定**。

---

*本說明整理自學習過程中的比較，方便與 `market.py` 等工具實作對照複習。*
