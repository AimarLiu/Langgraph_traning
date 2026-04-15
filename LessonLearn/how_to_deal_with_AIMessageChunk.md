# 如何處理 `AIMessageChunk`：兩個常見盲點整理

這份筆記整理我在寫 `stream_mode="messages"` 時遇到的兩個盲點，避免把 `AIMessageChunk` 當成 `AIMessage` 來用。

---

## 盲點 1：`AIMessageChunk` 的 `id` 是每個都不同嗎？

**典型情況**：同一次模型回覆的多個 chunk，會帶著**同一個 message id**（因此可以分成「一批 id 相同」的 chunk，最後合併成一則完整訊息）。

**但要注意**：

- 不同 provider / 版本下，`id` 行為可能不同（例如部分 chunk `id=None`，或中途更換 id）。
- 因此工程上要把「依 `id` 合併」當作主要策略，但也要準備 fallback（例如 `__noid__`）。

**結論**：`AIMessageChunk` 的 `id` **通常不是每個都不同**，而是「一批 chunk 共用同一個 id」組成完整回覆。

---

## 盲點 2：`stream_state['chunk_acc'].values()` 到底是什麼？為什麼要 `max(..., key=...)`？

假設你用一個 dict 來累積 chunk：

- `chunk_acc: dict[str, AIMessageChunk]`
- key = `AIMessageChunk.id`
- value = 「目前為止把同一個 id 的所有 chunk 用 `+` 合併後的結果」

### 2.1 `chunk_acc.values()` 會得到什麼？

會得到很多個 `AIMessageChunk`，但它們是「**已經合併過**」的：

- 每個 value 代表一個 id 的**累積訊息**
- 不是單一 token chunk，而是「那個 id 到目前為止的完整拼接」

因此 `chunk_acc.values()` 不是「一堆零碎片段」，而是「每個 id 一個累積結果」。

### 2.2 `key=lambda c: len(_text_from_ai_message(c))` 在做什麼？

這通常出現在：

```python
best = max(chunk_acc.values(), key=lambda c: len(_text_from_ai_message(c)))
```

它的意思是：

- `max(...)` 要挑出「最大」的那個元素
- `key=...` 告訴 `max`：不要直接比物件本身，改用 `key(obj)` 的結果來比較
- `lambda c: ...` 是一個匿名函式（輸入一個 chunk `c`，輸出一個數值）
- `_text_from_ai_message(c)` 把 chunk 的 content 轉成純文字字串
- `len(...)` 算字串長度（字元數）

所以整句就是：

> 在所有「已累積的 AIMessageChunk」中，挑出「轉成文字後最長」的那一個。

### 2.3 為什麼要用「最長」當 fallback？

當你**拿不到節點輸出中的完整 `AIMessage`**（例如只收到 messages 串流事件）時，你仍想在最後印出「最像最終答案」的文字。

這時用「最長」是個簡單但可用的 heuristic：

- 最長的累積內容，通常最接近最終回答

如果你想更嚴謹，可以另外記 `last_chunk_id`（最後一次看到的 chunk id），結尾直接取 `chunk_acc[last_chunk_id]`，避免「某個較長的舊訊息」被挑中。

---

## 實務建議（寫 `stream_mode="messages"` 時）

- **不要把 `AIMessageChunk` 當作 `AIMessage` 直接拿來當最後答案**；先用 `+` 依 `id` 合併。
- 優先用「節點更新 state 後的完整 `AIMessage`」當最終輸出；只在沒有完整 `AIMessage` 時才用 chunk 累積結果當 fallback。
- 對 `id=None` 的情況要有 fallback key，並盡量搭配 metadata（例如節點名）避免混流。

