# F2（恢復）怎麼用：行為摘要與須知

本筆記整理 `practice_07_interrupt_hitl.py` 的 F2 重點，方便操作時快速查閱。

## F2 行為摘要

| 模式 | 作法 | 說明 |
|------|------|------|
| **核准**（預設） | `invoke(None, config)` | 與官方「靜態斷點」建議一致：放行下一個節點，接著會跑 `run_tools` 再 `call_model`。 |
| **拒絕** | `Command(update={"messages": [RemoveMessage, 新 AIMessage]}, goto=END)` | 先移除最後一則帶 `tool_calls` 的 `AIMessage`，再放入「無工具呼叫」的新訊息，最後直接結束圖。 |
| **改參** | 先 `Command(update=...)` 修改 `tool_calls` 參數，再 `invoke(None, config)` | 示範人為改工具參數（如 `symbol`）後，再放行執行工具。 |

## 常用指令

```powershell
py -3.11 practice_07_interrupt_hitl.py
py -3.11 practice_07_interrupt_hitl.py --resume reject
py -3.11 practice_07_interrupt_hitl.py --resume edit
py -3.11 practice_07_interrupt_hitl.py --f1-only
```

## 須知

1. **先分清兩種中斷**
   - 靜態斷點：`interrupt_before` / `interrupt_after`（本階段用這種）
   - 節點內中斷：在節點函式內呼叫 `interrupt()`

2. **恢復方式不同**
   - 靜態斷點恢復：官方建議 `invoke(None, config)`。
   - 節點內 `interrupt()`：用 `Command(resume=...)`。

3. **拒絕／改參的關鍵**
   - 本範例用 `RemoveMessage + 新 AIMessage` 取代最後一則 pending tool call。
   - 這做法依賴最後一則 `AIMessage` 有 `id`，才能精準替換。

4. **配額錯誤不等於流程錯誤**
   - 若出現 Gemini `429 RESOURCE_EXHAUSTED`，通常是 API 配額問題，非 F2 邏輯錯誤。

5. **資料落地**
   - Checkpoint 會寫到 `data/langgraph_hitl.sqlite`，可用同一 `thread_id` 接續。

## 與程式碼對照（函式地圖）

- `_f2_approve(app, config)`  
  - 對應「核准」路徑。  
  - 直接 `app.invoke(None, config)`，讓圖從 `interrupt_before=['run_tools']` 的斷點繼續。

- `_f2_reject(app, config, last_ai)`  
  - 對應「拒絕」路徑。  
  - 先建立新的 `AIMessage`（清空 `tool_calls`），再用 `RemoveMessage(id=...)` 移除原訊息，最後 `Command(..., goto=END)` 直接結束流程。

- `_f2_edit_symbol(app, config, last_ai, new_symbol)`  
  - 對應「改參」路徑。  
  - 深拷貝原本 `tool_calls` 後修改參數（範例是 `symbol`），先 `Command(update=...)` 回寫狀態，再 `invoke(None)` 放行工具。

- `main()` 的參數路由  
  - `--resume approve|reject|edit` 會選擇上述三條 F2 分支。  
  - `--f1-only` 只做到中斷點檢查，不做 F2 恢復（省成本）。

## 延伸

- F3 可在 state 新增審批紀錄（例如：`approved_by`、`approved_at`、`decision`）與操作備註。
- 官方文件：[Human-in-the-loop](https://docs.langchain.com/oss/python/langgraph/interrupts)

