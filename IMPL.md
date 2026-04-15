# 實作紀錄

## Phase：學習課表與供應商指引

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| 迷你課表 | 以「會用工具的任務代理」為主軸的階段任務；含無 OpenAI 時的模型供應商建議與建議檔名 | `TODO.md` |
| 學習筆記：型別與 annotation | 說明「型別」與「型別註解／標註」用詞差異；補充 `from __future__ import annotations` | `LessonLearn/what_is_annotation.md` |
| 學習筆記：ToolNode import | `ServerInfo` 缺失原因、`langgraph` 升級建議、手寫 `run_tools` 替代 | `LessonLearn/why_can_not_import_ToolNode.md` |
| 學習筆記：無 ModelNode | 為何有 `ToolNode` 而沒有對應的 `ModelNode`；與自訂 `call_model` 的關係 | `LessonLearn/why_do_not_have_ModelNode.md` |
| 學習筆記：為何用閉包 | `build_agent_graph` 內巢狀定義 `call_model` 的原因（閉包 `llm_bound`、節點簽名、每次建圖隔離）；`partial` 替代寫法 | `LessonLearn/why_use_closure.md` |
| 學習筆記：長／短記憶 | Checkpoint（含 DB）與 Store+namespace 的差異、定址方式與使用時機 | `LessonLearn/what_is_different_between_long_short_memories.md` |
| 學習筆記：F2 指令恢復 | `invoke(None)`、`Command(update/goto)` 的核准／拒絕／改參流程與注意事項 | `LessonLearn/how_to_use_f2_lesson_command.md` |
| 學習筆記：AIMessageChunk | `stream_mode="messages"` 下的 chunk 合併（依 id 累加）、`chunk_acc.values()` 與 `max(key=...)` 的盲點整理 | `LessonLearn/how_to_deal_with_AIMessageChunk.md` |
| 學習筆記：stream 與 enumerate | `app.stream()` 非 polling（事件佇列 + generator）、`enumerate` 只負責編號、回圈結束即完成訊號 | `LessonLearn/how_stream_and_enumerate_work_together.md` |
| 學習筆記：外層圖與子圖 state | 說明外層圖如何接收子圖更新、子圖間如何透過外層共享欄位傳遞資料、欄位對齊與 reducer 注意事項 | `LessonLearn/how_outgraph_update_and_share_state.md` |
| LangSmith 設定 | 帳號、`.env` 變數、驗證步驟與 C3 對應 | `Docs/langsmith_setup.md` |
| 本機 logging 開關 | `AGENT_LOGGING`、`langgraph_learning.agent_logging`、與 LangSmith 並存說明 | `Docs/logging_setup.md`、`src/langgraph_learning/agent_logging.py` |
| 環境變數與執行 | `.env`、路徑設定、`pip install -e .` | `Docs/env_and_run.md` |

---

## Phase：依賴鎖檔（pip freeze）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| 完整依賴清單 | 由 Python 3.11 執行 `pip freeze` 匯出；含 `langchain-google-genai`（Gemini）、langchain / langgraph 等及其傳遞依賴 | `Docs/requirements.txt` |

### 程式碼要點

- 還原：`py -3.11 -m pip install -r Docs/requirements.txt`
- 換機或升級套件後，若需更新鎖檔，請重新執行 `py -3.11 -m pip freeze` 覆寫本檔。
- Gemini 整合套件：`langchain-google-genai`（依賴含 `google-genai`、`google-auth` 等）。

### 使用範例

```powershell
py -3.11 -m pip install -r Docs/requirements.txt
```

---

## Phase：LangGraph 最小圖（practice_01）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| 修正 `StateGraph` 編譯錯誤 | 補上 `START` → 節點 → `END`；`compile()` 前必須有入口邊 | `practice_01.py` |

### 程式碼要點

- 錯誤原因：`ValueError: Graph must have an entrypoint`（空圖無法 `compile()`）。
- 使用 `hello` 節點示範 `Annotated[list[str], operator.add]` 的 reducer 合併。

### 使用範例

```powershell
py -3.11 practice_01.py
```

---

## Phase：Gemini 煙霧測試（practice_02）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| `ChatGoogleGenerativeAI` 單次 `invoke` | `.env` 載入 `GOOGLE_API_KEY`；部分模型回傳的 `content` 為區塊列表，需抽出 `type:text` 再印出 | `practice_02_model_smoke.py` |

### 使用範例

```powershell
py -3.11 practice_02_model_smoke.py
```

---

## Phase：手動工具迴圈（practice_03）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| `@tool` + `bind_tools` + 手動 ToolMessage | 查 USD→THB：Frankfurter API；模型產生 `tool_calls` 後由程式執行工具再 `invoke` 第二輪 | `practice_03_tool_manual.py`（入口）；工具實作 `src/langgraph_learning/tools/market.py` |

### 使用範例

```powershell
py -3.11 practice_03_tool_manual.py
```

---

## Phase：LangGraph 任務代理（階段 B）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **B1** `AgentState` | `messages: Annotated[list[BaseMessage], add_messages]`；附 `_smoke_b1` 驗證 `StateGraph` schema 與 `add_messages` | `src/langgraph_learning/graphs/agent_graph.py` |
| **B2** `call_model` | `ChatGoogleGenerativeAI` + `bind_tools`（`langgraph_learning.tools`）；節點回傳 `{"messages": [AIMessage]}` | `src/langgraph_learning/graphs/agent_graph.py` |
| **B3** 工具節點 + 條件邊 | 使用官方 **`ToolNode(_tools)`** 執行工具；手寫 `run_tools` 對照保留於檔案底部註解 | `src/langgraph_learning/graphs/agent_graph.py` |
| **B4** 條件邊與終止 | 使用官方 `tools_condition` + `path_map`（`tools`→`run_tools`，`__end__`→`END`）；常數 `DEFAULT_RECURSION_LIMIT` 傳入 `invoke(config=...)` | `src/langgraph_learning/graphs/agent_graph.py` |
| 根目錄入口 | `path_setup.add_src_to_path()` 後 `from langgraph_learning.graphs.agent_graph import main` | `practice_04_agent_graph.py` |

