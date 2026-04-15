# Checkpointer 與服務生命週期：用處、好處，與「何時建立」

> 對應第三課表 **K3**：釐清 **checkpointer／連線** 在 **常駐服務**中的建立時機，並採用一種清楚的模式（本專案建議見文末「本專案採用」）。

---

## 用語對照（避免「長跑」在中文裡聽起來怪）

| 中文（建議） | 英文（業界常用） | 說明 |
|--------------|------------------|------|
| **常駐服務**、**持續運行的服務** | **long-running service** | 指 **進程啟動後長時間活著**、持續處理請求（例如掛在 uvicorn / gunicorn 後面的 FastAPI）。 |
| 不建議直譯成 | ~~long-term service~~ | **long-term** 多指「長期合約／長期專案」，**不是**這裡說的行程生命週期。 |

先前若寫「長跑服務」，語意上想表達的就是 **long-running service（常駐、非跑完就退出的腳本）**。

---

## 一、Checkpointer 有什麼用？（先懂價值）

| 能力 | 說明 |
|------|------|
| **跨多次呼叫保留狀態** | 同一個 `thread_id` 下，後續 `invoke`／`ainvoke` 能接續前一次的對話與圖狀態（與 `add_messages` 等 reducer 搭配）。 |
| **Human-in-the-loop** | 有 `interrupt_before`／`interrupt_after` 時，必須有 checkpointer 才能把「暫停點」寫入，之後用同一 `thread_id` **恢復**（`invoke(None, ...)` 等）。 |
| **除錯與審計** | 可搭配 `get_state_history`、`get_state` 做歷程檢視（Phase2 E3）。 |

沒有 checkpointer（或沒有固定儲存後端）時，**行程一結束或每次新開圖**，對話狀態就不在，**無法**做「同一使用者隔天再聊仍接續」的產品行為（除非你自己另存資料庫）。

---

## 二、常駐服務裡為什麼要談「建立時機」？

腳本（例如 `practice_06_checkpoint_memory.py`）常用：

```python
with SqliteSaver.from_conn_string("...") as checkpointer:
    app = build_agent_graph(checkpointer=checkpointer)
    # 同一個 with 區塊內多次 invoke
```

**行程結束就關連線**，很直覺。但 **HTTP 常駐服務**是：

- 進程**一直活著**；
- **每個請求**都會呼叫 `app.invoke`／`ainvoke`；
- 若你**每個請求**都 `SqliteSaver.from_conn_string` + `build_agent_graph` 再 `compile`，會有兩類問題：

1. **成本**：重複 **編譯圖**、重複建立 **SQLite 連線／Saver**，延遲與資源浪費。
2. **語意**：同一個使用者、同一 `thread_id` 應共用**同一個**持久化後端與**同一張**已編譯的圖；若每次請求亂開新庫或新圖實例，行為容易與預期不符。

因此 K3 要釐清：**Saver／已編譯的 `app` 應在「進程／生命週期」哪一層建立一次，並在請求裡重複使用**。

---

## 三、兩種直覺模式（對照）

| 模式 | 做法（概念） | 優點 | 注意 |
|------|----------------|------|------|
| **每請求新建** | 每個 HTTP 請求內 `from_conn_string` + `compile` | 實作時好像「乾淨」 | 通常 **慢**、**浪費連線**；除非刻意隔離（極少見）。 |
| **全域／生命週期單例** | 在 **FastAPI `lifespan`**（或等同的 startup）建立 **一個** `SqliteSaver`（或 async 版）、**一個** `compile(..., checkpointer=...)` 的 `app`，請求裡只拿來 `invoke`／`ainvoke` | 符合 **long-running service** 常態；**同一 DB 檔**、**同一 thread_id** 自然接續 | 需處理 **關閉**（shutdown 時離開 `with` 或關連線）；多 **worker** 時見下文。 |

**請求裡要帶的**主要是 **`config["configurable"]["thread_id"]`**（以及之後 L2 的 `user_id` 等），**不是**每次重建 checkpointer。

---

## 四、同步 `SqliteSaver` 與 `AsyncSqliteSaver`（選型提示）

- 本專案 Phase2 腳本使用 **`langgraph.checkpoint.sqlite.SqliteSaver`**（同步），搭配 `with ... as` 管理生命週期即可。
- 若 API 層**全鏈路 async**（`ainvoke` + 非同步儲存），官方建議可評估 **`AsyncSqliteSaver`**（`langgraph.checkpoint.sqlite.aio`，需 `aiosqlite`）。  
- 選哪個依你的部署與套件版本為準；**重點仍是「每進程／每生命週期少次建立，請求內重用」**，而非每請求新建。

---

## 五、多進程、多 Worker，與「水平擴展多台機器(分散式)時為何換成 Postgres」

### 先對齊幾個詞（中英）

