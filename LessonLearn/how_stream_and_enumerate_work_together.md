# `app.stream()` 與 `enumerate()` 怎麼一起運作

這份筆記整理一個常見疑問：`app.stream()` 是不是 polling？以及它怎麼知道「最後一筆」。

---

## 核心觀念：`app.stream()` 不是 polling

`app.stream()` 比較像「**內部事件佇列（queue）+ Python generator**」：

- 圖在執行每個步驟（例如 `call_model`、`run_tools`）時，會把事件放進內部 queue。
- `stream()` 會一邊推進圖，一邊把 queue 裡事件 `yield` 出來。
- `for chunk in app.stream(...)` 是在**消費已產生的事件**，不是固定時間去問遠端「有沒有新資料」。

因此它和一般「每秒打 API 查一次」的 polling 模式不同。

---

## `enumerate()` 在這裡做什麼

常見寫法：

```python
for i, chunk in enumerate(app.stream(inputs, config=config, stream_mode=mode), 1):
    print(i, chunk)
```

`enumerate()` 只負責：

- 幫每個 `yield` 出來的 chunk 編號（`1, 2, 3, ...`）
- 方便你列印與除錯

它**不參與串流協定**，也不決定資料何時到來。

---

## 怎麼判斷「最後一筆」？

通常沒有 `is_last=True` 這種欄位。結束信號是：

1. 圖跑到終點（`END`）或停止條件（例如中斷、錯誤、遞迴上限）。
2. runtime 把 queue 的剩餘輸出 flush 完。
3. generator 正常結束（`StopIteration`）。
4. `for` 迴圈自然離開。

所以你的程式通常寫成：

- 在 `for` 裡持續處理 chunk
- `for` 結束後做「最終摘要 / done」輸出

---

## 實務建議

- 將「是否完成」建立在 **`for` 是否結束**，不要硬猜某個 chunk 是最後一筆。
- 以 `try/except` 區分：
  - 正常結束（回圈自然完成）
  - 異常結束（例如 API 429、timeout、網路錯誤）
- 若要 UI 顯示進度，`enumerate` 的 `i` 可以直接當事件序號。