### 使用範例

```powershell
py -3.11 practice_04_agent_graph.py
```

---

## Phase：階段 C

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **C1** 第二個工具 | `get_eth_usdt_price_binance`：Binance `GET /api/v3/ticker/price?symbol=ETHUSDT`；與 Frankfurter 匯率工具一併 `bind_tools` + `ToolNode` | `src/langgraph_learning/tools/market.py` |
| **C2** 驗證與錯誤 | 白名單：`to_currency`、`symbol`；`_REQUEST_TIMEOUT`；`Timeout` / `HTTPError` / `RequestException` 分類；`_tool_error` 回傳 JSON | `src/langgraph_learning/tools/market.py` |

### 使用範例

```powershell
py -3.11 practice_04_agent_graph.py
```

---

## Phase：階段 D（可複用專案結構）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **D1** 工具與圖分離 | `tools`：`DEFAULT_MARKET_TOOLS`；`graphs`：`build_agent_graph`、`AgentState`、`main` | `src/langgraph_learning/tools/`、`src/langgraph_learning/graphs/` |
| **D1** 路徑／安裝 | 根目錄腳本用 `path_setup.add_src_to_path()`；或 `pip install -e .` | `path_setup.py`、`pyproject.toml` |
| **D2** 環境與執行說明 | 環境變數表、依賴還原、執行範例 | `Docs/env_and_run.md` |

### 程式碼要點

- 匯入 `langgraph_learning` 前須讓 Python 能找到 `src`（`path_setup` 或 editable install）。
- `Docs/requirements.txt` 仍為 lock 檔；若升級套件後請再 `pip freeze` 覆寫。

---

## Phase：第二課表 E（checkpoint）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **E1** `SqliteSaver` | `build_agent_graph(checkpointer=...)`；`SqliteSaver.from_conn_string`；checkpoint 寫入 `data/langgraph_checkpoints.sqlite`（已列 `.gitignore`） | `src/langgraph_learning/graphs/agent_graph.py`、`practice_06_checkpoint_memory.py` |
| **E2** 同 thread 接續 | 同一 `thread_id` 下兩次 `invoke`，第二輪只傳 `{"messages": [HumanMessage(...)]}`，與 checkpoint 內狀態經 `add_messages` 合併 | `practice_06_checkpoint_memory.py` |
| **E3** 歷史與 Replay | `get_state_history` 列檢查點；`get_state(checkpoint_id)` 對照；選用 `--replay` 示範 `invoke(None, config)` | `practice_06_checkpoint_memory.py` |
| 依賴 | `langgraph-checkpoint-sqlite` | `Docs/requirements.txt` |

### 使用範例

```powershell
py -3.11 practice_06_checkpoint_memory.py
```

### 程式碼要點

- 使用 checkpointer 時，每次 `invoke` 都帶相同 `config["configurable"]["thread_id"]` 以還原該對話。
- 多輪對話時輸入通常只含**本輪**新訊息；歷史由 checkpoint + `add_messages` 合併。
- **Fork**（`update_state` 自過去檢查點分岔）見官方 [Time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)；本腳本預設不執行，避免額外模型呼叫。

---

## Phase：第二課表 F（Human-in-the-loop）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **F1** `interrupt_before` | `build_agent_graph(..., interrupt_before=['run_tools'])`；`SqliteSaver` 寫入 `data/langgraph_hitl.sqlite`；`invoke` 後 `get_state().next == ('run_tools',)` 且尚無 `ToolMessage` | `src/langgraph_learning/graphs/agent_graph.py`、`practice_07_interrupt_hitl.py` |
| **F2** 恢復 | **核准**：`invoke(None, config)`（靜態斷點官方建議）；**拒絕**：`Command(update={...}, goto=END)` 撤銷 `tool_calls` 並結束；**改參**：`Command(update=...)` 替換 `AIMessage` 後再 `invoke(None)` | `practice_07_interrupt_hitl.py`（`--resume approve|reject|edit`） |
| **F3** 審批紀錄欄位 | 在 `AgentState` 新增 `approval_logs`（list reducer）；F2 三條路徑都追加 `decision / actor / approved_at / note`，並在輸出顯示最新紀錄 | `src/langgraph_learning/graphs/agent_graph.py`、`practice_07_interrupt_hitl.py` |

### 使用範例

```powershell
py -3.11 practice_07_interrupt_hitl.py
py -3.11 practice_07_interrupt_hitl.py --resume reject
py -3.11 practice_07_interrupt_hitl.py --resume edit
py -3.11 practice_07_interrupt_hitl.py --f1-only
```

### 程式碼要點

