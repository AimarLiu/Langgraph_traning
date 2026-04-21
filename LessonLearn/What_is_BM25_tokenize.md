# BM25 與 tokenize 是什麼？跟 chunk（split_documents）差在哪？

這篇筆記整理你在 N1（Hybrid RAG）看到的幾個常見疑問：

- 為什麼要用 **BM25**（keyword/sparse retrieval）？
- **tokenize** 在 BM25 裡扮演什麼角色？拿「明文」來 tokenize 合理嗎？
- tokenize 跟 `RecursiveCharacterTextSplitter.split_documents()` 的 **chunk 切分**有什麼不同？
- Hybrid 用 **min-max normalize + 加權排序**真的「精確」嗎？

---

## 1) BM25 在做什麼？（一句話）

**BM25 是一種關鍵字檢索的打分法**：它會根據「查詢詞在文件中出現的次數」與「該詞在整個語料的稀有程度」，計算每個文件對 query 的相關性分數，最後取分數高的前 `top_k`。

你可以把它理解成：**「詞越對、越稀有、越集中出現在文件中」→ 分數越高**。

---

## 2) tokenize 在 BM25 裡的角色

BM25 不是看字串整段相等，而是看「詞」：

1. 把 query 變成一串 tokens（詞）
2. 把每個文件也變成 tokens（詞）
3. 依 token 統計：
   - **TF（term frequency）**：某 token 在文件中出現幾次
   - **DF（document frequency）**：某 token 在多少份文件出現過
   - **IDF（inverse document frequency）**：token 越稀有（DF 越小），權重越大
4. 依 BM25 公式把每個 token 的貢獻加總，得到文件分數

所以 tokenize 的本質是：**決定什麼叫「一個詞」**。  
分詞好不好，會直接影響 BM25 的效果（尤其是中文）。

---

## 3) 為什麼說 `documents/metadatas` 是明文？拿明文 tokenize 合理嗎？

在你目前的實作中（Chroma + LangChain Document）：

- `documents` 存的是 chunk 的 **原始文字內容**（page_content）
- `metadatas` 存的是 **原始 metadata**（source/title/slug…）

BM25 是「字詞統計」模型，它本來就需要文字本體才能做 TF/IDF；  
因此「拿明文去 tokenize」是**正常且必要**的流程，不是額外洩漏（因為你本來就把明文存進向量庫當作檢索內容）。

---

## 4) tokenize vs chunk（split_documents）差在哪？

這兩件事常被混在一起，但它們處在不同層級：

### A) chunk（`split_documents`）是在「切檢索單位」

它決定向量庫裡的基本單位是什麼：

- 切大：每個 chunk 資訊多，但可能雜訊也多、引用不精準
- 切小：更精準，但容易上下文不足
- `chunk_overlap`：避免關鍵句被切斷

在你的專案中，chunk 發生在 **建索引（J1）** 階段：先把文章切成 chunks，再把 chunks 寫進 Chroma。

---

### B) tokenize（BM25）是在「把文字轉成可統計的詞」

tokenize 不會改變 chunk 的邊界；它是在每個 chunk 內把文字拆成 tokens，讓 BM25 能算 TF/IDF：

- chunk 決定「要檢索哪些單位」
- tokenize 決定「單位內哪些字詞算同一個 token」

在你目前的 BM25 tokenizer（簡化版）裡，token 規則是：

- 只取 `A-Za-z0-9`（英文與數字）
- 全部轉小寫

這個規則對英文文章（像 Lilian Weng blog）很夠用；  
但對中文語料通常不夠（因為中文需要分詞或 n-gram 才能有合理的 token）。

---

## 5) Hybrid（min-max normalize + 加權排序）為什麼能用？真的精確嗎？

先講結論：**它常常「更好用」，但不是「保證精確」**。

原因是 hybrid 在解兩個工程問題：

- **降低漏召回**：keyword 擅長精準詞、vector 擅長語意相近；兩者合併後，漏抓關鍵 chunk 的機率變低。
- **把兩種分數放到同一尺度比較**：BM25 分數與向量相似度/距離通常不在同一量綱，所以需要 normalize。

你現在用的流程可以拆成三步理解：

1. **兩路召回**：keyword 取 `keyword_top_k`；vector 取 `vector_top_k`
2. **去重合併**：把同一 chunk（或等價 chunk）視為同一筆
3. **融合排序**：兩路分數各自 min-max normalize 到 0~1，再用
   \[
   hybrid\_score = w_v \cdot vector\_norm + w_k \cdot keyword\_norm
   \]
   產生最終排序

