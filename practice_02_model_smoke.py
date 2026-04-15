import os
from typing import Any

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage

load_dotenv()

_api_key = os.getenv("GOOGLE_API_KEY")
if not _api_key:
    raise SystemExit("缺少環境變數 GOOGLE_API_KEY（請在 .env 設定）")


def _text_from_ai_message(msg: AIMessage) -> str:
    """Gemini 新版回傳的 content 可能是 str，也可能是含 type/text 的區塊列表。"""
    c: Any = msg.content
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts: list[str] = []
        for block in c:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts) if parts else str(c)
    return str(c)


llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    api_key=_api_key,
)
response = llm.invoke("告訴我目前台北市南港區是否下雨?")
assert isinstance(response, AIMessage)
print(_text_from_ai_message(response))