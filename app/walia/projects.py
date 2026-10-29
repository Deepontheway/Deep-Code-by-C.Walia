from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any


class ProjectError(ValueError):
    pass


class ProjectStore:
    def __init__(self, home: Path) -> None:
        self.path = Path(home) / "projects.json"
        self._lock = threading.Lock()

    def _read(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return []
        items = data.get("projects") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict) and item.get("path")]

    def _write(self, items: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({"projects": items}, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read()

    def add(self, path: str, name: str = "") -> dict[str, Any]:
        resolved = Path(path).expanduser().resolve(strict=True)
        if not resolved.is_dir():
            raise ProjectError("The selected project path is not a folder.")
        key = os.path.normcase(str(resolved))
        with self._lock:
            items = self._read()
            for item in items:
                if os.path.normcase(str(Path(item["path"]))) == key:
                    if name.strip():
                        item["name"] = name.strip()[:120]
                        self._write(items)
                    return item
            project = {
                "id": uuid.uuid4().hex,
                "name": (name.strip() or resolved.name or str(resolved))[:120],
                "path": str(resolved),
                "added_at": time.time(),
            }
            items.append(project)
            self._write(items)
            return project

    def remove(self, project_id: str) -> dict[str, Any] | None:
        with self._lock:
            items = self._read()
            removed = next((item for item in items if item.get("id") == project_id), None)
            if removed is None:
                return None
            self._write([item for item in items if item.get("id") != project_id])
            return removed

    def get(self, project_id: str) -> dict[str, Any] | None:
        with self._lock:
            return next((item for item in self._read() if item.get("id") == project_id), None)


def browse_for_folder() -> str | None:
    handle, temp_name = tempfile.mkstemp(prefix="walia-folder-", suffix=".txt")
    os.close(handle)
    temp_path = Path(temp_name)
    quoted = str(temp_path).replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog;"
        "$dialog.Description = 'Choose a project folder for Deep Code';"
        "$dialog.ShowNewFolderButton = $true;"
        "$dialog.SelectedPath = [Environment]::GetFolderPath('UserProfile');"
        "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {"
        "Set-Content -LiteralPath '%s' -Value $dialog.SelectedPath -Encoding UTF8 }"
    ) % quoted
    try:
        subprocess.run(
            [
                "powershell.exe",
                "-STA",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
        selected = temp_path.read_text(encoding="utf-8-sig").strip()
        return selected or None
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProjectError(f"Could not open the folder picker: {exc}") from exc
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass

