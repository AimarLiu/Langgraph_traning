"""LangChain 工具定義。"""

from langgraph_learning.tools.market import (
    get_eth_usdt_price_binance,
    get_usd_thb_exchange_rate,
)
from langgraph_learning.tools.rag_lilian import (
    LILIAN_RAG_SYSTEM_PROMPT,
    search_lilian_weng_knowledge,
)

DEFAULT_MARKET_TOOLS = [get_usd_thb_exchange_rate, get_eth_usdt_price_binance]
DEFAULT_RAG_TOOLS = [search_lilian_weng_knowledge]

__all__ = [
    "DEFAULT_MARKET_TOOLS",
    "DEFAULT_RAG_TOOLS",
    "LILIAN_RAG_SYSTEM_PROMPT",
    "get_eth_usdt_price_binance",
    "get_usd_thb_exchange_rate",
    "search_lilian_weng_knowledge",
]
