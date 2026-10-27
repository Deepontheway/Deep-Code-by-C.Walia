from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from . import agent, security
from .skills import list_skills
from .store import Store


def _home_dir() -> Path:
    configured = os.environ.get("WALIACODE_HOME")
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
    else:
        path = Path.home() / ".walia-code"
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


HOME = _home_dir()
CONFIG_PATH = HOME / "config.json"
STORE = Store(HOME / "walia.sqlite3")


def _config() -> dict[str, Any]:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {"base_url": "https://api.openai.com/v1", "model": "", "workspace": ""}


def _save_config(data: dict[str, Any]) -> None:
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_PATH)


def _get_api_key() -> str | None:
    env_key = os.environ.get("WALIACODE_API_KEY")
    if env_key:
        return env_key
    try:
        import keyring
        return keyring.get_password("walia-code", "provider_api_key")
    except Exception:
        return None


def _store_api_key(value: str | None) -> None:
    try:
        import keyring
        if value:
            keyring.set_password("walia-code", "provider_api_key", value)
        else:
            keyring.delete_password("walia-code", "provider_api_key")
    except Exception as exc:
        if value:
            raise HTTPException(status_code=503, detail="The operating-system credential store is unavailable. Set WALIACODE_API_KEY in the launcher environment or configure Windows Credential Manager, then retry. The key was not saved to a file.") from exc


app = FastAPI(title="WaliaCode", version="0.1.0", docs_url=None, redoc_url=None)


class ConfigInput(BaseModel):
    base_url: str = Field(min_length=8, max_length=500)
    model: str = Field(min_length=1, max_length=200)
    workspace: str = Field(default="", max_length=2000)
    api_key: str | None = Field(default=None, max_length=4000)
    clear_api_key: bool = False


class WorkspaceInput(BaseModel):
    path: str = Field(min_length=1, max_length=2000)


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    session_id: str | None = None


class DecisionInput(BaseModel):
    approved: bool


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    page = Path(__file__).parent / "web" / "index.html"
    return page.read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "product": "WaliaCode", "version": app.version}


@app.get("/api/config")
def get_config() -> dict:
    config = _config()
    return {
        "base_url": config.get("base_url", "https://api.openai.com/v1"),
        "model": config.get("model", ""),
        "workspace": config.get("workspace", ""),
        "api_key_configured": bool(_get_api_key()),
    }


@app.put("/api/config")
def put_config(request: ConfigInput) -> dict:
    try:
        base_url = security.validate_provider_url(request.base_url)
        workspace = ""
        if request.workspace.strip():
            workspace = str(security.workspace_root(request.workspace.strip()))
    except (security.PolicyError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if request.api_key:
        _store_api_key(request.api_key)
    elif request.clear_api_key:
        _store_api_key(None)
    saved = {"base_url": base_url, "model": request.model.strip(), "workspace": workspace}
    _save_config(saved)
    return {"saved": True, "base_url": base_url, "model": saved["model"], "workspace": workspace, "api_key_configured": bool(_get_api_key())}


@app.put("/api/workspace")
def put_workspace(request: WorkspaceInput) -> dict:
    try:
        path = str(security.workspace_root(request.path))
    except (security.PolicyError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    config = _config()
    config["workspace"] = path
    _save_config(config)
    return {"workspace": path, "files": security.list_workspace_files(path, limit=20)}


@app.get("/api/sessions")
def get_sessions() -> list[dict]:
    return STORE.list_sessions()


@app.post("/api/sessions")
def post_session() -> dict:
    return STORE.create_session()


@app.get("/api/sessions/{session_id}/messages")
def get_messages(session_id: str) -> list[dict]:
    if not STORE.has_session(session_id):
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return STORE.messages(session_id)


@app.post("/api/chat")
async def post_chat(request: ChatInput) -> dict:
    config = _config()
    session_id = request.session_id
    if not session_id:
        session_id = STORE.create_session(request.message[:80])["id"]
    if not STORE.has_session(session_id):
        raise HTTPException(status_code=404, detail="Chat session not found.")
    workspace = config.get("workspace") or None
    try:
        base_url = security.validate_provider_url(config.get("base_url", "https://api.openai.com/v1"))
        result = await agent.chat(
            session_id=session_id,
            user_text=request.message,
            workspace=workspace,
            base_url=base_url,
            model=config.get("model", ""),
            api_key=_get_api_key(),
            store=STORE,
        )
        return result
    except (security.PolicyError, agent.AgentError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/skills")
def get_skills() -> list[dict]:
    return list_skills()


@app.get("/api/approvals")
def get_approvals() -> list[dict]:
    return STORE.pending_approvals()


async def _execute_approved(approval: dict) -> dict:
    payload = approval["payload"]
    if approval["kind"] == "write_file":
        config = _config()
        path = security.write_workspace_file(config.get("workspace"), payload["path"], payload["content"])
        return {"path": path, "bytes_written": len(payload["content"].encode("utf-8"))}
    if approval["kind"] == "command":
        config = _config()
        result = await run_in_threadpool(security.run_approved_command, payload["argv"], payload.get("cwd"), config.get("workspace"))
        return result
    if approval["kind"] == "https_get":
        url = security.validate_public_https_url(payload["url"])
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0), follow_redirects=False) as client:
            response = await client.get(url, headers={"User-Agent": "WaliaCode/0.1 (user-approved read-only fetch)"})
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if len(response.content) > 1_000_000:
            raise HTTPException(status_code=413, detail="Response exceeded the 1 MB read limit.")
        if content_type not in {"text/plain", "text/html", "application/json", "application/xml", "text/xml"}:
            raise HTTPException(status_code=415, detail=f"Unsupported response content type: {content_type or 'unknown'}")
        response.raise_for_status()
        return {"url": url, "status_code": response.status_code, "content_type": content_type, "content": response.text[:20000]}
    raise HTTPException(status_code=400, detail="Unsupported approval action.")


@app.post("/api/approvals/{approval_id}/decision")
async def decide_approval(approval_id: str, request: DecisionInput) -> dict:
    approval = STORE.resolve_approval(approval_id, request.approved)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval was already resolved or does not exist.")
    if approval["state"] == "expired":
        raise HTTPException(status_code=410, detail="Approval expired; ask the agent to propose it again.")
    if not request.approved:
        return {"state": "rejected", "approval_id": approval_id}
    try:
        result = await _execute_approved(approval)
        STORE.add_message(approval["session_id"], "assistant", f"Approved {approval['kind']} completed. Result: {json.dumps(result, ensure_ascii=False)[:4000]}")
        return {"state": "completed", "approval_id": approval_id, "result": result}
    except Exception as exc:
        STORE.add_message(approval["session_id"], "assistant", f"Approved {approval['kind']} failed: {str(exc)[:1000]}")
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=str(exc)) from exc
