# 第二課表：LangGraph 進階能力（持久化 · 人機協作 · 串流 · 狀態 · RAG）

> **前置**：已完成 `TODO.md` 迷你課表（`StateGraph`、工具、`ToolNode`、`recursion_limit`、專案結構 `src/langgraph_learning/`）。  
> **目標**：把「能跑的代理」變成「可長期維護、可與人協作、可觀測」的應用元件；每一階段都可獨立用一支小腳本驗證。

---

## 與第一課表的關係

| 第一課表已涵蓋 | 本課表往哪裡延伸 |
|----------------|------------------|
| 單次 `invoke`、同步結果 | **串流** token／事件、前端體驗 |
| 記憶只在程式內的 `messages` | **Checkpoint**：跨請求還原狀態、thread |
| 全自動 tool 迴圈 | **interrupt**：核准／修改工具呼叫再繼續 |
| 單一 `AgentState` 以訊息為主 | **狀態欄位擴充**、裁剪歷史、結構化欄位 |
| 單一圖 | **子圖**、多步驟管線、簡單 **RAG** |

---

## 建議對應檔名（可依喜好調整）

| 檔案（建議） | 用途 |
|--------------|------|
| `practice_06_checkpoint_memory.py` | E：checkpoint、`thread_id`、同一對話多輪 |
| `practice_07_interrupt_hitl.py` | F：`interrupt`、人類核准後 `Command` 恢復 |
| `practice_08_stream_agent.py` | G：`stream()`、`stream_mode`、觀察節點／token |
| `practice_09_state_fields.py` | H：`TypedDict` 多欄位、自訂 reducer、訊息裁剪 |
| `practice_12_message_preprocess.py` | H4：`filter_messages` + `trim_messages` 前處理策略（可重用） |
| `practice_10_subgraph_or_router.py` | I：子圖封裝，或「研究 → 執行」兩段路由 |
| `practice_10_i2_intent_router.py` | I2：意圖分類 + 條件路由（閒聊／查價／申訴） |
| `practice_11_rag_tool.py` | J：向量庫／Retriever + `@tool`，代理檢索後作答 |

實作時可沿用 **`path_setup.add_src_to_path()`**，新程式碼放在 **`src/langgraph_learning/`** 對應子目錄，與階段 D 一致。

---

## 課表（建議順序）

### 階段 E：持久化與 thread（Checkpoint）

- [x] **E1** 使用 **`MemorySaver`** 或 **`SqliteSaver`**（擇一），編譯圖時傳入 **checkpointer**。  
- [x] **E2** 用 **`config={"configurable": {"thread_id": "..."}}`** 呼叫 `invoke`，確認同一 `thread_id` 下 **state 可接續**（第二輪還看得到上一輪的 `messages`）。  
- [x] **E3**（選修）用 **`get_state_history`** 或官方文件中的 **time travel** 概念，理解「檢查點列表」與回溯（API 以你安裝的 `langgraph` 版本為準）。

**自我檢查**：關掉程式再開，若用 **Sqlite** 持久檔，同一 `thread_id` 是否仍能載入歷史？

---

### 階段 F：人機協作（Human-in-the-loop）

- [x] **F1** 在「即將執行敏感工具」前設 **中斷點**（例如 `interrupt` 或官方 **HITL** 教學中的模式），圖在該處暫停。  
- [x] **F2** 從外部傳入 **`Command`**（或等效 API）**恢復**執行：核准、拒絕、或修改參數後再進 `ToolNode`。  
- [x] **F3**（選修）記錄「誰在何時核准」到 state 自訂欄位（與階段 H 銜接）。

**自我檢查**：沒有人類輸入時，圖不會默默執行高風險工具。

---

### 階段 G：串流（Streaming）

- [x] **G1** 將 `invoke` 改為 **`stream`**，印出 **節點完成事件**（例如 `updates` 模式）。  
- [x] **G2**（選修）試 **`messages` 模式**或 **`custom`**，感受 token／chunk 與圖事件的差異。  
- [x] **G3** 對照 **LangSmith** trace：串流時是否仍能看到完整步驟（必要時查官方 **streaming + tracing** 說明）。

**自我檢查**：終端機可看到「哪個節點先跑完」，而不是只有最後一個字串。

---

### 階段 H：狀態擴充（超越 `messages`）

- [x] **H1** 在 `TypedDict` 中新增欄位，例如 **`user_id`**、**`locale`**、**`pending_tool_args`**。  
- [x] **H2** 為列表欄位選擇 **reducer**（`operator.add` 或自訂合併函式），避免並行時狀態被覆寫。  
- [x] **H3**（選修）實作 **訊息裁剪**（只保留最近 N 則再進模型），控制 token 與成本。
- [x] **H4**（延伸）使用 **`filter_messages` + `trim_messages`**：先濾掉不需要角色/型別，再用 token 規則裁剪（可設定 `include_system`、`start_on`、`end_on`）。

**自我檢查**：節點只更新部分欄位時，其他欄位不被意外清空。

---

### 階段 I：子圖或進階路由

- [x] **I1** 將「查資料」與「寫回覆」拆成 **兩個子圖**或兩個模組化 `StateGraph`，由外層圖 **呼叫／組合**。  
- [x] **I2** 或實作 **條件路由**：先分類使用者意圖（閒聊／查價／申訴），再走不同節點鏈（不必一次到位，先 2～3 條分支即可）。

**自我檢查**：改其中一條分支的提示詞，不影響其他分支的檔案（模組邊界清楚）。

---

### 階段 J：RAG 入門（檢索 + 工具）

- [x] **J1** 準備小量文本（幾段 Markdown 或 JSON），建立 **向量儲存**（Chroma、FAISS 等擇一，依你環境能裝的為準）。  
- [x] **J2** 包一個 **`@tool`**：`query` → `similarity_search` → 回傳片段字串給模型。  
- [x] **J3** 讓代理在「需要內部知識」時呼叫該工具，並在答案中 **標示依據來自哪段檔案**（可強制在 prompt 裡要求）。

**自我檢查**：問卷外知識時模型不瞎掰，或會說「文件未載明」。

---

## 完成標準（整份第二課表）

1. **至少完成 E + G**：能說清楚 checkpoint 與串流分別解決什麼問題。  
2. **至少完成 E 或 F 之一 + J**：要嘛能續聊，要嘛能核准工具，並有一份 **可查的內部文件** 透過 RAG 接入。  
3. 新腳本與模組 **有註解或 `Docs/` 筆記**，半年後自己還看得懂如何執行。

---

## 參考文件（官方為準，版本更新時請以站內為主）

- [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)  
- [Human-in-the-loop](https://docs.langchain.com/oss/python/langgraph/interrupts)  
- [Streaming](https://docs.langchain.com/oss/python/langgraph/streaming)  
- [Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)  

---

*進度請自行把 `[ ]` 改為 `[x]`。若某階段與工作專案重疊，可跳過編號、但建議補一段筆記在 `IMPL.md` 或 `LessonLearn/`。*
