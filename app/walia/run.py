from __future__ import annotations

import os
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from .main import app

HOST = "127.0.0.1"
PORT = int(os.environ.get("WALIACODE_PORT", "8765"))
URL = f"http://{HOST}:{PORT}"


def _open_browser_when_ready() -> None:
    for _ in range(120):
        try:
            with urllib.request.urlopen(f"{URL}/health", timeout=1):
                break
        except Exception:
            time.sleep(0.5)
    else:
        return
    try:
        webbrowser.open(URL)
    except Exception:
        pass


def main() -> None:
    if os.environ.get("DEEPCODE_NO_BROWSER") != "1":
        threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()

