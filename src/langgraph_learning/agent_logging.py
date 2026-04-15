"""
本專案用 Python logging 的集中設定。

開關：環境變數 AGENT_LOGGING（見 Docs/logging_setup.md）。
關閉時不註冊 handler，並將 logger 設為不輸出 INFO。
"""

from __future__ import annotations

import logging
import os
import sys

_LOGGER_ROOT = "langgraph_learning"


def is_agent_logging_enabled() -> bool:
    """若為 true / 1 / yes / on（不分大小寫）則啟用。"""
    v = os.getenv("AGENT_LOGGING", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def configure_agent_logging() -> None:
    """應在 load_dotenv() 之後呼叫一次。重複呼叫會重置同一個 root logger 的 handler。"""
    log = logging.getLogger(_LOGGER_ROOT)
    log.handlers.clear()
    log.propagate = False

    if not is_agent_logging_enabled():
        log.setLevel(logging.CRITICAL + 1)
        return

    level_name = os.getenv("AGENT_LOGGING_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    log.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    log.addHandler(handler)


def get_agent_logger(name: str) -> logging.Logger:
    """子模組請用簡短名稱，皆掛在 langgraph_learning 下。"""
    if name.startswith(_LOGGER_ROOT):
        return logging.getLogger(name)
    return logging.getLogger(f"{_LOGGER_ROOT}.{name}")
