# 為什麼 `from langgraph.prebuilt import ToolNode` 會失敗？

## 錯誤訊息（範例）

```text
ImportError: cannot import name 'ServerInfo' from 'langgraph.runtime'
```

有時是在 `import` 鏈上觸發，例如：

```text
File "...langgraph\prebuilt\__init__.py", ...
File "...langgraph\prebuilt\tool_node.py", line 88, in <module>
    from langgraph.runtime import ExecutionInfo, ServerInfo
```

---

## 直接原因

`langgraph.prebuilt` 在載入 **`tool_node.py`** 時會執行：

```python
from langgraph.runtime import ExecutionInfo, ServerInfo
```

也就是：**要求同一個套件裡的 `langgraph.runtime` 模組必須提供 `ServerInfo`**。

若你安裝的 **`langgraph` 某個小版本**中，`runtime.py` **尚未定義或未匯出 `ServerInfo`**，就會在 import 當下失敗。這通常**不是你的應用程式碼寫錯**，而是 **套件內兩個檔案版本不一致**（例如 `tool_node` 已依賴新符號，但 `runtime` 還沒跟上同一版發佈）。

---

## 為什麼會「對不起來」？

常見情況包括：

- **某次小版本**裡，`prebuilt/tool_node.py` 已改成依賴新加入的 `ServerInfo`，但 **`runtime.py` 在該版尚未一併提供**（發版／打包時序問題）。
- 本機較少見：**手動覆寫或混用**不同版本的 `langgraph` 檔案。

實務上可對照：較新的 `langgraph` 會在 **`runtime.py` 中定義 `ServerInfo`**，並與 `tool_node` 的 import 一致。

---

## 怎麼處理？

### 1. 升級 `langgraph`（建議）

升級到 **已包含 `ServerInfo` 的版本**（例如本專案驗證過的 **`1.1.6`**）：

```powershell
py -3.11 -m pip install -U "langgraph>=1.1.6"
```

升級後再測：

```powershell
py -3.11 -c "from langgraph.prebuilt import ToolNode; print('OK')"
```

### 2. 專案依賴鎖檔

在 `Docs/requirements.txt`（或你的鎖檔）中將 **`langgraph`** 固定到已知可用的版本，避免未來又裝回有問題的小版。

### 3. 不依賴 `ToolNode` 的作法

在釐清／升級套件前，可以像本專案 **`practice_04_agent_graph.py`** 一樣，**手寫 `run_tools` 節點**：依 `AIMessage.tool_calls` 呼叫 `BaseTool.invoke`，並組出 **`ToolMessage`**。語意與官方 **`ToolNode`** 相近，且不觸發上述 import 鏈。

---

## 一句話整理

**不是 `ToolNode` 本身「壞掉」，而是當時安裝的 `langgraph` 版本裡，`tool_node` 需要從 `runtime` 匯入的 `ServerInfo` 不存在 → 換成修復後的版本（例如 `>=1.1.6`）通常即可。**

---

*本說明依專案實際環境（Python 3.11、`langgraph` 升級前後對照）整理，供日後複習。*
