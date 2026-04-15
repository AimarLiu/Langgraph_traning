"""第三課表 L1 啟動入口：API 實作已集中於 `src/api/`。"""

from __future__ import annotations

import path_setup

path_setup.add_src_to_path()

from api.app import app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
