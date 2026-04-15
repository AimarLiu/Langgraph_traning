"""閒聊分支：僅負責閒聊語氣與結構，與查價／申訴模組無關。"""

from __future__ import annotations


def build_chat_response(user_message: str) -> str:
    """依專用語氣組裝閒聊回覆（可只改本檔而不動其他分支）。"""
    msg = user_message.strip() or "（空訊息）"
    return (
        "【閒聊分支】\n"
        f"收到：{msg}\n"
        "這裡用輕鬆口吻陪聊即可；若之後要接 LLM，只替換本函式內容即可。"
    )
