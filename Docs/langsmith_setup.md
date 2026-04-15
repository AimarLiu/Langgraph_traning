# LangSmith 設定（本專案）

用於 **C3**：觀測 LangChain / LangGraph 執行過程（trace）、除錯與後續評估。  
官方總覽：[LangSmith](https://smith.langchain.com/)、[Tracing quickstart](https://docs.langchain.com/langsmith/observability-quickstart)。
你專案裡 langchain-core 已依賴 langsmith

---

## 1. 帳號與 API Key

1. 開啟 [smith.langchain.com](https://smith.langchain.com/) 註冊或登入。
2. 依官方步驟建立 **API Key**：[Create an API key](https://docs.langchain.com/langsmith/create-account-api-key#create-an-api-key)。
3. **勿**將 Key 提交到 Git；本專案 `.gitignore` 已包含 `.env`。

---

## 2. 環境變數（`.env`）

在專案根目錄 `.env` 新增（與 `GOOGLE_API_KEY` 並列即可）：

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=你的_LangSmith_API_Key
```

**選用：**

```env
LANGSMITH_PROJECT=LangGraph_Learning
```

未設定 `LANGSMITH_PROJECT` 時，trace 會進入工作區的預設 tracing 專案。

**多 workspace 時**（較少見）：可再設定 `LANGSMITH_WORKSPACE_ID`，見官方文件。

本專案腳本已使用 `load_dotenv()` 者會自動載入上述變數，**通常不需改程式**即可開始記錄 trace。

---

## 3. 依賴套件

`langsmith` 一般由 `langchain-core` 等套件帶入。若環境缺少，可執行：

```powershell
py -3.11 -m pip install langsmith
```

---

## 4. 驗證是否成功

1. 設定好 `.env` 後執行例如：

   ```powershell
   py -3.11 practice_04_agent_graph.py
   ```

2. 開啟 [LangSmith UI](https://smith.langchain.com/) → **Tracing** / **Projects**。
3. 應可看到新產生的 trace（含模型與工具相關 run）。

---

## 5. 與本專案 TODO（C3）的對應

| 目標 | 說明 |
|------|------|
| 還原工具選擇與參數 | 在 trace 中檢視 `tool_calls` 與子步驟 |
| 除錯 | 查看失敗步驟、延遲、錯誤訊息 |

進一步閱讀：**[Trace with LangGraph](https://docs.langchain.com/langsmith/trace-with-langgraph)**。

---

## 6. 關閉 LangSmith 時的本機 logging

若已關閉 tracing，仍可在終端機用 **Python `logging`** 觀察流程；開關為 **`AGENT_LOGGING`**，見 **`Docs/logging_setup.md`** 與 **`src/langgraph_learning/agent_logging.py`**。

---

## 7. 隱私與正式環境

- Trace 可能包含 **提示詞與模型輸出**；敏感資料請評估是否僅在開發機啟用 `LANGSMITH_TRACING`。
- 正式環境可改為僅在需要時開啟 tracing，或依 LangSmith 方案調整資料保留策略。

---

*文件隨專案練習更新；變數名稱以 [LangChain 文件](https://docs.langchain.com/langsmith/observability-quickstart) 為準。*
