"""One small GGUF model for offline use, managed without Ollama.

The model file is downloaded online from Hugging Face after approval and served
locally by llama-cpp-python's OpenAI-compatible server. No model is bundled with
the installer, and nothing is downloaded silently.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import httpx

LOCAL_MODEL_ID = "qwen2.5-coder-3b-instruct-q4"
LOCAL_MODEL_PORT = 11435
LOCAL_MODEL_BASE_URL = f"http://127.0.0.1:{LOCAL_MODEL_PORT}/v1"
LOCAL_MODEL_FILE = "qwen2.5-coder-3b-instruct-q4_k_m.gguf"
LOCAL_MODEL_URL = (
    "https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/"
    + LOCAL_MODEL_FILE
    + "?download=true"
)


class LocalModelError(RuntimeError):
    pass


class LocalModelRuntime:
    def __init__(self, home: Path):
        self.home = Path(home)
        self.models_dir = self.home / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.home / "local_model.log"
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()

    @property
    def model_path(self) -> Path:
        return self.models_dir / LOCAL_MODEL_FILE

    def is_downloaded(self) -> bool:
        try:
            return self.model_path.is_file() and self.model_path.stat().st_size > 100_000_000
        except OSError:
            return False

    def runtime_available(self) -> bool:
        return importlib.util.find_spec("llama_cpp") is not None

    def _running(self) -> bool:
        try:
            response = httpx.get(LOCAL_MODEL_BASE_URL + "/models", timeout=2.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def status(self) -> dict[str, Any]:
        size = 0
        if self.model_path.is_file():
            try:
                size = self.model_path.stat().st_size
            except OSError:
                size = 0
        return {
            "id": LOCAL_MODEL_ID,
            "base_url": LOCAL_MODEL_BASE_URL,
            "downloaded": self.is_downloaded(),
            "runtime_available": self.runtime_available(),
            "running": self._running(),
            "size_gb": round(size / (1024 ** 3), 2) if size else 0,
            "download_gb": 1.96,
            "ram_gb": 4,
            "file": str(self.model_path),
            "note": "Qwen2.5 Coder 3B Q4. Runs offline with llama.cpp; no Ollama needed.",
        }

    def _log_tail(self) -> str:
        try:
            text = self.log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return text[-2500:]

    def ensure_running(self) -> dict[str, Any]:
        with self._lock:
            if self._running():
                return self.status()
            if not self.is_downloaded():
                raise LocalModelError(
                    "The offline model is not downloaded yet. Open Settings > Model Hub and approve the "
                    "offline model download."
                )
            if not self.runtime_available():
                raise LocalModelError(
                    "The offline llama.cpp runtime is not installed. Run the Deep Code setup again to install "
                    "the local runtime, or choose an online model."
                )
            threads = max(2, min(8, os.cpu_count() or 4))
            command = [
                sys.executable,
                "-m",
                "llama_cpp.server",
                "--model",
                str(self.model_path),
                "--host",
                "127.0.0.1",
                "--port",
                str(LOCAL_MODEL_PORT),
                "--n_ctx",
                "4096",
                "--n_threads",
                str(threads),
                "--chat_format",
                "chatml",
            ]
            kwargs: dict[str, Any] = {}
            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            log = self.log_path.open("a", encoding="utf-8")
            log.write(f"\n--- starting offline model at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            log.flush()
            try:
                self._process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    cwd=str(self.home),
                    **kwargs,
                )
            except OSError as exc:
                log.close()
                raise LocalModelError(f"Could not start the offline model runtime: {exc}") from exc
            deadline = time.monotonic() + 120.0
            try:
                while time.monotonic() < deadline:
                    if self._running():
                        return self.status()
                    if self._process.poll() is not None:
                        detail = self._log_tail()
                        raise LocalModelError(
                            "The offline model runtime stopped while starting. "
                            + (detail or "Check the local_model.log file for details.")
                        )
                    time.sleep(1.0)
            finally:
                log.close()
            raise LocalModelError(
                "The offline model did not become ready within two minutes. "
                "On a 4 GB machine, close other apps and retry."
            )

    def stop(self) -> None:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            self._process = None
