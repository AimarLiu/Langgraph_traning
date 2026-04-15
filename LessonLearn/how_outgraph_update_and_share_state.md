# 外層圖與子圖的 State 傳遞：更新與共享

## 一句話先說結論

- 外層圖不會直接操作「子圖 State 型別」本身。
- 外層圖會接收子圖節點回傳的 **state 更新字典**，再合併到外層共享 state。

---

## 常見疑問

### Q1：子圖只會更新自己的 State 嗎？

是。子圖函式只會回傳它定義要更新的欄位（例如 `{"facts": [...]}`）。

### Q2：子圖之間會直接拿彼此的 State 嗎？

不會直接互拿。  
子圖 A 的更新會先回到外層 state，再由外層把當前 state 傳給子圖 B。

### Q3：外層圖看得到子圖 State 嗎？

精準說法是：

- 看得到「子圖回傳的欄位資料更新」
- 看不到「子圖型別定義物件」本身

因此實務上會感覺外層能看到子圖結果（例如 `facts`、`answer`）。

---

## 以 I1 為例（研究子圖 -> 回覆子圖）

- `ResearchState`：`question`, `facts`
- `ComposeState`：`question`, `facts`, `answer`
- `I1State`（外層）：`question`, `facts`, `answer`

流程：

1. 外層把當前 state 傳給 `research` 子圖。
2. `research` 回傳 `{"facts": ...}`。
3. 外層合併後，`facts` 進入外層 state。
4. 外層再把更新後 state 傳給 `compose` 子圖。
5. `compose` 回傳 `{"answer": ...}`，再合併回外層。

---

## 設計原則（實務）

- 外層 state 通常是共享欄位的 **superset（超集合）**。
- 子圖只宣告自己最小必需欄位，降低耦合。
- 想跨子圖傳遞資料，請使用同名欄位（例如都用 `facts`）。
- 若同欄位需累加，才在該欄位設 reducer（例如 list 用 `operator.add`）。

---

## 外層圖何時要用 reducer 合併？

### 建議使用 reducer 的時機

- 同一欄位可能被多個節點更新，且你要「保留多筆結果」而非最後一筆覆蓋。
- 欄位是累積型資料：如 `events`、`approval_logs`、`trace_steps`、`errors`。
- 有並行分支（fan-out/fan-in）會同時回寫同欄位。
- 子圖 A/B 都會回寫同欄位，且要合併而不是互蓋。

### 可以不用 reducer 的時機

- 欄位本質是單值，且你就是要最後寫入生效（例如 `answer`、`intent`）。
- 欄位只會由單一路徑、單一節點更新，不存在競合。

### 常用選型

- `list` 累加：`operator.add`
- `messages`：`add_messages`（LangGraph 專用）
- `dict` 局部更新：自訂 `merge(left, right)`（例如 `left | right`）

### 快速判斷

如果你在問「這個欄位要不要 reducer？」  
可先問自己：**我要保留歷史/多來源，還是只要最後結果？**

- 要保留多來源 -> 用 reducer
- 只要最後結果 -> 不用 reducer（覆蓋即可）

---

## 常見錯誤

- 以為子圖可以直接讀寫別的子圖內部型別或私有欄位。
- 外層沒有該共享欄位，導致子圖輸出無法被下一段流程使用。
- 欄位同名但資料結構不一致（例如前一段是 `list[str]`，後一段當 `dict` 使用）。

---

## I1 實例：哪些欄位適合 reducer？

以目前 I1（`research -> compose`）來看：

- `facts`：
  - **現況（單一路徑）**：`research` 主要寫入一次，不一定需要 reducer。
  - **未來（多來源）**：若加第二個研究子圖（例如 `research_fx` + `research_crypto`）都回寫 `facts`，就建議改成 list reducer（例如 `operator.add`）。
- `answer`：
  - 通常是最後成品，建議維持「最後寫入覆蓋」即可，不需要 reducer。
- `question`：
  - 常作為輸入參數，不做累積，通常不需要 reducer。

結論：  
I1 現版可不加 reducer；若要演進成多研究分支合流，優先把 `facts` 改成 reducer 欄位。
