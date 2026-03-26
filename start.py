#!/usr/bin/env python3
"""PC Builder Tool - 起動スクリプト"""
import subprocess
import sys
import os
import webbrowser
import time
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND = ROOT / "backend"


def install_deps():
    req = ROOT / "requirements.txt"
    print("依存パッケージをインストール中...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req), "-q"])
    print("インストール完了")


def main():
    print("=" * 50)
    print("  PC Builder Tool v1.0")
    print("=" * 50)

    # install if needed
    try:
        import fastapi, uvicorn, openpyxl, reportlab, bs4
    except ImportError:
        install_deps()

    # open browser after short delay
    def open_browser():
        time.sleep(2)
        webbrowser.open("http://127.0.0.1:8000")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    print("サーバーを起動中... http://127.0.0.1:8000")
    print("終了するには Ctrl+C を押してください")
    print()

    os.chdir(str(BACKEND))
    subprocess.run([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"])


if __name__ == "__main__":
    main()
