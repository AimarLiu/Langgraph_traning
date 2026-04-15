# 環境變數與執行方式

## 目錄結構（階段 D）

- **`src/langgraph_learning/`**：可 import 的套件（`tools`、`graphs`、`agent_logging`）。
- **專案根目錄**：`practice_*.py` 為薄入口；執行前會透過 **`path_setup.add_src_to_path()`** 把 `src` 加入 `sys.path`。
- **選用**：在專案根目錄執行 `py -3.11 -m pip install -e .` 後，可不依賴 `path_setup`，直接 `import langgraph_learning`。

---

## 環境變數總表

| 變數 | 必填 | 說明 |
|------|------|------|
| **`GOOGLE_API_KEY`** | 是（Gemini 練習） | [Google AI Studio](https://aistudio.google.com/) 取得；供 `ChatGoogleGenerativeAI`。 |
| **`LANGSMITH_TRACING`** | 否 | 設 `true` 啟用 LangSmith trace（見 `Docs/langsmith_setup.md`）。 |
| **`LANGSMITH_API_KEY`** | 與 tracing 搭配 | LangSmith 專案 API Key。 |
| **`LANGSMITH_PROJECT`** | 否 | Trace 歸入的專案名稱。 |
| **`AGENT_LOGGING`** | 否 | `true` / `1` / `yes` / `on` 啟用本機 stderr 日誌（見 `Docs/logging_setup.md`）。 |
| **`AGENT_LOGGING_LEVEL`** | 否 | 預設 `INFO`；可設 `DEBUG` 看每則訊息類型。 |
| **`MODEL_MAX_TOKENS`** | 否 | H4 前處理：`trim_messages` 的 `max_tokens`。預設 `20`。 |
| **`MODEL_TRIM_STRATEGY`** | 否 | H4 前處理：`trim_messages` 策略，`last` 或 `first`。預設 `last`。 |
| **`MODEL_TRIM_INCLUDE_SYSTEM`** | 否 | H4 前處理：是否保留最前面的 `SystemMessage`。預設 `true`。 |
| **`MODEL_TRIM_START_ON`** | 否 | H4 前處理：`trim_messages(start_on=...)`，常用 `human`；留空代表不限制。 |
| **`MODEL_EXCLUDE_TYPES`** | 否 | H4 前處理：`filter_messages(exclude_types=...)`，逗號分隔（例如 `tool,ai`）。 |

請將實際值寫在專案根目錄 **`.env`**（勿提交；已列於 `.gitignore`）。範本：**`.env.example`**。

---

## H4 訊息前處理（filter -> trim）建議設定

`src/langgraph_learning/graphs/agent_graph.py` 的 `preprocess_messages_for_model()` 會先 `filter_messages`、再 `trim_messages`。  
若要調整上下文長度與保留規則，建議在 `.env` 設定：

```env
MODEL_MAX_TOKENS=20
MODEL_TRIM_STRATEGY=last
MODEL_TRIM_INCLUDE_SYSTEM=true
MODEL_TRIM_START_ON=human
MODEL_EXCLUDE_TYPES=
```

### 什麼時候要調整

- 回答常忘記較早上下文：提高 `MODEL_MAX_TOKENS`。
- 成本偏高或延遲上升：降低 `MODEL_MAX_TOKENS`。
- 發現工具輸出塞爆上下文：`MODEL_EXCLUDE_TYPES=tool`。
- 模型常從 AI/工具訊息中段開始理解：維持 `MODEL_TRIM_START_ON=human`。
- 有強 system 規則不應遺失：維持 `MODEL_TRIM_INCLUDE_SYSTEM=true`。

---

## 依賴還原

```powershell
cd <專案根目錄>
py -3.11 -m pip install -r Docs/requirements.txt
```

可選：可編輯安裝本套件（方便 IDE 與其他腳本 import）：

```powershell
py -3.11 -m pip install -e .
```

---

## 執行範例（專案根目錄）

```powershell
py -3.11 practice_01.py
py -3.11 practice_02_model_smoke.py
py -3.11 practice_03_tool_manual.py
py -3.11 practice_04_agent_graph.py
py -3.11 practice_06_checkpoint_memory.py
```

第二課表 E1（`SqliteSaver`）會在專案根目錄建立 `data/langgraph_checkpoints.sqlite`；請勿將含敏感內容的 checkpoint 提交版本庫（已列於 `.gitignore`）。

E3 選用 **`--replay`** 會多一次模型呼叫（示範 Replay）：`py -3.11 practice_06_checkpoint_memory.py --replay`。

需已設定 **`GOOGLE_API_KEY`**；若網路會呼叫 Frankfurter／Binance 公開 API。

---

## 相關文件

| 主題 | 檔案 |
|------|------|
| LangSmith | `Docs/langsmith_setup.md` |
| 本機 logging | `Docs/logging_setup.md` |
| 依賴鎖檔 | `Docs/requirements.txt` |
| Checkpointer 與常駐服務生命週期（K3） | `Docs/checkpointer_in_services.md` |
