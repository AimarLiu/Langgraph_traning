# 「長記憶」與「短記憶」：Checkpoint 和 Store（namespace）差在哪？

## 先釐清：不是「有沒有資料庫」

書籍或文章常把 **Store + namespace** 說成「長記憶」，把 **Checkpoint** 說成「短記憶」。容易讓人誤會成：**Checkpoint 換成 SQLite／Postgres 持久化，不就也變成長記憶了？**

重點在於：**持久化只解決「資料會不會不見」**，不決定「記憶的語意與定址方式」。區分兩者要看 **存的是什麼、用什麼 key 取出來、給誰用**。

---

## Checkpoint（含資料庫後端）在做什麼

- 存的是 **這條圖在某一個 thread（對話／執行緒）裡的「執行狀態」**：例如 `state` 裡的 `messages`、目前走到哪個節點、`next` 是誰、checkpoint id 等。
- **定址方式**主要是 **`thread_id` +（可選）`checkpoint_id`**——也就是「這一輪對話／這一條 run」的時間軸與快照。
- 換成資料庫後端，只是讓這些狀態 **可持久、可重啟、可多進程共用儲存**，本質仍是 **「這個 thread 的對話／執行快照」**，不是內建成「全系統任意 key 的長期知識庫」。

因此：**E 階段刻意選資料庫儲存 Checkpoint，仍然是 Checkpoint 語意**——長的是 **同一 thread 狀態的壽命與可靠性**，並不自動等於「跨使用者、跨對話的長記憶」。

---

## Store + namespace（常說的長記憶）在做什麼

- 存的是 **你為產品定義的、通常可跨 thread 使用的資料**：使用者偏好、摘要過的事實、長期 profile、從文件抽出的條目等。
- **定址方式**是 **namespace（再搭配常見的 key 設計）**，例如依 `user_id`、`org_id`、`project_id` 分桶；**新開一個 thread、新對話**仍可依同一 namespace 讀回。
- 和「這條 graph 目前 `messages` 裡有什麼」是 **不同一層**：Store 是 **應用／產品層的記憶抽象**；Checkpoint 是 **這次圖執行的狀態機快照**。

一句話對照：

| 概念 | 一句話 |
|------|--------|
| **Checkpoint** | **這條對話（thread）的狀態怎麼接續、還原、重播。** |
| **Store + namespace** | **你希望系統「記住」的東西怎麼跨對話、跨 session 取用。** |

---

## 為什麼會覺得兩者重疊？

- 若只使用 **單一 thread**，永遠在同一條對話裡聊，**只靠 checkpoint 裡越堆越長的 `messages`**，體感上就像「一直記得」——但那是 **同一 thread 的對話歷史**，不是通用的「使用者長期記憶」模型。
- 若需要 **新開 thread 仍帶著舊偏好／舊事實**，通常會 **寫入 Store（或你自己的資料表／向量庫）**，在呼叫模型前依 namespace 取出再注入 prompt 或 state，而不是只靠新 thread 的 checkpoint。

---

## 使用時機（實務上怎麼選）

| 需求 | 較適合 |
|------|--------|
| 同一對話接續、重播、time travel、人類在環路暫停再繼續 | **Checkpoint**（thread 狀態） |
| 新對話也要記住使用者是誰、偏好、長期事實、跨專案知識 | **Store + namespace**（或自建表／向量庫） |
| 單一 thread 內上下文太長要壓縮 | 常見做法是 **摘要寫回 Store 或 state**，checkpoint 仍負責保存當前執行狀態 |

---

## 小結

- **DB Checkpoint**：把「短記憶」變成 **可靠、可還原的持久狀態**（針對 **thread**）。
- **Store + namespace**：另一套 **定址空間**（常 **跨 thread**）的長期記憶。
- 兩者 **可以同時用**：Checkpoint 管流程與對話接續；Store 管使用者／專案級要長期保留的內容。

（與 `practice_06_checkpoint_memory.py` 等 Checkpoint 練習搭配閱讀時，可把該檔當作「thread 狀態與快照」的實作脈絡。）
