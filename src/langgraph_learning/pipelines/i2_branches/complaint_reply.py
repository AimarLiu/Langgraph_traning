"""申訴分支：同理與流程說明，與閒聊／查價檔案分離。"""

from __future__ import annotations


def build_complaint_response(user_message: str) -> str:
    """申訴／客訴專用回覆骨架（調整語氣請只改本檔）。"""
    msg = user_message.strip() or "（未提供細節）"
    return (
        "【申訴分支】\n"
        f"已記錄您反映的重點：{msg}\n"
        "我們會請專人於 1～3 個工作天內與您聯繫；"
        "若需訂單編號或聯絡方式，請稍後補充在對話中。"
    )
