"""將專案根目錄下的 `src` 加入 sys.path，使 `langgraph_learning` 可被 import。

階段 D：練習腳本在根目錄執行時需先 `import path_setup` 再 `path_setup.add_src_to_path()`。
亦可改用 `pip install -e .`（見 pyproject.toml）省略此步驟。
"""

from __future__ import annotations

import sys
from pathlib import Path


def add_src_to_path() -> None:
    root = Path(__file__).resolve().parent
    src = root / "src"
    s = str(src)
    if s not in sys.path:
        sys.path.insert(0, s)
