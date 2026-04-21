# rerank 和 hybrid 是什麼？有什麼不同？

這兩個概念都常出現在 RAG，但解決的是不同問題：

- `hybrid`：解決「怎麼找資料（召回）」  
- `rerank`：解決「怎麼把找到的資料排好（精排）」

---

## 1) hybrid（混合檢索）

`hybrid retrieval` 會把兩種（或以上）檢索訊號一起用，常見是：

- 關鍵字檢索（例如 BM25，擅長精準詞）
- 向量檢索（semantic，擅長語意相近）

實務上通常是：

1. keyword 先取一批候選
2. vector 再取一批候選
3. 合併去重後做加權分數（或 RRF）排序

**優點**
- 召回更全面，降低漏抓關鍵文件的機率

**代價**
- 系統變複雜，參數（權重、top_k）需要調整

---

## 2) rerank（重排序）

`rerank` 是在「已經拿到候選文件」之後，使用較強的 cross-encoder 或 LLM 評分器，針對「query + document」重新打分排序。

常見流程：

1. 先用 vector/keyword/hybrid 拿到 top_n（例如 20）
2. reranker 對這 20 篇重打分
3. 取重排後前 top_k（例如 5）給生成模型

**優點**
- 最終送進 LLM 的前幾篇品質通常更高

**代價**
- 推論成本與延遲增加

---

## 3) 最重要差異（記憶版）

- `hybrid = 召回策略`
- `rerank = 排序策略`

兩者不是互斥，最常見是組合使用：

1. 先做 hybrid（確保「找得到」）
2. 再做 rerank（確保「排得準」）

---

## 4) 在你目前 Phase N1 的落地建議

若只先做一種，建議優先順序如下：

1. 先做 `hybrid`（更快看到召回改善）
2. 再加 `rerank`（提升最終答案品質）

最小可行參數（可作為初始值）：

- `keyword_top_k = 10`
- `vector_top_k = 10`
- `hybrid_merge_top_n = 20`
- `rerank_top_n = 20`
- `final_top_k = 5`
- `hybrid_weight_vector = 0.6`
- `hybrid_weight_keyword = 0.4`

---

## 5) 一句話總結

`hybrid` 負責「多找對的」，`rerank` 負責「把最對的放前面」。


## 6) TODO_Phase3 說明

N1-P1 ~ N1-P3 屬於 hybrid（召回與混合排序）
N1-P4 ~ N1-P5 屬於 rerank（精排後再生成）

你可以把它記成一句話：先 hybrid 找全，再 rerank 排準。
