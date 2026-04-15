"""Lilian Weng Chroma 索引：路徑、embedding 建立（J1/J2 共用）。"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

DEFAULT_COLLECTION = "lilian_weng_posts"
DEFAULT_EMBED_CANDIDATES = (
    "models/gemini-embedding-001",
    "models/text-embedding-004",
)


def project_root() -> Path:
    """套件位於 `src/langgraph_learning/tools/`，往上三層為專案根目錄。"""
    return Path(__file__).resolve().parents[3]


def default_chroma_persist_path() -> Path:
    return project_root() / "data" / "chroma" / "lilianweng"


def resolve_chroma_persist_dir() -> Path:
    raw = os.getenv("LILIAN_CHROMA_DIR", "").strip()
    return Path(raw) if raw else default_chroma_persist_path()


def resolve_collection_name() -> str:
    return os.getenv("LILIAN_CHROMA_COLLECTION", DEFAULT_COLLECTION).strip() or (
        DEFAULT_COLLECTION
    )


def create_embeddings(api_key: str) -> tuple[GoogleGenerativeAIEmbeddings, str]:
    """依環境與 API 相容性挑選可用 embedding model。"""
    preferred = os.getenv("J1_EMBED_MODEL", "").strip()
    candidates = [preferred] if preferred else []
    candidates.extend([m for m in DEFAULT_EMBED_CANDIDATES if m not in candidates])

    last_error: Exception | None = None
    for model in candidates:
        emb = GoogleGenerativeAIEmbeddings(
            model=model,
            google_api_key=api_key,
        )
        try:
            emb.embed_query("embedding health check")
            return emb, model
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(f"找不到可用 embedding model。最後錯誤: {last_error}")


def open_lilian_chroma_vectorstore() -> Chroma:
    """開啟已存在的 Chroma（與 J1 建索引時相同 collection / persist_directory）。"""
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 GOOGLE_API_KEY，無法查詢向量庫。")

    persist = resolve_chroma_persist_dir()
    collection = resolve_collection_name()
    embeddings, _ = create_embeddings(api_key=api_key)
    return Chroma(
        collection_name=collection,
        embedding_function=embeddings,
        persist_directory=str(persist),
    )
