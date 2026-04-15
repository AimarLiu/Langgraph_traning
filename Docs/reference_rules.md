# Cursor 專案 Rules 參考資源（Python + LangChain / LangGraph）

本文件整理學習 **LangGraph**、**LangChain**（Python）時，撰寫 Cursor 專案規則可參考的 **GitHub 倉庫與文章**。先把「慣例與風格」寫進 rules，有助 AI 在專案裡維持一致寫法。

---

## 官方／半官方（風格與慣例）

| 用途 | 連結 |
|------|------|
| LangChain 官方 **docs 倉庫**裡的 `.cursorrules`（偏**文件寫作**標準，但可看團隊怎麼寫規則） | [langchain-ai/docs — `.cursorrules`](https://github.com/langchain-ai/docs/blob/main/.cursorrules) |
| **LangGraph** 原始碼與範例 | [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) |
| **LangChain** Python 核心 | [langchain-ai/langchain](https://github.com/langchain-ai/langchain) |

學習程式時，規則檔多半還是要自己從官方文件與範例「抽」成專案規則；上面 docs 的 `.cursorrules` 主要是文件維護取向。

---

## 社群：現成 Cursor rules 範本（可複製再改）

| 說明 | 連結 |
|------|------|
| 多框架的 rules 集合（常含 AI/LangChain 相關條目） | [survivorforge/cursor-rules](https://github.com/survivorforge/cursor-rules) |
| AI／LangChain／RAG 等方向的 rules 範本 | [pr0mila/Cursor-Rules-for-AI-Engineers](https://github.com/pr0mila/Cursor-Rules-for-AI-Engineers) |

這類 repo 的內容品質不一，建議當「靈感 + 草稿」，再對照你使用的 **LangChain / LangGraph 版本** 微調。

---

## 文章／索引站（非 GitHub，但好搜）

- [cursorrules.org — LangChain 相關文章](https://cursorrules.org/article/langchain-cursor-mdc-file)：說明如何把 LangChain 慣例寫進 rules / MDC。

---

## Cursor 建議的 rules 寫法（與「寫 rules」直接相關）

除了專案根目錄的 `.cursorrules`，較新的做法是使用 **`.cursor/rules/*.mdc`**：

- 使用 **YAML frontmatter**，可設定 `description`、`globs`、`alwaysApply`。
- 將「全專案通用」與「僅某類檔案」（例如 `**/graphs/**/*.py`）**拆成多條 rule**，較易維護。

實務建議（對齊 Cursor 官方 create-rule 指引）：

- **一個主題一條 rule**，內容盡量精簡（例如單一規則不宜過長）。
- 需要時用 **`globs`** 限定適用檔案，避免不相關檔案也套用同一套規則。

---

*本文件由專案初始化時依先前對話中整理的「Cursor rules 參考來源」寫入；連結若失效請至各倉庫主分支重新尋找對應檔案。*
