# 第三課表：走向「可上線」的代理應用（API · 非同步 · 評測 · 進階 RAG／多代理）

> **前置**：已完成 `TODO.md` 與 `TODO_phase2.md`（含 checkpoint、串流、HITL、狀態與子圖、RAG 入門）。  
> **目標**：在既有 `src/langgraph_learning/` 架構上，補齊產品化常見能力：對外服務介面、非同步與資源管理、可重複的品質驗證，以及選修的進階檢索／多代理模式。

---

## 建議對應檔名（可依喜好調整）

| 檔案（建議） | 用途 |
|--------------|------|
| `practice_13_async_agent.py` | K：圖的 `ainvoke`／`astream`，必要時 async tool |
| `practice_14_fastapi_agent.py` | L：FastAPI 掛載 `compile()` 後的 graph；L1/L2 打通 API + checkpoint |
| `practice_15_eval_smoke.py` | M：LangSmith Dataset／Evaluator 或本機 golden 測試雛型 |
| `practice_16_rag_advanced_smoke.py` | N：RAG 加深（reranker 或 hybrid） |
| `practice_17_supervisor_or_multi.py` | O：督導節點 + 兩條子能力 |

---

## 課表（建議順序）

### 階段 K：非同步與資源生命週期

- [x] **K1** 將一輪對話改為 `await graph.ainvoke(...)`（或 `astream`），確認與同步行為一致。  
- [x] **K2**（選修）工具為 I/O 密集時改為 async 或 Runnable，避免阻塞 event loop。  
- [x] **K3** 釐清 checkpointer 在常駐服務（long-running service）中的建立時機；已記錄於 `Docs/checkpointer_in_services.md`。  

### 階段 L：HTTP 外殼（最小 API）

- [x] **L1** 用 FastAPI 暴露 `POST /chat`：body 含 `message`，回傳最後一則 AI 文字；並在程式註解標註 async/sync 邊界。  
- [x] **L2** 將 `thread_id`（與選修 `user_id`）從 header 或 body 傳入 `config["configurable"]`，與 checkpoint 銜接。  
- [x] **L3**（選修）`GET /health` + `pydantic-settings`，且不把敏感資訊打入 log。  
- [x] **L4**（選修）在 `build_agent_graph` 的 `call_model` 將 `llm_bound.invoke` 改為 `await llm_bound.ainvoke`，並更新註解。  

### 階段 M：評測與回歸

- [x] **M1** 建立小型 golden 集（5～10 筆）。  
- [x] **M2**（選修）接上 LangSmith Dataset + Evaluation 或 LLM-as-judge。  
- [x] **M3** 在 pytest 或腳本中跑 smoke。  

### 階段 N：RAG 管線加深（擇一主線）

- [ ] **N1** 在現有 Chroma 流程上加上 rerank 或 hybrid 其中一種。  
- [ ] **N2**（選修）查詢改寫／Multi-query。  
- [ ] **N3** 維持可追溯依據。  

### 階段 O：督導與多能力組合（輕量 multi-agent）

- [ ] **O1** 增加督導節點做任務判斷再路由。  
- [ ] **O2**（選修）兩個專家子圖共享狀態子集。  
- [ ] **O3** 記錄單代理 vs 多代理邊界，避免過度設計。  

### 階段 P（選修）：長期記憶與跨 thread

- [ ] **P1** 閱讀官方 Store 概念。  
- [ ] **P2**（選修）實作跨對話偏好寫入／讀回。  

---

## 完成標準（整份第三課表）

1. 至少完成 K + L（含 L1、L2）：具可對外呼叫的最小服務，理解 async 與 thread_id/checkpoint。  
2. 至少完成 M 或 N 之一：可重跑評測，或 RAG 有明確深化。  
3. O、P 為選修：依專案需求決定是否深入。  
