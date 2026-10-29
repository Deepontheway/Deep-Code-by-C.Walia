from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from . import activation as activation_mod
from . import agent, security
from .downloads import DownloadManager
from .local_models import (
    LOCAL_MODEL_BASE_URL,
    LOCAL_MODEL_ID,
    LOCAL_MODEL_URL,
    LocalModelError,
    LocalModelRuntime,
)
from .runtime import MODEL_CATALOG, ensure_runtime_layout, model_catalog, runtime_status
from .setup_catalog import SETUP_COMPONENTS
from .languages import catalog as language_catalog, detect_project_languages
from .mcp import McpError, McpStore
from .projects import ProjectError, ProjectStore, browse_for_folder
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


HOME = ensure_runtime_layout()
CONFIG_PATH = HOME / "config.json"
STORE = Store(HOME / "walia.sqlite3")
ACTIVATION = activation_mod.Activation(HOME)
PROJECTS = ProjectStore(HOME)
MCP = McpStore(HOME)
DOWNLOADS = DownloadManager()
LOCAL_MODELS = LocalModelRuntime(HOME)


def _config() -> dict[str, Any]:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {
        "base_url": "https://opencode.ai/zen/v1",
        "model": "big-pickle",
        "workspace": "",
        "personality_mode": "auto",
        "chaos_level": 1,
        "privacy_mode": "local-first",
    }


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

_PUBLIC_PATHS = {"/", "/health", "/logo.png", "/favicon.ico"}
_PUBLIC_PREFIXES = ("/api/activation",)


@app.middleware("http")
async def activation_gate(request, call_next):
    path = request.url.path
    if path in _PUBLIC_PATHS or any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
        return await call_next(request)
    if not ACTIVATION.is_active():
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=403,
            content={
                "detail": "This installation is not activated. Open the app and enter the access code from the owner.",
                "activation_required": True,
                "install_id": ACTIVATION.install_id,
                "owner_email": activation_mod.OWNER_EMAIL,
            },
        )
    return await call_next(request)


class ConfigInput(BaseModel):
    base_url: str = Field(min_length=8, max_length=500)
    model: str = Field(min_length=1, max_length=200)
    workspace: str = Field(default="", max_length=2000)
    api_key: str | None = Field(default=None, max_length=4000)
    clear_api_key: bool = False
    personality_mode: str = Field(
        default="auto",
        pattern="^(auto|companion|standard|minimal|mentor|engineer|playful|stoic|hype|caring|chaotic)$",
    )
    chaos_level: int = Field(default=1, ge=0, le=3)
    privacy_mode: str = Field(default="local-first", pattern="^(local-first|cloud-with-consent)$")


class WorkspaceInput(BaseModel):
    path: str = Field(min_length=1, max_length=2000)


class ProjectInput(BaseModel):
    path: str = Field(min_length=1, max_length=2000)
    name: str = Field(default="", max_length=120)
    activate: bool = False


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    session_id: str | None = None


class DecisionInput(BaseModel):
    approved: bool


class SessionTitleInput(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ModelDownloadInput(BaseModel):
    model: str = Field(min_length=1, max_length=200)
    session_id: str | None = None


class MemoryInput(BaseModel):
    content: str = Field(min_length=1, max_length=1200)
    tags: str = Field(default="", max_length=240)
    importance: int = Field(default=3, ge=1, le=5)


class McpServerInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    command: str = Field(min_length=1, max_length=1000)
    args: list[str] = Field(default_factory=list, max_length=64)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str = Field(default="", max_length=2000)
    enabled: bool = True


class McpToggleInput(BaseModel):
    enabled: bool


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    page = Path(__file__).parent / "web" / "index.html"
    return page.read_text(encoding="utf-8")


@app.get("/logo.png")
def logo() -> FileResponse:
    return FileResponse(Path(__file__).parent / "web" / "logo.png", media_type="image/png")


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    return FileResponse(Path(__file__).parent / "web" / "logo.png", media_type="image/png")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "product": "DeepCode", "version": app.version}


@app.get("/api/runtime")
def get_runtime() -> dict:
    return runtime_status()


