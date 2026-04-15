# 迷你課表：會用工具的任務代理（Tool-using Agent）

> 目標：用 **LangGraph** 組出有 **狀態**、**工具呼叫**、**可終止** 的最小任務代理，再逐步加上錯誤處理與觀測。  
> 前置：已完成 `practice_01.py`（`StateGraph` + `START` / `END` + 狀態 reducer）。

---

## 模型供應商（沒有 OpenAI 付費時）

| 方向 | 說明 | 與本專案整合 |
|------|------|----------------|
| **Google Gemini（推薦先試）** | [Google AI Studio](https://aistudio.google.com/) 可申請 API Key；免費層有 **RPM / RPD 配額**（會隨政策調整）。正式條款與計費見官方：[Gemini API 定價](https://ai.google.dev/gemini-api/docs/pricing)、[計費說明](https://ai.google.dev/gemini-api/docs/billing)。 | LangChain 需另裝 **`langchain-google-genai`**（或官方 `google-genai` SDK），程式裡用 `ChatGoogleGenerativeAI` 等，而非 `ChatOpenAI`。 |
| **Groq** | 常有 **免費額度**、延遲低；適合練習與原型（額度以官網為準）。 | 可裝 **`langchain-groq`**，使用 `ChatGroq`。 |
| **本機 Ollama** | 不需雲端 API 金鑰；模型在自己電腦跑，適合離線與隱私練習。 | 可裝 **`langchain-ollama`** 等整合套件，端點設本機。 |
| **OpenAI** | 新帳戶是否贈送試用額度 **依官方當期活動與地區而變**，沒有保證；沒付費時不必執著，先用上列其一即可。 | 你目前已裝 **`langchain-openai`**，日後有 Key 再切換最省事。 |

**實務建議**：先選 **Gemini 或 Groq** 其中一個拿到 Key → 用 **`.env`** 存 `GOOGLE_API_KEY` 或 `GROQ_API_KEY` → 課表裡的「呼叫模型」步驟改為對應的 Chat 類別。

---

## 課表（建議順序）

### 階段 A：單輪工具概念（不先上完整 Agent 迴圈）

- [x] **A1** 在獨立腳本裡用你選的供應商完成：**一則 user 訊息 → 模型回覆**（同步 `invoke` 即可）。
- [x] **A2** 用 LangChain 定義 **1 個 `@tool`**（例如：查目前 UTC 時間、或「假裝查訂單狀態」的函式），手動在程式裡呼叫一次，確認回傳格式。
- [x] **A3** 用 **`bind_tools`**（或等效 API）讓模型對簡單輸入產生 **tool_calls**，你在程式裡 **解析並執行工具**，再把 **ToolMessage** 塞回對話（先寫「手動迴圈」一輪即可）。

### 階段 B：LangGraph 包住「想 → 用工具 → 再答」

- [x] **B1** 定義 `AgentState`：`messages` 用 `Annotated[..., add_messages]`（LangGraph 慣用訊息累加方式）。
- [x] **B2** 節點 **`call_model`**：載入 Chat 模型，**bind_tools**，回傳 `{"messages": [ai_message]}`。
- [x] **B3** 節點 **`run_tools`**：讀取最後一則 AI 訊息的 `tool_calls`，執行對應工具，回傳 **ToolMessage** 列表更新 state。
- [x] **B4** **條件邊**：若還有 tool_calls → 進 `run_tools` → 再回到 `call_model`；若沒有 → `END`。並設 **最大步數** 防止無限迴圈。

### 階段 C：像「任務代理」一點

- [x] **C1** 再加 **第 2 個工具**（例如計算機或查本地 JSON 假資料），練習「模型在兩者間選擇」。
- [x] **C2** 為工具加上 **輸入驗證** 與 **逾時／例外** 處理，錯誤以清楚字串回給模型。
- [x] **C3**（選修）接上 **LangSmith** 或自訂 logging，能從 log 還原每一輪的 tool 選擇與參數。

### 階段 D：整理成可複用專案結構

- [x] **D1** 將工具集中放在例如 `src/tools/`（或 `tools/`），圖的定義放在 `src/graphs/`。
- [x] **D2** 在 `Docs/` 補一段「如何設定環境變數與執行範例」；依需要更新 `Docs/requirements.txt`（新增 `langchain-google-genai` 或 `langchain-groq` 等）。

---

## 建議對應檔名（可依喜好調整）

| 檔案 | 用途 |
|------|------|
| `practice_02_model_smoke.py` | A1：單次對話煙霧測試 |
| `practice_03_tool_manual.py` | A2–A3：工具 + 手動一輪 tool loop |
| `practice_04_agent_graph.py` | B1–B4：LangGraph 任務代理骨架 |
| `practice_05_agent_two_tools.py` | C1–C2：雙工具與錯誤處理 |

---

## 完成標準（自我檢查）

1. 給一句需要工具的問題（例如「現在幾點？」），代理能 **呼叫對應工具** 並用自然語言總結。  
2. 給一句不需要工具的閒聊，代理能 **直接回答**、不亂呼叫工具。  
3. 故意給會讓工具失敗的輸入，程式 **不崩潰**，且模型仍能得到錯誤說明並回覆使用者。  

---

*課表可隨你進度勾選 `[ ]` → `[x]`；若你確定選用的供應商，可把「環境變數名稱與套件」寫在 `Docs` 裡固定下來。*

---

## 下一階段學習

- **第二課表（進階）**：持久化、人機協作、串流、狀態擴充、子圖／路由、RAG 入門 → 見 **`TODO_phase2.md`**。  
- **第三課表（產品化）**：非同步、FastAPI、評測回歸、RAG 加深、督導路由、選修跨 thread 記憶 → 見 **`TODO_phase3.md`**。