- 中斷須搭配 **checkpointer** 與 **`thread_id`**，才能在暫停後從同一 thread 恢復。
- **靜態** `interrupt_before`／`interrupt_after`：官方以 **`invoke(None)`** 從斷點繼續；**節點內** `interrupt()` 則搭配 **`Command(resume=...)`**（本腳本註解有說明）。
- 拒絕／改寫 pending 工具呼叫時，本範例以 **`RemoveMessage` + 新 `AIMessage`** 搭配 `add_messages` 語意更新最後一則模型訊息。
- F3：`approval_logs` 以 `operator.add` reducer 追加紀錄，避免覆蓋既有審批歷程。
- 官方說明：[Human-in-the-loop](https://docs.langchain.com/oss/python/langgraph/interrupts)。

---

## Phase：第二課表 G（Streaming）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **G1** `stream(updates)` | 以 `app.stream(..., stream_mode="updates")` 逐步印出節點完成事件（`call_model`、`run_tools`）與更新摘要（`messages`、`tool_calls`） | `practice_08_stream_agent.py` |
| **G2** `messages` / `custom` / `both` | `--mode messages` 觀察訊息流；`--mode custom` 於包裝版 `call_model` 內 `get_stream_writer()` 示範自訂事件；`--mode both` 同時訂閱 `updates`+`messages` | `practice_08_stream_agent.py` |

### 使用範例

```powershell
py -3.11 practice_08_stream_agent.py
py -3.11 practice_08_stream_agent.py --mode messages
py -3.11 practice_08_stream_agent.py --mode both
py -3.11 practice_08_stream_agent.py --mode custom
```

### 程式碼要點

- `updates` 模式每個 chunk 代表節點完成後的狀態更新，可直接觀察節點執行順序。
- `messages` 模式偏向「訊息／token 流」事件；`custom` 需節點內呼叫 `get_stream_writer()`，本腳本以暫時包裝 `call_model` 示範。
- `stream_mode` 傳入多個模式時，每個 chunk 會是 `(mode, payload)` 元組。
- 腳本在串流過程中同步追蹤最後一則 `AIMessage`，結束後印出摘要文字，便於與 `invoke` 結果對照。

---

## Phase：第二課表 H（狀態擴充）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **H1** `AgentState` 新欄位 | 在 `TypedDict` 新增 `user_id`、`locale`、`pending_tool_args`（使用 `NotRequired`，避免舊腳本必填） | `src/langgraph_learning/graphs/agent_graph.py` |
| **H1** 輸入示範 | 在串流練習腳本補上三欄位示範值，方便觀察 state 擴充後的輸入形狀 | `practice_08_stream_agent.py` |
| **H2** reducer 最小範例 | 獨立 `H2DemoState`：`audit_events` 用 `operator.add` 串接列表；`pending_tool_args` 用自訂 `merge_pending_tool_args` 淺合併字典，示範多節點 partial update 不互相覆寫整欄 | `practice_09_state_fields.py` |
| **H3** 訊息裁剪 | 在練習檔保留「最近 N 則 + 可選 system」的裁剪概念與斷言驗證 | `practice_09_state_fields.py` |
| **H4** 官方訊息前處理 | 正式接入 `agent_graph.call_model`：`preprocess_messages_for_model = filter_messages -> trim_messages`，並保留可調常數（max_tokens / include_system / start_on / exclude_types） | `src/langgraph_learning/graphs/agent_graph.py`、`practice_12_message_preprocess.py` |
| **H4** `.env` 可配置化 | 將 H4 前處理常數改為環境變數讀取（含布林/整數/CSV 解析與非法值 fallback），並補 `.env.example` 範本鍵值 | `src/langgraph_learning/graphs/agent_graph.py`、`.env.example` |
| **H4** 執行文件補充 | 在環境說明補上 H4 變數表、建議 `.env` 範例與調參時機 | `Docs/env_and_run.md` |

### 程式碼要點

- `messages` 仍是主要對話狀態，新增欄位作為業務上下文，不影響既有工具流程。
- `NotRequired` 可讓舊腳本不需要立刻傳入新欄位。
- **Reducer 選型（H2）**：同一欄位若有多筆更新需合併時，在 `Annotated[..., reducer]` 指定規則；列表常見 `operator.add`；需「合併 dict／結構」時寫自訂 `(left, right) -> merged`（注意 `None` 與初值）。主代理圖中 `approval_logs` 已用 `operator.add`；訊息欄位用 `add_messages`。
- **訊息裁剪（H3）**：練習腳本先建立「只保留最近 N 則」的直覺基礎，確認裁剪不會破壞最末對話上下文。
- **官方前處理（H4）**：正式流程已接在 `call_model` 前，採 `filter_messages(...) -> trim_messages(...)`。先控制可進模型訊息，再做 token 裁剪；預設 `MAX_MODEL_TOKENS=20`、`strategy='last'`、`include_system=True`、`start_on='human'`。
- **H4 環境變數化**：可透過 `.env` 調整 `MODEL_MAX_TOKENS`、`MODEL_TRIM_STRATEGY`、`MODEL_TRIM_INCLUDE_SYSTEM`、`MODEL_TRIM_START_ON`、`MODEL_EXCLUDE_TYPES`，不需改程式碼。

### 使用範例（H2/H3/H4）

```powershell
py -3.11 practice_09_state_fields.py
py -3.11 practice_12_message_preprocess.py
```

---

## Phase：第二課表 I（子圖）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **I1** 研究子圖 | `ResearchState` 子圖只負責查資料，呼叫 market 工具並產出 `market_snapshot` 與 `errors`（資料取得與解析集中於單一子圖） | `src/langgraph_learning/pipelines/i1_subgraphs.py` |
| **I1** 回覆子圖 | `ComposeState` 子圖只負責把 `market_snapshot`/`errors` 轉成 `final_response` | `src/langgraph_learning/pipelines/i1_subgraphs.py` |
| **I1** 外層組合圖 | `build_i1_outer_graph()` 依序組合 `research -> compose`，示範模組化 `StateGraph` 串接 | `src/langgraph_learning/pipelines/i1_subgraphs.py` |
| **I1** 實戰命名對齊 | 外層與子圖狀態改為較貼近實務：`intent`、`market_snapshot`、`final_response`、`errors`，便於後續 I2 意圖路由擴展 | `src/langgraph_learning/pipelines/i1_subgraphs.py`、`practice_10_subgraph_or_router.py` |

### 程式碼要點

- 子圖拆分原則：研究子圖只做「資料取得/整理」，回覆子圖只做「文案組裝」，降低互相耦合。
- 外層圖只負責流程編排（先研究再回覆），未來可直接替換其中一個子圖而不影響另一個。
- State 命名提前對齊實務欄位（`intent`、`market_snapshot`、`final_response`、`errors`），可直接承接 I2 的分類路由與錯誤分流。

### 使用範例（I1）

```powershell
py -3.11 practice_10_subgraph_or_router.py
```

---

## Phase：第二課表 I2（條件路由）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **I2** 意圖分類 | Gemini **`with_structured_output(IntentClassification)`**（`intent` + `brief_reason`）；環境變數 **`I2_INTENT_MODEL`**（預設與主圖相同 `gemini-3-flash-preview`）；單測分類可用 **`classify_intent_structured`** | `src/langgraph_learning/pipelines/i2_intent_router.py` |
| **I2** 條件邊 | `classify` 後 `add_conditional_edges` 分流至 `chat_reply`／`complaint_reply`／`prepare_price` | `src/langgraph_learning/pipelines/i2_intent_router.py` |
| **I2** 查價鏈 | `prepare_price` 對齊 I1 欄位後串接既有 **研究子圖 → 回覆子圖** | `src/langgraph_learning/pipelines/i2_intent_router.py` |
| **I2** 分支模組 | 閒聊／申訴回覆骨架分檔，改提示不影響其他分支 | `src/langgraph_learning/pipelines/i2_branches/chat_reply.py`、`complaint_reply.py` |
| **I2** 入口腳本 | 三則範例句驗證分類與 `invoke` | `practice_10_i2_intent_router.py` |

### 程式碼要點

- 模組邊界：條件路由與查價子圖在 `i2_intent_router.py`；純文案調整集中在 `i2_branches/`。
- 查價分支重用 I1 子圖，避免重複市場查詢邏輯。
- 分類需 **`GOOGLE_API_KEY`**；state 會寫入 **`intent_reason`**（對應模型 `brief_reason`），便於對照路由與除錯。

### 使用範例（I2）

```powershell
py -3.11 practice_10_i2_intent_router.py
```

---

## Phase：第二課表 J1（Chroma 索引前置）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **J1** 套件安裝 | 安裝 `langchain-chroma`、`chromadb`、`beautifulsoup4`，提供向量儲存與 HTML 抓取能力 | Python 環境（pip） |
| **J1** 抓文腳本 | 新增一鍵腳本：從 Lilian Weng 首頁抓文章連結、下載內容、轉存 Markdown 快照 | `src/langgraph_learning/tools/j1_build_lilian_chroma.py` |
| **J1** 切分與索引 | 使用 `RecursiveCharacterTextSplitter` 切 chunk，透過 `Chroma` 寫入持久化資料夾 | `src/langgraph_learning/tools/j1_build_lilian_chroma.py` |
| **J1** Embedding 設定 | 使用 `GoogleGenerativeAIEmbeddings`，並提供 `J1_EMBED_MODEL` + fallback（`models/gemini-embedding-001`） | `src/langgraph_learning/tools/j1_build_lilian_chroma.py` |
| **J1** 實跑驗證 | 成功抓取 3 篇文章、建立 19 chunks，並以 probe query 驗證可檢索到 reward hacking 內容 | `data/lilianweng_markdown/`、`data/chroma/lilianweng/` |

### 程式碼要點

- 腳本流程：`discover URLs -> fetch post -> save markdown -> split -> embed -> persist chroma -> similarity_search`。
- 提供配額保護參數：`--max-chars-per-doc`、`--chunk-size`、`--chunk-overlap`，避免免費層 embedding request 超額。
- 可用 `--keep-existing` 決定是否覆蓋舊索引，預設會重建。

### 使用範例（J1）

```powershell
py -3.11 src/langgraph_learning/tools/j1_build_lilian_chroma.py --limit 3 --max-chars-per-doc 12000 --chunk-size 2400 --chunk-overlap 200
```

---

## Phase：第二課表 J2／J3（RAG `@tool`）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **J2** Chroma 共用設定 | 專案根目錄解析、`LILIAN_CHROMA_DIR`／`LILIAN_CHROMA_COLLECTION`、`create_embeddings` | `src/langgraph_learning/tools/lilian_chroma_store.py` |
| **J2** 檢索工具 | `@tool search_lilian_weng_knowledge`：`similarity_search` → 帶 title/source/slug 的文字片段 | `src/langgraph_learning/tools/rag_lilian.py` |
| **J2** 工具匯出 | `DEFAULT_RAG_TOOLS` 與 `search_lilian_weng_knowledge` | `src/langgraph_learning/tools/__init__.py` |
| **J2** 圖編譯 | `build_agent_graph(tools=...)` 可注入自訂工具清單（預設仍為市場工具） | `src/langgraph_learning/graphs/agent_graph.py` |
| **J2** 入口腳本 | 合併市場工具 + RAG 工具，示範「先檢索再作答並標示依據」 | `practice_11_rag_tool.py` |
| **J2** 環境範例 | `.env.example` 補上 `LILIAN_CHROMA_*`、`J1_EMBED_MODEL` | `.env.example` |
| **J3** 系統提示常數 | `LILIAN_RAG_SYSTEM_PROMPT`：何時呼叫內部知識庫 vs 市場工具；答案須附「依據」對應 `[n]`／title／slug／source | `src/langgraph_learning/tools/rag_lilian.py`、`tools/__init__.py` |
| **J3** 入口腳本 | 初始 `messages` 含 `SystemMessage(LILIAN_RAG_SYSTEM_PROMPT)`，與 `build_agent_graph` 既有流程一致 | `practice_11_rag_tool.py` |

### 程式碼要點

- 工具內若 Chroma 目錄不存在，回傳 JSON 錯誤字串提示先跑 J1。
- `practice_11_rag_tool.py` 在 import `agent_graph` 前若 `MODEL_MAX_TOKENS` 過小會暫調，避免 H4 trim 裁掉 tool 結果。
- J3 以**系統提示**約束引用格式與「文件未載明」行為，不修改 `build_agent_graph` 預設邏輯；其他入口可複用 `LILIAN_RAG_SYSTEM_PROMPT`。

### 使用範例（J2／J3）

```powershell
py -3.11 practice_11_rag_tool.py
```

---

## Phase：第三課表 K1（非同步 `ainvoke`）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **K1** | 同一輪使用者輸入分別以 `invoke` 與 `await ainvoke` 執行預設代理圖，比對訊息則數並印出最終 AI 文字 | `practice_13_async_agent.py` |

### 程式碼要點

- 沿用 `build_agent_graph()` 與 `agent_graph.main()` 同款查價提示，確保會走工具迴圈。
- 節點內仍為同步 `llm_bound.invoke`；K1 目標是**圖層** `ainvoke` 與 `invoke` 行為一致，非強制節點改 async。
- 若兩次執行訊息則數不同，腳本會提示（模型／路徑可能非完全確定性）。
- 可選：`main` 末尾預設註解的 `demo_concurrent_ainvoke`，以 `asyncio.gather` 對照連續 `ainvoke` 的牆鐘時間（取消註解後會額外呼叫模型）。

### 使用範例

```powershell
py -3.11 practice_13_async_agent.py
```

---

## Phase：第三課表 K2（async 市場工具）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **K2** | 市場工具改為 **httpx**；`StructuredTool.from_function(func=..., coroutine=...)` 同時提供同步／非同步實作。`graph.ainvoke` 時 `ToolNode` 走 `tool.ainvoke` → **AsyncClient**，不阻塞 event loop；`invoke` 與子圖內 `.invoke()` 仍用同步 **Client** | `src/langgraph_learning/tools/market.py` |

### 程式碼要點

- 純 `async def` 的 `@tool` 在 LangChain 中 **無** `func`，同步 `tool.invoke` 會拋錯，故採 **雙實作** 而非只留 async。
- **httpx** 預設不跟隨重新導向，已設 `follow_redirects=True`（Frankfurter 可能回 301；舊版 `requests` 預設會跟隨）。
- 逾時：`httpx.Timeout(20.0, connect=5.0)`（需給 default 或四項明確參數，否則 httpx 建構失敗）。

### 使用範例

（與 K1 相同，工具行為對呼叫端不變。）

```powershell
py -3.11 practice_13_async_agent.py
```

---

## Phase：第三課表 K3（checkpointer 與常駐服務生命週期）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **K3** | 釐清 **SqliteSaver／已編譯圖** 在常駐服務（**long-running service**）中宜 **單例重用**（lifespan 建立一次），請求內只傳 `config`（含 `thread_id`）；對照「每請求新建」之成本與語意問題；補 **AsyncSqliteSaver**、**horizontal scaling**／**shared storage** 與多 worker 注意 | `Docs/checkpointer_in_services.md` |
| **K3** | `build_agent_graph` docstring 摘要連結至上述文件 | `src/langgraph_learning/graphs/agent_graph.py` |

### 程式碼要點

- Checkpointer 用途：跨 `invoke` 保留狀態、`thread_id` 接續對話、HITL 暫停／恢復必備。
- 腳本可用 `with SqliteSaver.from_conn_string(...)`；HTTP 服務則用 **startup／lifespan** 對齊「建立一次」語意。
- L 階段 FastAPI 實作時應沿用文件中的建議模式；用語見文件開頭「常駐服務／long-running service」對照表。

### 使用範例

閱讀說明即可；實作見第三課表 L（`practice_14_fastapi_agent.py` 規劃）。

```powershell
# 既有 checkpoint 練習仍適用「生命週期內一個 saver」概念
py -3.11 practice_06_checkpoint_memory.py
```

---

## Phase：第三課表 L1（FastAPI `POST /chat`）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **L1** | FastAPI API 已集中到 `src/api/`：`app.py` 組裝 app + lifespan（單例 graph）、`routes/chat.py` 提供 **`POST /chat`**（`await graph.ainvoke`）、`routes/health.py` 先放健康檢查路由骨架；`practice_14_fastapi_agent.py` 改為啟動入口。並保留註解標註 **① 路由 async／ainvoke**、**② `call_model` 仍同步 `invoke`**、**③ `ToolNode` 對 async 工具走 `ainvoke`**（K2） | `src/api/app.py`、`src/api/routes/chat.py`、`src/api/routes/health.py`、`practice_14_fastapi_agent.py` |
| 依賴 | **fastapi**、**uvicorn**（及傳遞依賴如 starlette、click 等） | `Docs/requirements.txt` |

### 程式碼要點

- L1 架構已在 L2 擴充為「請求帶 `thread_id`／`user_id` → `config["configurable"]` + checkpoint 持久化」。
- 若圖異常結束於仍含 `tool_calls` 的 `AIMessage`，回 **500** 便於察覺設定／遞迴問題。
- L3：`GET /health` 已接上 `pydantic-settings`（見下方 L3 小節）。

### 使用範例

```powershell
py -3.11 -m pip install -r Docs/requirements.txt
py -3.11 practice_14_fastapi_agent.py
```

另開終端：

```powershell
curl -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"message\":\"只回一個字：好\"}"
```

---

## Phase：第三課表 L2（`thread_id`/checkpoint 銜接）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **L2** | `POST /chat` 支援 `thread_id` / `user_id` 從 **header**（`X-Thread-Id`、`X-User-Id`）或 **body**（`thread_id`、`user_id`）傳入；缺少 `thread_id` 回 422；並回傳本輪實際使用的 `thread_id`、`user_id`、`config_source`（header/body/mixed）便於審計 | `src/api/routes/chat.py`、`src/api/schemas.py` |
| **L2** | 請求欄位對應註解：`X-Thread-Id`/`body.thread_id`、`X-User-Id`/`body.user_id` → `config["configurable"]["thread_id" / "user_id"]` | `src/api/routes/chat.py` |
| **L2** | lifespan 內建立單例 `AsyncSqliteSaver`，以 `build_agent_graph(checkpointer=...)` 編譯圖並在 shutdown 關閉；checkpoint 檔採 `data/langgraph_checkpoints.sqlite` | `src/api/app.py` |

### 程式碼要點

- header 與 body 同時提供時，以 **header 優先**；`config_source="mixed"` 方便追蹤來源。
- `thread_id` 成為每次 `ainvoke` 的必要欄位，確保 checkpoint 定址明確。
- 若 body 的 `thread_id` / `user_id` 為空字串，會在路由層視為「未提供」，可由 header `X-Thread-Id` / `X-User-Id` 正常接手。
- 路由邊界註解已更新：路由 `await graph.ainvoke`、`call_model` 已改 async `ainvoke`（舊同步寫法保留註解）、ToolNode 對 async 工具走 `ainvoke`。

### 使用範例

```powershell
# 第 1 輪（body 傳 thread_id）
curl -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"thread_id\":\"demo-t1\",\"message\":\"請記住我叫小明\"}"

# 第 2 輪（同一 thread_id，可改用 header）
curl -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -H "X-Thread-Id: demo-t1" -d "{\"message\":\"我剛剛叫什麼名字？\"}"
```

---

## Phase：第三課表 L3（`/health` + `pydantic-settings`）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **L3** | `ApiSettings`：`BaseSettings` 讀 `.env`；`GOOGLE_API_KEY`／`LANGSMITH_API_KEY` 用 **`SecretStr`**；`@lru_cache` 的 `get_settings()` | `src/api/settings.py` |
| **L3** | `GET /health` 回傳 `status`（`ok`／`degraded`）、各項 **是否已設定** 的布林、`langsmith_project`、`checkpoint_db`；**不**回傳金鑰、**不**在路由內 log 敏感內容 | `src/api/routes/health.py`、`src/api/schemas.py` |
| **L3** | lifespan 使用 `get_settings().checkpoint_db`（環境變數 **`LANGGRAPH_CHECKPOINT_DB`**，預設 `data/langgraph_checkpoints.sqlite`） | `src/api/app.py` |
| **L3** | `.env.example` 補充 `LANGGRAPH_CHECKPOINT_DB` 註解 | `.env.example` |

### 程式碼要點

- `degraded`：行程正常但缺少 `GOOGLE_API_KEY` 時（與 `agent_graph` 啟動需求一致），仍回 **200**，便於與純 liveness 探針共存。
- 若需除錯設定，只 log 布林或路徑字串，**禁止** `logger.info(settings)` 或印出 `SecretStr`。

### 使用範例

```powershell
curl -s http://127.0.0.1:8000/health
```

---

## Phase：第三課表 L4（模型節點 async）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **L4** | `build_agent_graph` 的 `call_model` 改為 `async def`，模型呼叫改用 `await llm_bound.ainvoke(model_messages)`；**原本同步寫法** `llm_bound.invoke(...)` 以註解保留在同一位置，方便對照學習 | `src/langgraph_learning/graphs/agent_graph.py` |
| **L4** | API 層註解同步更新：標明 `call_model` 已 async，舊同步寫法保留註解 | `src/api/app.py`、`src/api/routes/chat.py` |

### 程式碼要點

- L1/L2 時阻塞重點原本在模型節點；L4 後模型 API 等待改為 async 等待，較符合整條 `ainvoke` 路徑。
- 你要求的「保留舊方式」已在 `call_model` 旁以註解留下，便於直接對照：
  - 新：`ai = await llm_bound.ainvoke(...)`
  - 舊（註解保留）：`# ai = llm_bound.invoke(...)`

### 使用範例

```powershell
py -3.11 practice_14_fastapi_agent.py
curl -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"thread_id\":\"l4-demo\",\"message\":\"Say only: OK\"}"
```

---

## Phase：L 階段文件補充（L1/L2/L4 對照）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| L 階段同步/非同步演進表 | 整理 L1/L2/L4 在「路由、模型節點、ToolNode」三段的行為差異、阻塞觀察點與排錯方向 | `Docs/l1_l2_l4_async_diff.md` |

---

## Phase：第三課表 M1（golden dataset，10 筆）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **M1** golden 測試資料 | 建立 10 筆案例，覆蓋一般問答、格式控制、市場工具、資料不足、敏感資訊、空輸入與模糊指令等場景；每筆含 `must_include` / `must_not_include` | `evaluation/datasets/m1_golden_cases.json` |
| **M3** smoke 腳本骨架 | 新增 `practice_15_eval_smoke.py`：讀取 golden、逐筆 `await graph.ainvoke`、規則比對、輸出 PASS/FAIL 與摘要；支援 `--limit` / `--case-id` | `practice_15_eval_smoke.py` |
| 課表同步 | `TODO_phase3.md` 的 M1 已勾選完成 | `TODO_phase3.md` |

### 程式碼要點

- 第一版以「可快速重跑的本機規則比對」為主：先把回歸流程跑起來，再逐步升級到 LangSmith/LMM-as-judge。
- 評測規則採最小可行設計：`must_include` 與 `must_not_include`，降低初期維護成本。
- smoke 使用 `configurable.thread_id`（`m1-smoke-{case_id}`）保留與 checkpoint 流程一致的呼叫習慣。

### 使用範例

```powershell
py -3.11 practice_15_eval_smoke.py
py -3.11 practice_15_eval_smoke.py --limit 3
py -3.11 practice_15_eval_smoke.py --case-id M1-003
```

---

## Phase：第三課表 M2（LangSmith Dataset + Evaluation）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **M2** Dataset 同步模式 | 在 `practice_15_eval_smoke.py` 新增 `--mode sync-dataset`：把 `m1_golden_cases.json` 同步至 LangSmith dataset（預設 `LangGraph_Learning_M1_Golden`），支援 `--force-recreate` 重建資料集 | `practice_15_eval_smoke.py` |
| **M2** LangSmith evaluate 模式 | 新增 `--mode langsmith-eval`：以 `langsmith.evaluation.evaluate(...)` 跑完整資料集，並輸出 experiment 名稱與 URL | `practice_15_eval_smoke.py` |
| **M2** 自訂 evaluator | 以 `must_include` / `must_not_include` 實作 `keyword_rule` 評估器，直接對應 M1 golden 規格 | `practice_15_eval_smoke.py` |
| **M2** LLM-as-judge（三維度） | 新增 `llm_judge_relevance`、`llm_judge_helpfulness`、`llm_judge_groundedness`（皆為 0/1 + reason）；以 `with_structured_output` 產生結構化評分，並可與 `keyword_rule` 雙軌並跑 | `practice_15_eval_smoke.py`、`.env.example` |
| **M2** judge 模板切換 | 新增 `--llm-judge-template strict|lenient`，同一批案例可用兩種評分尺度對照語意分數 | `practice_15_eval_smoke.py`、`.env.example` |
| **M2** judge 維度選擇 | 新增 `--llm-judge-dimensions`（CSV），可在 `relevance/helpfulness/groundedness` 間自選，平衡評測覆蓋率與 token 成本 | `practice_15_eval_smoke.py`、`.env.example` |
| **M2** 429 指數退避重試 | `target_inference` 與 `llm_judge_*` 都接上 retry（429/timeout 等暫時性錯誤）；新增 `--retry-attempts`、`--retry-max-wait-seconds` 與對應 `.env` 變數 | `practice_15_eval_smoke.py`、`.env.example` |
| **M2** 保底模式（keyword-only） | LLM judge 在重試後仍失敗時，自動停用後續 judge（只保留 `keyword_rule`）避免整體評測中斷；可用 `--no-fallback-on-judge-error` 關閉 | `practice_15_eval_smoke.py`、`.env.example` |
| 課表同步 | `TODO_phase3.md` 的 M2 已勾選完成 | `TODO_phase3.md` |

### 程式碼要點

- 單一腳本整合三種流程：本機 smoke（M1/M3）與 LangSmith dataset/eval（M2）。
- Dataset 同步採「依 `metadata.case_id` 去重」策略，重跑同步時會略過已存在案例，避免重複寫入。
- Evaluation target 仍走 `graph.ainvoke`，確保 LangSmith 上的結果與本機 smoke 路徑一致。
- LLM judge 預設關閉；開啟 `--enable-llm-judge` 後才會加跑語意評分，模型由 `M2_JUDGE_MODEL` 控制。
- judge 模板支援 `strict/lenient`，可用同一 dataset 比較不同評分尺度下的穩定性。
- judge 維度可用 `--llm-judge-dimensions` 自訂，避免每次都跑滿三維度造成額外 token 消耗。
- 若遇到 Gemini 429/暫時性錯誤，腳本會做指數退避重試；重試策略可由 CLI 或 `.env` 參數調整。
- 保底模式預設開啟：judge 若連續失敗會自動降級為 keyword-only，確保該輪 evaluate 可完成並產生結果。

### 使用範例

```powershell
# M2-1: 同步 10 筆 golden 到 LangSmith
py -3.11 practice_15_eval_smoke.py --mode sync-dataset --dataset-name LangGraph_Learning_M1_Golden

# M2-2: 在 LangSmith 跑評測
py -3.11 practice_15_eval_smoke.py --mode langsmith-eval --dataset-name LangGraph_Learning_M1_Golden

# M2-3: 抽樣 3 筆（省 token）
py -3.11 practice_15_eval_smoke.py --mode langsmith-eval --dataset-name LangGraph_Learning_M1_Golden --sample-size 3 --random-seed 42

# M2-4: 雙軌評測（keyword + 三維度語意評分，lenient）
py -3.11 practice_15_eval_smoke.py --mode langsmith-eval --dataset-name LangGraph_Learning_M1_Golden --sample-size 3 --random-seed 42 --enable-llm-judge --llm-judge-template lenient

# M2-5: 嚴格模板 + 指定單一維度（只跑 relevance，省 token）
py -3.11 practice_15_eval_smoke.py --mode langsmith-eval --dataset-name LangGraph_Learning_M1_Golden --sample-size 3 --random-seed 42 --enable-llm-judge --llm-judge-template strict --llm-judge-dimensions relevance

# M2-6: 額外提高重試容錯（遇到 429 時）
py -3.11 practice_15_eval_smoke.py --mode langsmith-eval --dataset-name LangGraph_Learning_M1_Golden --sample-size 3 --enable-llm-judge --llm-judge-dimensions relevance --retry-attempts 5 --retry-max-wait-seconds 12

# M2-7: 關閉保底模式（judge 失敗即拋錯）
py -3.11 practice_15_eval_smoke.py --mode langsmith-eval --dataset-name LangGraph_Learning_M1_Golden --sample-size 3 --enable-llm-judge --no-fallback-on-judge-error
```

---

## Phase：第三課表 M3（pytest smoke 銜接）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **M3** pytest 設定 | 在 `pyproject.toml` 新增 `tool.pytest.ini_options`，固定測試入口為 `tests/` | `pyproject.toml` |
| **M3** 離線 smoke 測試 | 新增 `tests/test_eval_smoke.py`，覆蓋 golden 載入、關鍵字規則與 `run_smoke`（透過 monkeypatch 避免真實模型呼叫） | `tests/test_eval_smoke.py` |
| **M3** 依賴補齊 | 鎖檔加入 `pytest`，可直接還原測試環境 | `Docs/requirements.txt` |
| 課表同步 | `TODO_phase3.md` 的 **M3** 已勾選完成 | `TODO_phase3.md` |

### 程式碼要點

- 測試主軸是「可重跑、可離線」：不依賴外部 API，也不要求 `GOOGLE_API_KEY`。
- `run_smoke` 測試用 `monkeypatch` 替換 `build_agent_graph` 與 `_ainvoke_answer`，專注驗證流程控制與 exit code。
- 既有 `practice_15_eval_smoke.py` 腳本仍保留；pytest 版本用於快速回歸與 CI 前置檢查。

### 使用範例

```powershell
py -3.11 -m pip install -r Docs/requirements.txt
py -3.11 -m pytest
```

---

## Phase：第三課表 M3（最小 CI）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| **M3-CI** GitHub Actions | workflow 升級為雙 job：`lint` + `test`，在 `push`、`pull_request`、`workflow_dispatch` 觸發 | `.github/workflows/pytest.yml` |
| **M3-CI** 環境建置 | `ubuntu-latest` + Python 3.11，安裝 `Docs/requirements.txt` 與 `pip install -e .` | `.github/workflows/pytest.yml` |
| **M3-CI** 測試執行 | 以 `python -m pytest -q` 跑 smoke 測試，作為合併前最小門檻 | `.github/workflows/pytest.yml` |
| **M3-CI** 靜態檢查 | `ruff` lint 範圍擴大為 `src/ + tests/`，`test` job 需等待 `lint` 成功才執行 | `.github/workflows/pytest.yml`、`pyproject.toml` |
| **M3-CI** ruff 規則 | 在 `pyproject.toml` 新增最小規則：`target-version=py311`、`line-length=100`、`select=[E9,F63,F7,F82]` | `pyproject.toml` |
| **M3-CI** 觸發收斂 | workflow 改為僅在 `main` push 與 `main` 目標 PR 觸發，並加上 `concurrency` 自動取消同分支舊工作 | `.github/workflows/pytest.yml` |

### 程式碼要點

- 使用 `actions/setup-python` 的 pip cache（依 `Docs/requirements.txt`）降低重跑時間。
- `test` 設為 `needs: lint`，可先擋下基礎風格/語法問題再進入測試階段。
- `ruff` 已擴到 `src + tests`，但規則採「最小防呆」集合（語法與高風險名稱錯誤）避免一次性導入大量既有風格修正。
- 觸發條件收斂到 `main` 主線流程，並啟用 `concurrency.cancel-in-progress=true`，減少重複 CI 分鐘消耗。

### 使用範例

```powershell
# 本機先確認（與 CI 對齊）
py -3.11 -m ruff check src tests
py -3.11 -m pytest -q

# 推送後會在 GitHub Actions 自動執行同等測試
```

---

## Phase：版本控制維護（`.gitignore` 清理）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| Git 忽略規則擴充 | 補齊 Python 快取、虛擬環境、pytest/ruff/mypy 快取、coverage、IDE/OS 暫存 | `.gitignore` |
| 環境檔白名單 | 保留 `.env` 系列忽略，但以 `!.env.example` 明確允許範例檔進版控 | `.gitignore` |
| 本機資料隔離 | 持續忽略 `data/`（含 checkpoint/索引等執行期資料），避免把本機狀態推到 GitHub | `.gitignore` |

### 程式碼要點

- 忽略規則以「可重建的本機產物」為主，避免提交 cache/venv/coverage 與編輯器雜訊。
- 專案必要設定檔（如 `.env.example`）保留追蹤，確保團隊可快速建立環境。

---

## Phase：文件補強（README 英文化）

### 實作內容

| 項目 | 說明 | 檔案路徑 |
|------|------|----------|
| README 新增 | 新建英文版專案說明，定位為 LangGraph 訓練課程，並補上「你會學到什麼」的總覽段落 | `README.md` |
| A~P 課表整理 | 依 `TODO.md`、`TODO_phase2.md`、`TODO_phase3.md` 匯整 Phase A~P，保留每項 `[x]` / `[ ]` 進度勾選 | `README.md` |
| README 導覽補強 | 新增 `Quick Start`、`Project Structure`、`How to Continue from Here`，提升 GitHub 首頁可用性 | `README.md` |
| README Badge 區塊 | 新增 `Badges` 小節與 `Python CI` badge 範本連結（待替換 `<OWNER>/<REPO>`） | `README.md` |

### 程式碼要點

- README 全文使用英文，對齊你提出的文件語言需求。
- 進度勾選與三份 TODO 保持一致，方便直接作為 GitHub 首頁的進度看板。
- 增加快速啟動與路徑導覽，讓新進讀者可在不閱讀全部 TODO 的情況下快速開始與接續學習。
- Badge 先用可複製的模板 URL，推上 GitHub 後替換 repo 路徑即可立即顯示 CI 狀態。