@app.get("/api/models/catalog")
def get_model_catalog() -> dict:
    config = _config()
    models: list[dict[str, Any]] = []
    local_status = LOCAL_MODELS.status()
    for entry in model_catalog():
        model = dict(entry)
        if model.get("location") == "local":
            model["installed"] = local_status["downloaded"]
            model["server_running"] = local_status["running"]
        else:
            model["installed"] = None
        model["configured"] = (
            model["id"] == config.get("model")
            and model.get("base_url") == config.get("base_url")
        )
        models.append(model)
    return {
        "models": models,
        "local_model": local_status,
        "configured": {
            "base_url": config.get("base_url"),
            "model": config.get("model"),
        },
    }


@app.get("/api/local-model/status")
def local_model_status() -> dict:
    return LOCAL_MODELS.status()


@app.post("/api/local-model/start")
def start_local_model() -> dict:
    try:
        return LOCAL_MODELS.ensure_running()
    except LocalModelError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/local-model/stop")
def stop_local_model() -> dict:
    LOCAL_MODELS.stop()
    return LOCAL_MODELS.status()


@app.get("/api/setup/catalog")
def get_setup_catalog() -> dict:
    return {"components": SETUP_COMPONENTS}


@app.get("/api/languages")
def get_languages() -> dict:
    return {"languages": language_catalog()}


@app.get("/api/workspace/languages")
def get_workspace_languages() -> dict:
    config = _config()
    workspace = config.get("workspace")
    if not workspace:
        return {"languages": []}
    try:
        root = security.workspace_root(workspace)
    except (security.PolicyError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"languages": detect_project_languages(root)}


@app.get("/api/opencode/models")
async def opencode_models() -> dict:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0), follow_redirects=False) as client:
            response = await client.get("https://opencode.ai/zen/v1/models")
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Could not load the OpenCode model catalog.") from exc
    ids = [str(item.get("id", "")) for item in payload.get("data", []) if isinstance(item, dict)]
    ids = [item for item in ids if item]
    free = [item for item in ids if agent.is_free_opencode_model(item)]
    return {"free": free, "all": ids}


@app.get("/api/ollama/models")
async def ollama_models() -> dict:
    models = await _installed_ollama_models()
    if models is None:
        return {"running": False, "models": []}
    return {"running": True, "models": models}


@app.get("/api/personalities")
def get_personalities() -> dict:
    return {"personalities": list(agent.PERSONALITY_PACKS), "chaos_levels": agent.CHAOS_PROMPTS}


@app.get("/api/config")
def get_config() -> dict:
    config = _config()
    return {
        "base_url": config.get("base_url", "https://opencode.ai/zen/v1"),
        "model": config.get("model", ""),
        "workspace": config.get("workspace", ""),
        "personality_mode": config.get("personality_mode", "auto"),
        "chaos_level": int(config.get("chaos_level", 1)),
        "privacy_mode": config.get("privacy_mode", "local-first"),
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
    saved = {
        "base_url": base_url,
        "model": request.model.strip(),
        "workspace": workspace,
        "personality_mode": request.personality_mode,
        "chaos_level": request.chaos_level,
        "privacy_mode": request.privacy_mode,
    }
    _save_config(saved)
    return {
        "saved": True,
        "base_url": base_url,
        "model": saved["model"],
        "workspace": workspace,
        "personality_mode": saved["personality_mode"],
        "chaos_level": saved["chaos_level"],
        "privacy_mode": saved["privacy_mode"],
        "api_key_configured": bool(_get_api_key()),
    }


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


def _activate_project(project: dict) -> dict:
    config = _config()
    config["workspace"] = project["path"]
    _save_config(config)
    return {"workspace": project["path"], "project": project}


@app.get("/api/projects")
def get_projects() -> dict:
    active = _config().get("workspace", "")
    projects = PROJECTS.list()
    for project in projects:
        project["active"] = bool(active) and os.path.normcase(project["path"]) == os.path.normcase(active)
    return {"projects": projects, "active": active}


@app.post("/api/projects")
def post_project(request: ProjectInput) -> dict:
    try:
        project = PROJECTS.add(request.path, request.name)
        if request.activate:
            _activate_project(project)
    except (ProjectError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"project": project, "active": _config().get("workspace", "")}


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str) -> dict:
    removed = PROJECTS.remove(project_id)
    if removed is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    config = _config()
    if config.get("workspace") and os.path.normcase(config["workspace"]) == os.path.normcase(removed["path"]):
        config["workspace"] = ""
        _save_config(config)
    return {"deleted": True, "project": removed}