| 中文 | 英文 | 白話 |
|------|------|------|
| **水平擴展** | **horizontal scaling** / **scale out** | **加機器、加副本**：從 1 台 API 變成多台，每台都跑一份應用程式，一起分擔流量。 |
| **多實例** | **multiple instances** / **replicas** | **多份**「同一套程式」同時在跑：可能是 **多 process（多 worker）**、也可能是 **多台機器各一個或多個 process**。 |
| **同一儲存** | **shared storage** / **shared checkpoint backend** | 大家**讀寫同一個持久化後端**：不是 A 機一份 SQLite 檔、B 機另一份；而是**連到同一個**（通常）**網路可達的資料庫**。 |

### 單機多 worker 時，SQLite 發生什麼事？

- **同一台機器、同一個 SQLite 檔案**，可以給 **多個進程** 用（常見是 uvicorn `--workers 4` = 4 個進程），SQLite 會用 **檔案鎖／WAL（Write-Ahead Logging）** 協調誰能寫。
- 仍有一些**限制與競爭**：高併發寫入時，可能遇到鎖等待；**教學／小流量**通常夠用。

### 「水平擴展多機」時，為什麼常改成 Postgres（或類似）checkpointer？

- **多台機器**上若各自放 **本地路徑的 `xxx.sqlite`**，每台磁碟上的檔案**彼此不相通**：使用者的 `thread_id` 若被負載平衡打到**另一台機**，就**讀不到**上一台寫的 checkpoint，對話會「斷掉」。
- 解法不是「把 SQLite 檔放在 NFS 硬掛給大家」（常難調又容易出詭異問題），而是改成 **大家連到同一個集中式資料庫**（常見是 **PostgreSQL**），由 **Postgres checkpointer**（或官方支援的後端）把 checkpoint **存在 DB 的表**裡。

### 那「多實例同時寫」不會打架嗎？不用鎖嗎？

- **要協調併發**，但不是你在應用程式裡自己對「整份檔案」加一個大鎖而已。
- **關係型資料庫**（如 PostgreSQL）會用 **交易（transaction）**、**列／索引上的鎖**、**隔離層級** 等機制，保證：
  - 不同 `thread_id` 的列可以**併發更新**；
  - 同一 `thread_id` 的連續 checkpoint 會以**事務順序**寫入，**不會**兩筆更新混在一起變成「資料混亂」。
- 簡單說：**鎖與一致性由資料庫引擎負責**；LangGraph 的 checkpointer 實作會依官方設計對 DB 做讀寫。你仍然要選**支援併發的後端**，並在架構上讓**所有 API 實例**連**同一個** DB。

### 小結

| 場景 | 常見做法 |
|------|----------|
| 本機學習、單 worker | 單一 SQLite 檔 + **單例 Saver + 單例 compiled graph** 即可對齊 K3。 |
| 單機多 worker | 仍可能共用**同一 SQLite 檔**（視鎖與負載）；要注意競爭。 |
| **horizontal scaling（多機）** | **shared checkpoint backend**（例如 **Postgres**），讓 **multiple instances** 都寫進 **同一儲存**，再用負載平衡分流請求。 |

---

## 六、本專案在 K3 採用的說法（給 L 階段銜接）

**建議模式（常駐 HTTP 服務／long-running service）**：

1. **啟動時（lifespan / startup）**：建立 **一個** 指向 `data/langgraph_checkpoints.sqlite`（或你設定的路徑）的 **SqliteSaver**（或 Async 版），並 **`build_agent_graph(checkpointer=...)` 後 `compile` 一次**，將結果放在 **app state**（例如 `app.state.graph`）。
2. **每個請求**：只組 **`config`**（含 **`thread_id`**），呼叫 **`await graph.ainvoke(input, config=config)`**，**不要**每請求重新 `compile`。
3. **關閉時（shutdown）**：依所用 API **關閉 saver／連線**（若使用 `with` 包在 lifespan 裡，離開時即關閉）。

**練習腳本**（`practice_06` 等）維持 **`with SqliteSaver...`** 包住整段示範，與「服務單例」是同一概念的不同包裝：**限制 saver 生命週期在「這段執行期」內建立一次**。

---

## 相關檔案

| 檔案 | 說明 |
|------|------|
| `src/langgraph_learning/graphs/agent_graph.py` | `build_agent_graph(checkpointer=...)` |
| `practice_06_checkpoint_memory.py` | 腳本內 `with SqliteSaver` + 同 thread 多輪 |
| `Docs/env_and_run.md` | checkpoint 檔路徑與 `.gitignore` 提醒 |

---

## 官方文件（路徑以站內最新為準）

- [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)  
- [Application Structure](https://docs.langchain.com/oss/python/langgraph/application-structure)  

---

*K3：釐清「為何要在意建立時機」與「常駐服務建議單例重用」；實際 FastAPI 範例見第三課表 L 階段（`practice_14_fastapi_agent.py` 規劃）。*