### 為什麼說不保證精確？

- **normalize 是啟發式**：min-max 會受到 outlier 影響；不同 query 的分數分佈也會變。
- **權重是經驗值**：`0.6/0.4` 是合理起點，但不是理論保證最優。
- **召回 vs 精排的本質差異**：hybrid 主要還在「找得到/找更全」，不是「最準確把前 5 篇排對」；真正要更準通常靠 rerank（N1-P4）。

因此你要用「驗收指標」來看它是否“更精確”，例如：

- golden set 命中率（ground truth chunk 是否更常出現在 top_n）
- 最終答案品質（可用規則/LLM judge/人工 review）
- 延遲與成本（hybrid 多了 keyword 計分與 merge）

---

## 6) 你目前專案中的對照位置（方便回頭看）

- **切 chunk（索引階段）**：`src/langgraph_learning/tools/j1_build_lilian_chroma.py`
  - `RecursiveCharacterTextSplitter(...).split_documents(docs)`
- **BM25 tokenize / 建索引（查詢時）**：`src/langgraph_learning/tools/bm25_keyword.py`
  - `tokenize_for_bm25()`：token 規則
  - `build_bm25_index_from_chroma()`：從 Chroma `vs.get(include=["documents","metadatas"])` 建 BM25 統計
  - `bm25_top_k()` / `keyword_search_chroma_collection()`：對 query 計分並取 top_k
- **Hybrid（N1-P1~P3：合併 + normalize + 加權）**：`src/langgraph_learning/tools/hybrid_lilian_chroma.py`
  - `hybrid_search_lilian_chroma()`
- **LangChain `@tool` 包裝（對外工具介面）**：`src/langgraph_learning/tools/rag_lilian.py`
  - `search_lilian_weng_knowledge(...)`
- **Hybrid smoke（直接看結果）**：`practice_16_rag_advanced_smoke.py`


## 7) similarity_search 跟 similarity_search_with_score 差在回傳內容：

- similarity_search(query, k=...)

   - 回傳：list[Document]
   - 只有文件（chunk）本體與 metadata，沒有分數/距離。

- similarity_search_with_score(query, k=...)

   - 回傳：list[tuple[Document, score]]
   - 多了第二個值 score（在 Chroma 這類向量庫常見是距離 distance：越小越相近；但不同向量庫/設定可能是相似度，方向不一定一樣）。

- 在你目前 hybrid 實作裡，我用 similarity_search_with_score 是因為 P2/P3 需要保留 vector 的原始分數，才能做 normalize + 加權排序；如果只用 similarity_search 就拿不到這個數字。

## 8) Rerank

- 在你現在 N1 的設計裡，rerank 就是把 hybrid（N1-P1~P3）產出的候選（例如 top_n=20）再「精排」一次，最後才取 final_top_k（例如 5）給 LLM。

- 更精準一點講：
   - rerank 的輸入不是「一定要 hybrid」，而是「任何召回方式先拿到一批候選文件」都可以 rerank（vector-only、keyword-only、hybrid 都行）。
   - 但在你的 TODO_phase3.md pipeline 描述裡，順序就是：hybrid 先擴召回/混合排序 → rerank 再把最相關的排到最前面。


## 9) keyword v.s. vector

- vector 檢索需要把 q 轉成向量；BM25 keyword 不需要把 q 轉成向量，而是把 q 做 tokenize 後丟進 `bm25_top_k()`（BM25Okapi 風格公式）去算分。

- 但有一個小修正很重要：

- similarity_search / similarity_search_with_score 通常不會呼叫「聊天 LLM」（不是 ChatModel 那種生成文字）。它們會用到的是 embedding 模型（例如你專案裡的 GoogleGenerativeAIEmbeddings），把 q encode 成向量，再去向量庫做相似度/距離檢索。
- embedding 跟 LLM 常共用同一個雲端供應商/金鑰，但不是同一個「LLM 推理」步驟。

- keyword（BM25）這邊：
不需要 query embedding。
你的 _bm25_top_k 會先把 query tokenize，再用 TF/IDF/BM25 公式對每個 chunk 打分（這些都在程式裡完成）。

- 補一句實務上的差異：vector 會多一次 embedding API 成本/延遲；BM25 主要是 CPU 計算成本（你這版還會先掃 collection 建 index，規模大時會更明顯）。