@app.post("/api/projects/{project_id}/activate")
def activate_project(project_id: str) -> dict:
    project = PROJECTS.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    try:
        security.workspace_root(project["path"])
    except (security.PolicyError, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"That project folder is unavailable: {exc}") from exc
    return _activate_project(project)


@app.post("/api/projects/browse")
async def browse_project_folder() -> dict:
    try:
        selected = await run_in_threadpool(browse_for_folder)
    except ProjectError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"path": selected or "", "cancelled": selected is None}


@app.get("/api/memories")
def get_memories(q: str = "", limit: int = 100) -> dict:
    return {"memories": STORE.list_memories(limit=limit, query=q), "query": q}


@app.post("/api/memories")
def post_memory(request: MemoryInput) -> dict:
    try:
        memory = STORE.add_memory(request.content, request.tags, "manual", request.importance)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"memory": memory}


@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: str) -> dict:
    if not STORE.delete_memory(memory_id):
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"deleted": True, "id": memory_id}


@app.get("/api/mcp/servers")
def get_mcp_servers() -> dict:
    return {"servers": MCP.list_servers(), "path": str(MCP.path)}


@app.post("/api/mcp/servers")
def post_mcp_server(request: McpServerInput) -> dict:
    try:
        server = MCP.add_server(
            name=request.name,
            command=request.command,
            args=request.args,
            env=request.env,
            cwd=request.cwd,
            enabled=request.enabled,
        )
    except McpError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"server": server}


@app.patch("/api/mcp/servers/{server_id}")
def patch_mcp_server(server_id: str, request: McpToggleInput) -> dict:
    try:
        server = MCP.set_enabled(server_id, request.enabled)
    except McpError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"server": server}


@app.delete("/api/mcp/servers/{server_id}")
def delete_mcp_server(server_id: str) -> dict:
    if not MCP.remove_server(server_id):
        raise HTTPException(status_code=404, detail="MCP server not found.")
    return {"deleted": True, "id": server_id}


@app.post("/api/mcp/servers/{server_id}/discover")
async def discover_mcp_server(server_id: str) -> dict:
    try:
        server = await run_in_threadpool(MCP.discover, server_id)
    except McpError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"server": server}


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


@app.patch("/api/sessions/{session_id}")
def rename_session(session_id: str, request: SessionTitleInput) -> dict:
    try:
        result = STORE.rename_session(session_id, request.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return result


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str) -> dict:
    if not STORE.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return {"deleted": True, "session_id": session_id}


@app.get("/api/usage")
def get_usage() -> dict:
    return STORE.usage_summary()


@app.post("/api/models/download")
def download_model(request: ModelDownloadInput) -> dict:
    entry = next(
        (item for item in model_catalog() if item["id"] == request.model and item.get("location") == "local"),
        None,
    )
    if entry is None:
        raise HTTPException(status_code=400, detail="That offline model is not in the catalog.")
    if LOCAL_MODELS.is_downloaded():
        return {
            "status": "already_downloaded",
            "model": LOCAL_MODEL_ID,
            "message": "The offline model is already downloaded.",
        }
    if request.session_id and not STORE.has_session(request.session_id):
        raise HTTPException(status_code=404, detail="Chat session not found.")
    approval = STORE.create_approval(
        request.session_id or "",
        "local_model_download",
        {
            "model": LOCAL_MODEL_ID,
            "url": LOCAL_MODEL_URL,
            "destination": str(LOCAL_MODELS.model_path),
        },
    )
    return {
        "status": "pending_approval",
        "approval_id": approval["id"],
        "model": LOCAL_MODEL_ID,
        "download_gb": entry.get("download_gb"),
        "message": "Approve the download card to download the 1.96 GB offline model.",
    }


