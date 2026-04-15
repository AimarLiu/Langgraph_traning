"""最小 Hello World，用於確認環境可執行並顯示實際 Python 版本。"""

import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


def main() -> None:
    print("Hello, World!")
    v = sys.version_info
    print(f"執行中 Python：{v.major}.{v.minor}.{v.micro}")


if __name__ == "__main__":
    main()
