# 本機 Logging 開關（不依賴 LangSmith）

當 **LangSmith tracing** 關閉時，仍可用標準 **`logging`** 在終端機（預設 **stderr**）看到代理流程摘要。  
實作集中在套件 **`langgraph_learning.agent_logging`**（檔案：`src/langgraph_learning/agent_logging.py`），由環境變數 **`AGENT_LOGGING`** 控制是否輸出。

---

## 環境變數

| 變數 | 說明 |
|------|------|
| **`AGENT_LOGGING`** | 設為 `true` / `1` / `yes` / `on`（不分大小寫）→ **啟用**；未設或其他值 → **關閉** |
| **`AGENT_LOGGING_LEVEL`** | 選用，預設 `INFO`。若要印出每則訊息類型的 **DEBUG** 列，可設為 `DEBUG` |

### `.env` 範例

```env
# 關閉（與不寫這行效果相同）
# AGENT_LOGGING=false

# 啟用
AGENT_LOGGING=true

# 選用：更細的列（含每則 message 類型與 tool_calls）
# AGENT_LOGGING_LEVEL=DEBUG
```

---

## 程式中如何使用

1. 在 **`load_dotenv()` 之後** 呼叫一次：

   ```python
   from langgraph_learning.agent_logging import configure_agent_logging, get_agent_logger

   configure_agent_logging()
   log = get_agent_logger(__name__)
   ```

2. 使用 `log.info(...)`、`log.debug(...)` 等；**關閉**時這些不會出現在 stderr（logger 等級被拉高）。

3. **不要**在 log 中寫入 API Key、Token、完整使用者內容（必要時只記錄長度或前幾字）。

---

## 目前哪裡有記錄？

**`src/langgraph_learning/graphs/agent_graph.py`**（根目錄 **`practice_04_agent_graph.py`** 為入口）：

- `graph.invoke` 前後（含 `recursion_limit`、訊息總則數）
- 每次 **`call_model`**：輸入訊息則數、是否有 `tool_calls` 及工具名稱
- **`DEBUG`**：逐步列出每則訊息類型（需在 `AGENT_LOGGING_LEVEL=DEBUG` 時才會顯示）

**ToolNode** 內部若未加自訂 log，仍只會看到「進入 call_model」等節點層級；要更細可之後再加 **callback** 或包一層節點。

---

## 與 LangSmith 的關係

- **LangSmith**：雲端 trace UI，需 `LANGSMITH_*` 變數。  
- **本機 logging**：僅終端機輸出，由 **`AGENT_LOGGING`** 控制。  
兩者可同開或只開其一，互不衝突。

---

*設定細節以 `src/langgraph_learning/agent_logging.py` 為準。*
