from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path
from typing import Any

import httpx


class DownloadManager:
    """Downloads a model file over HTTPS and reports byte-level progress."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def start(self, model: str, url: str, destination: Path) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        job = {
            "id": job_id,
            "model": model,
            "url": url,
            "status": "running",
            "progress": 0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "started_at": time.time(),
            "finished_at": None,
            "error": "",
        }
        with self._lock:
            self._jobs[job_id] = job
        thread = threading.Thread(target=self._run, args=(job_id, url, Path(destination)), daemon=True)
        thread.start()
        return dict(job)

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.update(changes)

    def _run(self, job_id: str, url: str, destination: Path) -> None:
        part = destination.with_suffix(destination.suffix + ".part")
        destination.parent.mkdir(parents=True, exist_ok=True)
        downloaded = 0
        try:
            with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(120.0)) as client:
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    total = int(response.headers.get("content-length") or 0)
                    self._update(job_id, total_bytes=total)
                    with part.open("wb") as handle:
                        for chunk in response.iter_bytes(1024 * 256):
                            if chunk:
                                handle.write(chunk)
                                downloaded += len(chunk)
                                progress = int((downloaded / total) * 100) if total else 0
                                self._update(
                                    job_id,
                                    downloaded_bytes=downloaded,
                                    progress=max(0, min(100, progress)),
                                )
            if downloaded < 100_000_000:
                raise OSError("The downloaded file is too small to be a usable GGUF model.")
            part.replace(destination)
            self._update(
                job_id,
                status="done",
                progress=100,
                downloaded_bytes=downloaded,
                finished_at=time.time(),
            )
        except (httpx.HTTPError, OSError, ValueError) as exc:
            try:
                part.unlink(missing_ok=True)
            except OSError:
                pass
            self._update(
                job_id,
                status="error",
                error=str(exc)[:1000],
                finished_at=time.time(),
            )

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(job) for job in self._jobs.values()]

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None
