"""J1 helper: crawl Lilian Weng posts and build a Chroma index.

Usage:
    py -3.11 src/langgraph_learning/tools/j1_build_lilian_chroma.py --limit 4
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

# 允許直接執行本檔時找到 `langgraph_learning`（等同 path_setup）
_ROOT = Path(__file__).resolve().parents[3]
_SRC = _ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langgraph_learning.tools.lilian_chroma_store import (
    create_embeddings,
    default_chroma_persist_path,
)

SITE_URL = "https://lilianweng.github.io/"
DEFAULT_COLLECTION = "lilian_weng_posts"
DEFAULT_MD_DIR = "data/lilianweng_markdown"
DEFAULT_CHROMA_DIR = default_chroma_persist_path()


def _slug_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path:
        return "home"
    return path.split("/")[-1] or "post"


def _fetch_html(url: str, timeout_s: int) -> str:
    resp = requests.get(url, timeout=timeout_s)
    resp.raise_for_status()
    return resp.text


def discover_post_urls(site_url: str, limit: int, timeout_s: int) -> list[str]:
    """Get latest post URLs from Lil'Log home page."""
    html = _fetch_html(site_url, timeout_s)
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        if "/posts/" not in href:
            continue
        if href.startswith("#"):
            continue
        url = urljoin(site_url, href)
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
        if len(urls) >= limit:
            break
    return urls


def _article_text_blocks(soup: BeautifulSoup) -> list[str]:
    article = soup.find("article") or soup.find("main") or soup
    blocks: list[str] = []
    for node in article.find_all(
        ["h1", "h2", "h3", "h4", "p", "li", "pre", "code", "blockquote"]
    ):
        text = node.get_text(" ", strip=True)
        if not text:
            continue
        blocks.append(text)
    return blocks


def fetch_post_as_document(url: str, timeout_s: int) -> Document:
    """Fetch one post and convert to a LangChain Document."""
    html = _fetch_html(url, timeout_s)
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    h1 = soup.find("h1")
    if h1 is not None:
        title = h1.get_text(" ", strip=True)
    if not title:
        t = soup.find("title")
        title = t.get_text(" ", strip=True) if t else "Untitled"

    full_text = soup.get_text(" ", strip=True)
    date_match = re.search(r"Date:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", full_text)
    post_date = date_match.group(1) if date_match else "unknown"

    blocks = _article_text_blocks(soup)
    body = "\n\n".join(blocks)
    if not body:
        body = full_text

    doc = Document(
        page_content=body,
        metadata={
            "source": url,
            "title": title,
            "date": post_date,
            "slug": _slug_from_url(url),
        },
    )
    return doc


def save_markdown_snapshot(doc: Document, output_dir: Path) -> Path:
    """Save a markdown snapshot for inspection."""
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = doc.metadata["slug"]
    path = output_dir / f"{slug}.md"
    content = (
        f"# {doc.metadata['title']}\n\n"
        f"- source: {doc.metadata['source']}\n"
        f"- date: {doc.metadata['date']}\n\n"
        f"{doc.page_content}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


def build_chroma_index(
    docs: list[Document],
    persist_dir: Path,
    collection_name: str,
    chunk_size: int,
    chunk_overlap: int,
    reset: bool,
) -> tuple[int, int]:
    """Chunk docs and persist them to Chroma."""
    if reset and persist_dir.exists():
        shutil.rmtree(persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit("缺少 GOOGLE_API_KEY，無法建立 embedding。")

    embeddings, embed_model = create_embeddings(api_key=api_key)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = splitter.split_documents(docs)

    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
    )
    vectorstore.add_documents(chunks)

    return len(docs), len(chunks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl Lilian Weng posts and index to Chroma."
    )
    parser.add_argument("--limit", type=int, default=4, help="How many posts to fetch.")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout seconds.")
    parser.add_argument(
        "--markdown-dir",
        type=Path,
        default=Path(DEFAULT_MD_DIR),
        help="Where fetched markdown snapshots are saved.",
    )
    parser.add_argument(
        "--persist-dir",
        type=Path,
        default=DEFAULT_CHROMA_DIR,
        help="Chroma persist directory.",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=DEFAULT_COLLECTION,
        help="Chroma collection name.",
    )
    parser.add_argument("--chunk-size", type=int, default=2400)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not remove old Chroma data before indexing.",
    )
    parser.add_argument(
        "--probe-query",
        type=str,
        default="What is reward hacking in RL?",
        help="Run a quick similarity search query after indexing.",
    )
    parser.add_argument(
        "--max-chars-per-doc",
        type=int,
        default=18000,
        help=(
            "Trim each fetched post body to reduce embedding quota usage "
            "(free tier safety valve)."
        ),
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    reset = not args.keep_existing

    print("=== J1 Chroma Build: Lilian Weng posts ===")
    print(f"site: {SITE_URL}")
    print(f"fetch limit: {args.limit}")
    print(f"persist dir: {args.persist_dir}")
    print(f"collection: {args.collection}")
    print(f"embed model env: {os.getenv('J1_EMBED_MODEL', '(auto fallback)')}")
    print()

    urls = discover_post_urls(SITE_URL, limit=args.limit, timeout_s=args.timeout)
    if not urls:
        raise RuntimeError("找不到文章 URL，請確認站台結構或調整 selector。")

    print("Discovered URLs:")
    for i, url in enumerate(urls, start=1):
        print(f"{i}. {url}")
    print()

    docs: list[Document] = []
    for url in urls:
        doc = fetch_post_as_document(url, timeout_s=args.timeout)
        if len(doc.page_content) > args.max_chars_per_doc:
            doc.page_content = doc.page_content[: args.max_chars_per_doc]
        md_path = save_markdown_snapshot(doc, args.markdown_dir)
        docs.append(doc)
        print(f"[saved] {md_path} (chars={len(doc.page_content)})")

    doc_count, chunk_count = build_chroma_index(
        docs=docs,
        persist_dir=args.persist_dir,
        collection_name=args.collection,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        reset=reset,
    )

    print()
    print("Index build complete.")
    print(f"- documents: {doc_count}")
    print(f"- chunks: {chunk_count}")

    # quick probe query so user can verify index content.
    api_key = os.getenv("GOOGLE_API_KEY")
    embeddings, used_model = create_embeddings(api_key=api_key)
    print(f"- embedding model: {used_model}")
    vectorstore = Chroma(
        collection_name=args.collection,
        embedding_function=embeddings,
        persist_directory=str(args.persist_dir),
    )
    hits = vectorstore.similarity_search(args.probe_query, k=3)
    print()
    print(f"Probe query: {args.probe_query!r}")
    for idx, hit in enumerate(hits, start=1):
        meta = hit.metadata
        preview = hit.page_content[:140].replace("\n", " ")
        print(f"{idx}. title={meta.get('title')} slug={meta.get('slug')}")
        print(f"   preview={preview}...")


if __name__ == "__main__":
    main()
