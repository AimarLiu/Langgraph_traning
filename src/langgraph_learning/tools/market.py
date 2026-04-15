"""
匯率／加密現貨價格工具（Frankfurter、Binance 公開 API）。

C2：白名單、HTTP 逾時、分類例外；錯誤以 JSON 字串回傳。

K2：I/O 以 **httpx** 實作；**coroutine** 使用 AsyncClient，在 `graph.ainvoke` /
`ToolNode` 非同步路徑下不阻塞 event loop。同步 **func** 保留給 `invoke`、
子圖內 `.invoke()` 等既有呼叫。
"""

from __future__ import annotations

import json
from typing import Any

# Feature 	  Requests	                    HTTPX
# I/O Model	  Synchronous only (blocking)	Both synchronous and asynchronous
import httpx
from langchain_core.tools import StructuredTool

# connect 5s、其餘 20s（對齊原 requests (5, 20) 語意；httpx 需 default 或四項齊全）
_REQUEST_TIMEOUT = httpx.Timeout(20.0, connect=5.0)

_ALLOWED_FRANKFURTER_QUOTE = frozenset({"THB", "JPY", "EUR", "GBP"})
_ALLOWED_BINANCE_SYMBOLS = frozenset({"ETHUSDT", "BTCUSDT"})


def _tool_error(message: str, **extra: Any) -> str:
    payload: dict[str, Any] = {"error": message}
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def _validate_frankfurt_quote(to_currency: str) -> tuple[str | None, str]:
    """回傳 (error_json_or_none, normalized_quote_upper)."""
    quote = to_currency.strip().upper()
    if quote not in _ALLOWED_FRANKFURTER_QUOTE:
        return (
            _tool_error(
                "不支援的目標幣別。",
                allowed=sorted(_ALLOWED_FRANKFURTER_QUOTE),
                received=to_currency,
            ),
            quote,
        )
    return None, quote


def _validate_binance_symbol(symbol: str) -> tuple[str | None, str]:
    sym = symbol.strip().upper()
    if sym not in _ALLOWED_BINANCE_SYMBOLS:
        return (
            _tool_error(
                "不支援的交易對。",
                allowed=sorted(_ALLOWED_BINANCE_SYMBOLS),
                received=symbol,
            ),
            sym,
        )
    return None, sym


def _usd_thb_sync(to_currency: str = "THB") -> str:
    err, quote = _validate_frankfurt_quote(to_currency)
    if err:
        return err

    url = "https://api.frankfurter.app/latest"
    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT, follow_redirects=True) as client:
            r = client.get(url, params={"from": "USD", "to": quote})
            r.raise_for_status()
            data = r.json()
        rates = data.get("rates") or {}
        if quote not in rates:
            return _tool_error(
                "API 回應缺少匯率欄位。", quote=quote, raw_keys=list(rates.keys())
            )
        rate = rates[quote]
        date = data.get("date", "unknown")
        return json.dumps(
            {
                f"usd_to_{quote.lower()}": rate,
                "quote": quote,
                "date": date,
                "note": "Frankfurter（參考用）",
            },
            ensure_ascii=False,
        )
    except httpx.TimeoutException:
        return _tool_error("Frankfurter 請求逾時，請稍後再試。")
    except httpx.HTTPStatusError as e:
        return _tool_error(
            "Frankfurter HTTP 錯誤。",
            status_code=e.response.status_code,
            detail=str(e),
        )
    except httpx.RequestException as e:
        return _tool_error("Frankfurter 網路請求失敗。", detail=str(e))
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return _tool_error("解析 Frankfurter 回應失敗。", detail=str(e))


