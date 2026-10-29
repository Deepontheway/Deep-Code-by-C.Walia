"""Local Model Context Protocol (MCP) server registry and stdio client.

MCP servers are local commands explicitly configured by the user. Discovery is
started from the UI; agent-initiated tool calls always create an approval first.
Server output is untrusted data and must never be treated as instructions.
"""
from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
SERVER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,80}$")
MAX_TOOL_RESULT_BYTES = 60_000


class McpError(RuntimeError):
    pass


def _clean_id(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", (value or "").strip().lower()).strip("-_")
    if not slug:
        raise McpError("MCP server name must contain letters or numbers.")
    return slug[:41].rstrip("-_")


def _clean_command(value: str) -> str:
    command = (value or "").strip()
    if not command or len(command) > 1000 or "\x00" in command:
        raise McpError("MCP command must be a non-empty path or executable name.")
    return command


def _clean_args(values: Any) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise McpError("MCP args must be a list of strings.")
    if len(values) > 64:
        raise McpError("MCP args is limited to 64 entries.")
    result: list[str] = []
    for value in values:
        text = str(value)
        if len(text) > 2000 or "\x00" in text:
            raise McpError("An MCP argument is too long or contains a null byte.")
        result.append(text)
    return result


def _clean_env(values: Any) -> dict[str, str]:
    if values is None:
        return {}
    if not isinstance(values, dict):
        raise McpError("MCP environment variables must be an object.")
    result: dict[str, str] = {}
    for key, value in values.items():
        name = str(key).strip()
        if not ENV_KEY_PATTERN.match(name):
            raise McpError(f"Invalid environment variable name: {name}")
        text = str(value)
        if len(text) > 4000 or "\x00" in text:
            raise McpError(f"Environment value for {name} is too long.")
        result[name] = text
    return result


def _clean_cwd(value: str) -> str:
    path = (value or "").strip()
    if not path:
        return ""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise McpError("MCP working directory must be an absolute path.")
    if not candidate.is_dir():
        raise McpError("MCP working directory does not exist.")
    return str(candidate.resolve())


class _McpSession:
    def __init__(self, server: dict[str, Any], timeout: float = 20.0):
        self.server = server
        self.timeout = timeout
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stderr: list[str] = []
        self._next_id = 1
        self._write_lock = threading.Lock()
        self._closed = False
        env = os.environ.copy()
        env.update(server.get("env") or {})
        kwargs: dict[str, Any] = {}
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.process = subprocess.Popen(
                [server["command"], *server.get("args", [])],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=server.get("cwd") or None,
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **kwargs,
            )
        except OSError as exc:
            raise McpError(f"Could not start MCP server '{server['name']}': {exc}") from exc
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()
        self._err_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self._err_reader.start()

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if isinstance(message, dict):
                self._queue.put(message)

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            text = line.rstrip()
            if text:
                self._stderr.append(text[:2000])
                del self._stderr[:-40]

    @property
    def stderr_text(self) -> str:
        return "\n".join(self._stderr)[-4000:]

    def _send(self, payload: dict[str, Any]) -> None:
        if self._closed or self.process.stdin is None:
            raise McpError("MCP server connection is closed.")
        try:
            with self._write_lock:
                self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
                self.process.stdin.flush()
        except (OSError, ValueError) as exc:
            raise McpError(f"Could not write to MCP server: {exc}") from exc

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                detail = self.stderr_text
                suffix = f" Server stderr: {detail}" if detail else ""
                raise McpError(f"MCP server did not answer {method} in time.{suffix}")
            try:
                message = self._queue.get(timeout=remaining)
            except queue.Empty:
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                error = message.get("error") or {}
                raise McpError(str(error.get("message") or error.get("code") or "MCP request failed."))
            result = message.get("result")
            return result if isinstance(result, dict) else {"result": result}

    def initialize(self) -> dict[str, Any]:
        result = self.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "deep-code-by-c-walia", "version": "0.1"},
            },
        )
        self.notify("notifications/initialized")
        return result

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        process = getattr(self, "process", None)
        if process is None:
            return
        try:
            if process.stdin:
                process.stdin.close()
        except OSError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
        for stream in (process.stdout, process.stderr):
            try:
                if stream:
                    stream.close()
            except OSError:
                pass

    def __enter__(self) -> "_McpSession":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


