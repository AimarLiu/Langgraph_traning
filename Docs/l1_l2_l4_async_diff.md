# L1 / L2 / L4 非同步演進對照（路由／模型節點／ToolNode）

> 範圍：第三課表 L 階段，聚焦 `POST /chat` 路由、`call_model` 節點、`ToolNode` 執行工具三段的同步/非同步演進。  
> 目的：快速回答「目前哪一段已 async、哪一段仍可能阻塞 event loop」。

---

## 一張表看懂差異

| 階段 | 路由層（FastAPI） | 模型節點（`call_model`） | 工具節點（`ToolNode`） | 事件迴圈觀察重點 |
|------|-------------------|--------------------------|------------------------|------------------|
| **L1** | `async def chat` + `await graph.ainvoke(...)` | `llm_bound.invoke(...)`（同步） | 若工具有 coroutine，`ToolNode` 走 `ainvoke` | 工具 I/O 可讓出 loop；模型等待仍偏同步阻塞 |
| **L2** | 同 L1，另加 `thread_id/user_id -> config["configurable"]` + checkpoint | `llm_bound.invoke(...)`（同步） | 同 L1（搭配 K2 async 工具） | 對話可接續，但模型節點仍是主要阻塞點 |
| **L4** | 同 L2 | `await llm_bound.ainvoke(...)`（非同步） | 同 L2 | 路由、模型、工具皆走 async 路徑（仍受單進程/GIL與外部 API 延遲影響） |

---

## 三段拆開看（為何會有體感差異）

### 1) 路由層（`POST /chat`）

- L1 起就採 `await graph.ainvoke(...)`，可與 ASGI 事件迴圈配合。  
- L2 補上 `thread_id/user_id` 映射到 `config["configurable"]`，讓 checkpoint 可定址並跨請求接續。  
- 路由本身 async，不代表圖內每個節點都 async；要配合模型/工具節點實作一起看。

### 2) 模型節點（`call_model`）

- L1/L2：使用 `llm_bound.invoke(...)`，即使外層走 `ainvoke`，此節點仍可能長時間佔住 worker 執行緒。  
- L4：改為 `await llm_bound.ainvoke(...)`。  
- 專案中保留了舊寫法註解，方便對照：
  - 新：`ai = await llm_bound.ainvoke(model_messages)`
  - 舊（註解）：`# ai = llm_bound.invoke(model_messages)`

### 3) 工具節點（`ToolNode`）

- K2 起市場工具提供 coroutine 實作；`ToolNode` 在 async 路徑會走 `tool.ainvoke`。  
- 因此 L1/L2 時「工具等待」通常已可讓出事件迴圈。  
- L4 不改 ToolNode 行為；主要補齊的是模型節點 async。

---

## 實務結論（給排錯與效能觀察）

- **若 L1/L2 感到併發效益不明顯**：先看模型節點是否仍同步 `invoke`。  
- **若做完 L4 仍慢**：多半是外部模型/API 延遲、工具端 API 延遲，或部署資源（worker、CPU、連線）限制。  
- **checkpoint 相關問題**：優先檢查 `thread_id` 是否固定且有傳入 `config["configurable"]`。  

---

## 參考檔案

- `src/api/routes/chat.py`
- `src/api/app.py`
- `src/langgraph_learning/graphs/agent_graph.py`
- `src/langgraph_learning/tools/market.py`
- `Docs/checkpointer_in_services.md`