async def _usd_thb_async(to_currency: str = "THB") -> str:
    err, quote = _validate_frankfurt_quote(to_currency)
    if err:
        return err

    url = "https://api.frankfurter.app/latest"
    try:
        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT, follow_redirects=True
        ) as client:
            r = await client.get(url, params={"from": "USD", "to": quote})
            r.raise_for_status()
            data = r.json()
        rates = data.get("rates") or {}
        if quote not in rates:
            return _tool_error(
                "API 回應缺少匯率欄位。", quote=quote, raw_keys=list(rates.keys())
            )
        rate = rates[quote]
        date = data.get("date", "unknown")
        return json.dumps(
            {
                f"usd_to_{quote.lower()}": rate,
                "quote": quote,
                "date": date,
                "note": "Frankfurter（參考用）",
            },
            ensure_ascii=False,
        )
    except httpx.TimeoutException:
        return _tool_error("Frankfurter 請求逾時，請稍後再試。")
    except httpx.HTTPStatusError as e:
        return _tool_error(
            "Frankfurter HTTP 錯誤。",
            status_code=e.response.status_code,
            detail=str(e),
        )
    except httpx.RequestException as e:
        return _tool_error("Frankfurter 網路請求失敗。", detail=str(e))
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return _tool_error("解析 Frankfurter 回應失敗。", detail=str(e))


def _eth_binance_sync(symbol: str = "ETHUSDT") -> str:
    err, sym = _validate_binance_symbol(symbol)
    if err:
        return err

    url = "https://api.binance.com/api/v3/ticker/price"
    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT, follow_redirects=True) as client:
            r = client.get(url, params={"symbol": sym})
            r.raise_for_status()
            data = r.json()
        return json.dumps(
            {
                "symbol": data.get("symbol", sym),
                "price_usdt": data["price"],
                "source": "Binance /api/v3/ticker/price（參考用）",
            },
            ensure_ascii=False,
        )
    except httpx.TimeoutException:
        return _tool_error("Binance 請求逾時，請稍後再試。")
    except httpx.HTTPStatusError as e:
        return _tool_error(
            "Binance HTTP 錯誤。",
            status_code=e.response.status_code,
            detail=str(e),
        )
    except httpx.RequestException as e:
        return _tool_error("Binance 網路請求失敗。", detail=str(e))
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return _tool_error("解析 Binance 回應失敗。", detail=str(e))


async def _eth_binance_async(symbol: str = "ETHUSDT") -> str:
    err, sym = _validate_binance_symbol(symbol)
    if err:
        return err

    url = "https://api.binance.com/api/v3/ticker/price"
    try:
        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT, follow_redirects=True
        ) as client:
            r = await client.get(url, params={"symbol": sym})
            r.raise_for_status()
            data = r.json()
        return json.dumps(
            {
                "symbol": data.get("symbol", sym),
                "price_usdt": data["price"],
                "source": "Binance /api/v3/ticker/price（參考用）",
            },
            ensure_ascii=False,
        )
    except httpx.TimeoutException:
        return _tool_error("Binance 請求逾時，請稍後再試。")
    except httpx.HTTPStatusError as e:
        return _tool_error(
            "Binance HTTP 錯誤。",
            status_code=e.response.status_code,
            detail=str(e),
        )
    except httpx.RequestException as e:
        return _tool_error("Binance 網路請求失敗。", detail=str(e))
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return _tool_error("解析 Binance 回應失敗。", detail=str(e))


_USD_THB_DESC = (
    "查詢目前 1 美元 (USD) 可兌換多少目標貨幣。to_currency 預設 THB；"
    "僅允許白名單幣別。資料來自 Frankfurter 公開 API。"
)
_ETH_DESC = (
    "查詢 Binance 現貨交易對最新成交價。symbol 預設 ETHUSDT；"
    "僅允許白名單（練習用）。資料來自 Binance 公開 REST API。"
)

get_usd_thb_exchange_rate = StructuredTool.from_function(
    func=_usd_thb_sync,
    coroutine=_usd_thb_async,
    name="get_usd_thb_exchange_rate",
    description=_USD_THB_DESC,
)

get_eth_usdt_price_binance = StructuredTool.from_function(
    func=_eth_binance_sync,
    coroutine=_eth_binance_async,
    name="get_eth_usdt_price_binance",
    description=_ETH_DESC,
)