@app.get("/api/models/downloads")
def get_model_downloads() -> list[dict]:
    return DOWNLOADS.list()


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
        base_url = security.validate_provider_url(config.get("base_url", "https://opencode.ai/zen/v1"))
        if config.get("model") == LOCAL_MODEL_ID or base_url.rstrip("/") == LOCAL_MODEL_BASE_URL.rstrip("/"):
            await run_in_threadpool(LOCAL_MODELS.ensure_running)
        result = await agent.chat(
            session_id=session_id,
            user_text=request.message,
            workspace=workspace,
            base_url=base_url,
            model=config.get("model", ""),
            api_key=_get_api_key(),
            store=STORE,
            personality_mode=config.get("personality_mode", "auto"),
            chaos_level=int(config.get("chaos_level", 1)),
            mcp=MCP,
        )
        return result
    except (security.PolicyError, agent.AgentError, LocalModelError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class ActivationRequestInput(BaseModel):
    name: str = Field(default="", max_length=120)
    email: str = Field(default="", max_length=240)
    note: str = Field(default="", max_length=1000)
    server: str | None = Field(default=None, max_length=500)


class ActivationCodeInput(BaseModel):
    code: str = Field(min_length=8, max_length=4000)


@app.get("/api/activation/status")
def activation_status() -> dict:
    return ACTIVATION.status()


@app.post("/api/activation/request")
async def activation_request(request: ActivationRequestInput) -> dict:
    if request.server:
        try:
            ACTIVATION.config_path.parent.mkdir(parents=True, exist_ok=True)
            config = {}
            try:
                config = json.loads(ACTIVATION.config_path.read_text(encoding="utf-8-sig"))
                if not isinstance(config, dict):
                    config = {}
            except (OSError, ValueError):
                config = {}
            config["activation_server"] = security.validate_provider_url(request.server)
            ACTIVATION.config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        except security.PolicyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = await ACTIVATION.request_access(request.name, request.email, request.note)
    return {**result, "status": ACTIVATION.status()}


@app.post("/api/activation/check")
async def activation_check() -> dict:
    result = await ACTIVATION.check_pending()
    return result


@app.post("/api/activation/activate")
def activation_activate(request: ActivationCodeInput) -> dict:
    try:
        status = ACTIVATION.activate(request.code)
    except activation_mod.ActivationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return status


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
    if approval["kind"] == "create_folder":
        config = _config()
        path = security.create_workspace_folder(config.get("workspace"), payload["path"])
        return {"path": path, "created": "folder"}
    if approval["kind"] == "create_file":
        config = _config()
        path = security.create_workspace_file(config.get("workspace"), payload["path"], payload.get("content", ""))
        return {"path": path, "bytes_written": len(payload.get("content", "").encode("utf-8")), "created": "file"}
    if approval["kind"] == "move_path":
        config = _config()
        return security.move_workspace_path(config.get("workspace"), payload["source"], payload["destination"])
    if approval["kind"] == "delete_path":
        config = _config()
        path = security.delete_workspace_path(config.get("workspace"), payload["path"], bool(payload.get("recursive", False)))
        return {"path": path, "deleted": True}
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
    if approval["kind"] in {"model_download", "local_model_download"}:
        job = DOWNLOADS.start(payload["model"], payload["url"], Path(payload["destination"]))
        return {"model": payload["model"], "job_id": job["id"], "status": "started"}
    if approval["kind"] == "mcp_call":
        result = await run_in_threadpool(
            MCP.call_tool,
            payload["server"],
            payload["tool"],
            payload.get("arguments") or {},
        )
        return {"server": payload["server"], "tool": payload["tool"], "result": result}
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
        if approval["session_id"] and STORE.has_session(approval["session_id"]):
            STORE.add_message(approval["session_id"], "assistant", f"Approved {approval['kind']} completed. Result: {json.dumps(result, ensure_ascii=False)[:4000]}")
        return {"state": "completed", "approval_id": approval_id, "result": result}
    except Exception as exc:
        if approval["session_id"] and STORE.has_session(approval["session_id"]):
            STORE.add_message(approval["session_id"], "assistant", f"Approved {approval['kind']} failed: {str(exc)[:1000]}")
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=str(exc)) from exc

