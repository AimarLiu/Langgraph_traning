# C-RAG 與 Adaptive-RAG 的差異

## 先說結論（對照目前 N 階段）

以目前 `TODO_phase3.md` 的 N 階段定義來看（`rerank/hybrid`、`query rewrite/multi-query`、可追溯依據），
它比較接近「**進階版傳統 RAG**」，而不是完整的 **C-RAG** 或 **Adaptive-RAG**。

---

## 什麼是 C-RAG（Corrective RAG）

**核心精神：**  
先做檢索，再「判斷檢索品質是否足夠」，若不足就啟動修正流程（correction loop）。

常見流程：

1. retrieve（初次檢索）
2. evaluate retrieval quality（相關性/涵蓋率/可信度判斷）
3. corrective action（query 重寫、重檢索、換檢索策略，甚至 fallback 到外部來源）
4. 再生成答案 + 保留依據

關鍵辨識點：

- 有沒有明確「**檢索品質評估節點**」
- 有沒有「**評估失敗 -> 自動補救**」的閉環

---

## 什麼是 Adaptive-RAG

**核心精神：**  
不是每個問題都走同一條 RAG pipeline，而是先判斷問題型態，再動態選擇路徑。

常見策略：

- 簡單常識題 -> 直接回答（no retrieval）
- 需要內部知識 -> 基礎 RAG
- 高風險或多跳問題 -> 深度 RAG（multi-query、rerank、更多工具）

關鍵辨識點：

- 有沒有明確「**路由器（router/policy）**」
- 有沒有「**依問題類型/難度切換檢索強度**」

---

## C-RAG vs Adaptive-RAG（一句話版）

- **C-RAG**：重點在「檢索品質不佳時如何修正」。
- **Adaptive-RAG**：重點在「不同問題走不同檢索策略」。

---

## 對你目前課表 N 階段的定位

目前 N 階段項目屬於：

- retrieval quality 的優化元件（rerank/hybrid）
- query 端優化（rewrite/multi-query）
- answer traceability（可追溯依據）

所以更精確可稱為：  
**Advanced RAG building blocks（進階 RAG 組件）**。

如果要更像 C-RAG：

- 新增 retrieval quality judge 節點
- 明確定義 fail 時的 corrective actions（重寫/重查/fallback）

如果要更像 Adaptive-RAG：

- 新增問題路由器（intent/complexity/risk）
- 定義不同問題類型對應的 RAG pipeline

---

## 實作建議（最小可落地）

### C-RAG 最小版

1. `retrieve -> judge -> (pass) answer / (fail) rewrite+retrieve -> answer`
2. judge 先用規則（top-k 分數門檻 + 來源數量）即可
3. 保留「第一次檢索」與「修正後檢索」對照資訊

### Adaptive-RAG 最小版

1. `route_question` 節點先分流：`direct` / `basic_rag` / `deep_rag`
2. `deep_rag` 再加 multi-query 或 rerank
3. 每條路徑都回傳相同輸出欄位，方便後續評測比較


### 建議路線：

- 先走主線：N -> O -> P
    - 先把「可用功能面」做完整
    - 累積足夠 baseline，後面比較容易看出分支優化是否真的有效
- 再走分支：NC -> NA
    - NC（C-RAG）是在 N 主線上加「檢索品質判斷 + 補救閉環」
-   NA（Adaptive-RAG）是在 N/O 的基礎上加「動態路由策略」

這樣做的好處：

- 不會一開始就把架構複雜度拉太高
- 你可以先有一套穩定可跑的基準，再做分支實驗
- 評測（M 階段）也更好對照主線 vs 分支差異

所以結論：可以，而且推薦。