class McpStore:
    def __init__(self, home: Path):
        self.path = Path(home) / "mcp.json"
        self._lock = threading.Lock()

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return {"servers": []}
        if not isinstance(data, dict) or not isinstance(data.get("servers"), list):
            return {"servers": []}
        servers = []
        for entry in data["servers"]:
            if isinstance(entry, dict) and entry.get("id") and entry.get("command"):
                servers.append(entry)
        return {"servers": servers}

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _public(server: dict[str, Any], include_env: bool = False) -> dict[str, Any]:
        result = {
            "id": server.get("id", ""),
            "name": server.get("name", ""),
            "command": server.get("command", ""),
            "args": server.get("args", []),
            "cwd": server.get("cwd", ""),
            "enabled": bool(server.get("enabled", True)),
            "tools": server.get("tools", []),
            "last_error": server.get("last_error", ""),
            "discovered_at": server.get("discovered_at"),
        }
        if include_env:
            result["env"] = server.get("env", {})
        else:
            result["env_keys"] = sorted((server.get("env") or {}).keys())
        return result

    def list_servers(self) -> list[dict[str, Any]]:
        with self._lock:
            data = self._load()
        return [self._public(server) for server in data["servers"]]

    def get_server(self, server_id: str, include_env: bool = False) -> dict[str, Any] | None:
        with self._lock:
            data = self._load()
        for server in data["servers"]:
            if server.get("id") == server_id:
                return self._public(server, include_env=include_env)
        return None

    def _internal(self, server_id: str) -> dict[str, Any] | None:
        data = self._load()
        for server in data["servers"]:
            if server.get("id") == server_id:
                return server
        return None

    def add_server(
        self,
        *,
        name: str,
        command: str,
        args: Any = None,
        env: Any = None,
        cwd: str = "",
        enabled: bool = True,
    ) -> dict[str, Any]:
        clean_name = " ".join((name or "").split())[:80]
        if not clean_name:
            raise McpError("MCP server name is required.")
        server = {
            "id": _clean_id(clean_name),
            "name": clean_name,
            "command": _clean_command(command),
            "args": _clean_args(args),
            "env": _clean_env(env),
            "cwd": _clean_cwd(cwd),
            "enabled": bool(enabled),
            "tools": [],
            "last_error": "",
            "discovered_at": None,
        }
        with self._lock:
            data = self._load()
            if any(item.get("id") == server["id"] for item in data["servers"]):
                raise McpError("An MCP server with that name already exists.")
            data["servers"].append(server)
            self._save(data)
        return self._public(server)

    def set_enabled(self, server_id: str, enabled: bool) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            for server in data["servers"]:
                if server.get("id") == server_id:
                    server["enabled"] = bool(enabled)
                    self._save(data)
                    return self._public(server)
        raise McpError("MCP server not found.")

    def remove_server(self, server_id: str) -> bool:
        with self._lock:
            data = self._load()
            before = len(data["servers"])
            data["servers"] = [item for item in data["servers"] if item.get("id") != server_id]
            if len(data["servers"]) == before:
                return False
            self._save(data)
            return True

    def _mark_discovery(
        self,
        server_id: str,
        *,
        tools: list[dict[str, Any]] | None = None,
        error: str = "",
    ) -> None:
        with self._lock:
            data = self._load()
            for server in data["servers"]:
                if server.get("id") == server_id:
                    if tools is not None:
                        server["tools"] = tools
                        server["discovered_at"] = time.time()
                    server["last_error"] = error[:1000]
                    self._save(data)
                    return

    def discover(self, server_id: str) -> dict[str, Any]:
        server = self._internal(server_id)
        if server is None:
            raise McpError("MCP server not found.")
        if not server.get("enabled", True):
            raise McpError("Enable this MCP server before discovering tools.")
        try:
            with _McpSession(server) as session:
                session.initialize()
                result = session.request("tools/list")
        except McpError as exc:
            self._mark_discovery(server_id, error=str(exc))
            raise
        tools = []
        for item in result.get("tools", []):
            if not isinstance(item, dict) or not item.get("name"):
                continue
            tools.append(
                {
                    "name": str(item["name"])[:120],
                    "description": str(item.get("description") or "")[:600],
                    "input_schema": item.get("inputSchema") if isinstance(item.get("inputSchema"), dict) else {},
                }
            )
        self._mark_discovery(server_id, tools=tools)
        updated = self.get_server(server_id)
        assert updated is not None
        return updated

    def call_tool(self, server_id: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        server = self._internal(server_id)
        if server is None:
            raise McpError("MCP server not found.")
        if not server.get("enabled", True):
            raise McpError("This MCP server is disabled.")
        known = {str(item.get("name")) for item in server.get("tools", []) if isinstance(item, dict)}
        if known and tool_name not in known:
            raise McpError(f"Tool '{tool_name}' is not in the discovered tool list for this server.")
        with _McpSession(server, timeout=60.0) as session:
            session.initialize()
            result = session.request(
                "tools/call",
                {"name": tool_name, "arguments": arguments if isinstance(arguments, dict) else {}},
            )
        encoded = json.dumps(result, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > MAX_TOOL_RESULT_BYTES:
            result = {"truncated": True, "preview": encoded[:MAX_TOOL_RESULT_BYTES]}
        return result if isinstance(result, dict) else {"result": result}
