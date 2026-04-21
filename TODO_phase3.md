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

- [x] **N1** 在現有 Chroma 流程上加上 rerank 或 hybrid 其中一種。  
- [ ] **N2**（選修）查詢改寫／Multi-query。  
- [ ] **N3** 維持可追溯依據。  

#### N1 可落地 Pipeline（建議先 Hybrid 再 Rerank）

- [x] **N1-P1 檢索召回層（Hybrid）**：並行執行 `keyword(BM25)` 與 `vector(Chroma)`，各取 `top_k=10`。  
- [x] **N1-P2 去重與分數合併**：以 `doc_id/source+chunk_index` 去重，保留每篇文件的兩種原始分數。  
- [x] **N1-P3 混合排序**：做 min-max normalize 後加權排序（初始 `vector=0.6`、`keyword=0.4`），取 `top_n=20`。  
- [x] **N1-P4 精排層（Rerank）**：對 `top_n=20` 做 rerank，輸出 `rerank_score`，再取 `final_top_k=5`。  
- [x] **N1-P5 生成與引用 (citations 保留)**：只餵 `final_top_k` 進 LLM，輸出答案時保留 citations（來源、段落、分數）。  
- [x] **N1-P6 可觀測性**：在 log/trace 保留 `query -> retrieve -> hybrid_score -> rerank_score -> final_docs`。  
- [x] **N1-P7 驗收指標**：至少用 5~10 題 golden set 比較「baseline vector-only」vs「hybrid+rerank」的命中率與答案品質。  

##### N1-Pipeline 建議對應檔案

- [x] `src/langgraph_learning/tools/rag_lilian.py`：加入 hybrid merge + normalize + rerank 入口。  
- [x] `practice_16_rag_advanced_smoke.py`：增加 baseline / hybrid / hybrid+rerank 三種模式 smoke 比對。  
- [x] `TODO_phase3.md`：完成後勾選 N1 與 N1-P1~P7。  

#### N-CRAG-path（修正型檢索分支）

- [ ] **NC1** 加入「檢索品質判斷節點」（如：top-k 分數門檻、來源覆蓋率）。  
- [ ] **NC2** 判斷不通過時啟動 corrective loop（query rewrite 或 fallback 檢索）。  
- [ ] **NC3** 輸出保留「初次檢索 vs 修正後檢索」對照摘要，便於回歸檢查。  

#### N-Adaptive-path（動態路由分支）

- [ ] **NA1** 新增問題路由節點（`direct` / `basic_rag` / `deep_rag`）。  
- [ ] **NA2** `deep_rag` 路徑套用 multi-query 或 rerank，其他路徑維持較低成本。  
- [ ] **NA3** 統一各路徑輸出欄位（answer / citations / route），方便評測比較。  

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
