from __future__ import annotations

import base64
import hmac
import json
import os
import re
import sqlite3
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

PRODUCT = "deep-code-by-cwalia"
CODE_PREFIX = "WALIA1"
INSTALL_ID_RE = re.compile(r"^DC-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_REQUEST_DAYS = 3650
ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("ACTIVATION_DB") or (ROOT / "data" / "activation.sqlite3"))
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://") :]
USING_POSTGRES = DATABASE_URL.startswith("postgresql://")
RATE_LIMIT_WINDOW = 3600
RATE_LIMIT_MAX = 40

app = FastAPI(title="Deep Code Activation Server", version="1.1.0")
_rate: dict[str, list[float]] = {}


def owner_token() -> str:
    return os.environ.get("OWNER_TOKEN", "").strip()


class Connection:
    """Small DB-API adapter so the server runs on SQLite locally and Postgres in production."""

    def __init__(self, raw: Any, postgres: bool) -> None:
        self.raw = raw
        self.postgres = postgres

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        if self.postgres:
            sql = sql.replace("?", "%s")
        return self.raw.execute(sql, params)

    def executescript(self, script: str) -> None:
        if not self.postgres:
            self.raw.executescript(script)
            return
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self.raw.execute(statement)

    def __enter__(self) -> "Connection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        if exc_type is None:
            self.raw.commit()
        else:
            self.raw.rollback()
        self.raw.close()
        return False


def connect() -> Connection:
    if USING_POSTGRES:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("Install psycopg[binary] to use DATABASE_URL.") from exc
        return Connection(psycopg.connect(DATABASE_URL, row_factory=dict_row), True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return Connection(conn, False)


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY,
                install_id TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                code TEXT,
                decision_note TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_requests_install ON requests(install_id, created_at);
            """
        )


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def public_view(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    return {
        "id": item["id"],
        "install_id": item["install_id"],
        "status": item["status"],
        "code": item.get("code") if item["status"] == "approved" else None,
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
    }


def admin_view(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return dict(row)


def check_rate(request: Request) -> None:
    host = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = [stamp for stamp in _rate.get(host, []) if now - stamp < RATE_LIMIT_WINDOW]
    if len(bucket) >= RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many activation requests. Try again later.")
    bucket.append(now)
    _rate[host] = bucket


def require_owner(
    authorization: str | None = Header(default=None),
    x_owner_token: str | None = Header(default=None),
) -> None:
    expected = owner_token()
    if not expected:
        raise HTTPException(status_code=503, detail="OWNER_TOKEN is not configured on the server.")
    supplied = (x_owner_token or "").strip()
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Owner token is missing or invalid.")


def load_private_key() -> Ed25519PrivateKey:
    pem = os.environ.get("ACTIVATION_PRIVATE_KEY_PEM", "").strip()
    path = os.environ.get("ACTIVATION_PRIVATE_KEY_PATH", "").strip()
    if pem:
        data = pem.replace("\\n", "\n").encode("utf-8")
    elif path:
        key_path = Path(path).expanduser()
        if not key_path.is_file():
            raise HTTPException(status_code=503, detail="Owner private key file is missing.")
        data = key_path.read_bytes()
    else:
        raise HTTPException(status_code=503, detail="Owner private key is not configured.")
    try:
        key = serialization.load_pem_private_key(data, password=None)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Owner private key is invalid: {exc}") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise HTTPException(status_code=503, detail="Owner private key is not an Ed25519 key.")
    return key


def b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def issue_code(install_id: str, name: str, email: str, days: int) -> str:
    if days < 0 or days > MAX_REQUEST_DAYS:
        raise HTTPException(status_code=400, detail=f"days must be between 0 and {MAX_REQUEST_DAYS}.")
    issued = date.today()
    expires = None if days == 0 else (issued + timedelta(days=days)).isoformat()
    payload = {
        "v": 1,
        "product": PRODUCT,
        "install_id": install_id,
        "name": name.strip(),
        "email": email.strip(),
        "issued": issued.isoformat(),
        "expires": expires,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = load_private_key().sign(raw)
    return f"{CODE_PREFIX}.{b64encode(raw)}.{b64encode(signature)}"


class AccessRequest(BaseModel):
    install_id: str = Field(min_length=16, max_length=32)
    name: str = Field(default="", max_length=120)
    email: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=1000)


class ApproveInput(BaseModel):
    days: int = 365
    name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=200)
    note: str = Field(default="", max_length=1000)


class RejectInput(BaseModel):
    note: str = Field(default="", max_length=1000)


init_db()


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "product": "deep-code-activation",
        "database": "postgres" if USING_POSTGRES else "sqlite",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/requests")
def create_request(payload: AccessRequest, request: Request) -> dict[str, Any]:
    check_rate(request)
    install_id = payload.install_id.strip().upper()
    if not INSTALL_ID_RE.match(install_id):
        raise HTTPException(status_code=400, detail="Install ID must look like DC-XXXX-XXXX-XXXX.")
    email = payload.email.strip()
    if email and not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Email address is not valid.")
    now = time.time()
    with connect() as conn:
        existing = conn.execute(
            "SELECT * FROM requests WHERE install_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
            (install_id,),
        ).fetchone()
        if existing:
            return {"id": existing["id"], "status": existing["status"], "install_id": install_id}
        request_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO requests (id, install_id, name, email, note, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)",
            (request_id, install_id, payload.name.strip(), email, payload.note.strip(), now, now),
        )
    return {"id": request_id, "status": "pending", "install_id": install_id}


@app.get("/api/requests/{request_id}")
def get_request(request_id: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Activation request not found.")
    return public_view(row)


@app.get("/api/admin/requests")
def list_requests(_: None = Depends(require_owner)) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM requests ORDER BY created_at DESC LIMIT 500").fetchall()
    return [admin_view(row) for row in rows]


@app.get("/api/admin/stats")
def admin_stats(_: None = Depends(require_owner)) -> dict[str, int]:
    with connect() as conn:
        rows = conn.execute("SELECT status, COUNT(*) AS total FROM requests GROUP BY status").fetchall()
    counts = {"pending": 0, "approved": 0, "rejected": 0}
    for row in rows:
        counts[row["status"]] = int(row["total"])
    counts["total"] = sum(counts.get(key, 0) for key in ("pending", "approved", "rejected"))
    return counts


@app.post("/api/admin/requests/{request_id}/approve")
def approve_request(
    request_id: str,
    payload: ApproveInput,
    _: None = Depends(require_owner),
) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Activation request not found.")
    if row["status"] == "rejected":
        raise HTTPException(status_code=409, detail="This request was already rejected.")
    name = (payload.name if payload.name is not None else row["name"]).strip()
    email = (payload.email if payload.email is not None else row["email"]).strip()
    if email and not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Email address is not valid.")
    code = issue_code(row["install_id"], name, email, payload.days)
    now = time.time()
    with connect() as conn:
        conn.execute(
            "UPDATE requests SET status = 'approved', code = ?, name = ?, email = ?, decision_note = ?, updated_at = ? WHERE id = ?",
            (code, name, email, payload.note.strip(), now, request_id),
        )
    return {"id": request_id, "status": "approved", "code": code, "install_id": row["install_id"]}


@app.post("/api/admin/requests/{request_id}/reject")
def reject_request(
    request_id: str,
    payload: RejectInput,
    _: None = Depends(require_owner),
) -> dict[str, Any]:
    now = time.time()
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE requests SET status = 'rejected', code = NULL, decision_note = ?, updated_at = ? WHERE id = ?",
            (payload.note.strip(), now, request_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Activation request not found.")
    return {"id": request_id, "status": "rejected"}


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD


DASHBOARD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Deep Code Activation</title>
<style>
:root { color-scheme: dark; --bg:#0c0c0e; --panel:#161618; --elev:#1c1c1f; --border:#38383a; --text:#f4f4f5; --muted:#a1a1aa; --accent:#0a84ff; --green:#30d158; --yellow:#ff9f0a; --red:#ff453a; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--text); font:13px/1.5 -apple-system, "Segoe UI", sans-serif; padding:24px; }
h1 { margin:0 0 4px; font-size:18px; }
.sub { color:var(--muted); margin-bottom:18px; }
.bar { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:16px; }
input, select, button { font:inherit; color:var(--text); background:var(--elev); border:1px solid var(--border); border-radius:8px; padding:8px 10px; }
input { min-width:280px; }
button { cursor:pointer; }
button:hover { border-color:var(--accent); }
button.primary { background:var(--accent); border-color:var(--accent); color:white; }
button.danger { color:var(--red); }
button.good { color:var(--green); }
.stats { display:flex; gap:10px; margin-bottom:16px; }
.stat { background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:10px 14px; min-width:110px; }
.stat b { display:block; font-size:20px; }
.stat span { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.08em; }
table { width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--border); border-radius:12px; overflow:hidden; }
th, td { text-align:left; padding:10px; border-bottom:1px solid var(--border); vertical-align:top; }
th { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.08em; }
tr:last-child td { border-bottom:0; }
.mono { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size:11px; }
.note { color:var(--muted); max-width:260px; }
.status { font-size:11px; text-transform:uppercase; letter-spacing:.08em; }
.status.pending { color:var(--yellow); }
.status.approved { color:var(--green); }
.status.rejected { color:var(--red); }
.code { max-width:340px; word-break:break-all; }
.toast { position:fixed; right:20px; bottom:20px; background:var(--elev); border:1px solid var(--border); border-radius:10px; padding:12px 16px; box-shadow:0 20px 60px rgba(0,0,0,.6); display:none; max-width:420px; }
.toast.show { display:block; }
.empty { color:var(--muted); padding:24px; text-align:center; }
</style>
</head>
<body>
<h1>Deep Code Activation</h1>
<div class="sub">Approve installation requests and issue signed access codes.</div>
<div class="bar">
  <input id="token" type="password" placeholder="Owner token">
  <button class="primary" id="save">Save token</button>
  <button id="refresh">Refresh</button>
  <select id="filter">
    <option value="pending">Pending</option>
    <option value="all">All</option>
    <option value="approved">Approved</option>
    <option value="rejected">Rejected</option>
  </select>
</div>
<div class="stats" id="stats"></div>
<div id="list"><div class="empty">Enter the owner token to load requests.</div></div>
<div class="toast" id="toast"></div>
<script>
const $ = (id) => document.getElementById(id);
let timer = null;
function toast(message, bad) {
  const node = $("toast");
  node.textContent = message;
  node.style.borderColor = bad ? "var(--red)" : "var(--green)";
  node.classList.add("show");
  clearTimeout(node._t);
  node._t = setTimeout(() => node.classList.remove("show"), 4000);
}
function token() { return $("token").value.trim() || localStorage.getItem("deepcode_owner_token") || ""; }
function esc(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
async function api(path, options) {
  const opts = Object.assign({}, options || {});
  opts.headers = Object.assign({"Authorization": "Bearer " + token()}, opts.headers || {});
  const response = await fetch(path, opts);
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail || detail; } catch (e) {}
    throw new Error(detail);
  }
  return response.json();
}
function renderStats(stats) {
  $("stats").innerHTML = ["pending","approved","rejected","total"].map((key) =>
    `<div class="stat"><b>${Number(stats[key] || 0)}</b><span>${key}</span></div>`).join("");
}
function render(rows) {
  if (!rows.length) { $("list").innerHTML = '<div class="empty">No requests in this view.</div>'; return; }
  const filter = $("filter").value;
  const visible = filter === "all" ? rows : rows.filter((row) => row.status === filter);
  if (!visible.length) { $("list").innerHTML = '<div class="empty">No requests in this view.</div>'; return; }
  const table = document.createElement("table");
  table.innerHTML = "<thead><tr><th>Install ID</th><th>Person</th><th>Note</th><th>Status</th><th>Code</th><th>Actions</th></tr></thead><tbody></tbody>";
  const body = table.querySelector("tbody");
  for (const row of visible) {
    const tr = document.createElement("tr");
    const when = new Date((row.created_at || 0) * 1000).toLocaleString();
    tr.innerHTML = `
      <td><div class="mono">${esc(row.install_id)}</div><div class="note">${esc(when)}</div></td>
      <td><div>${esc(row.name || "Unknown")}</div><div class="note">${esc(row.email || "")}</div></td>
      <td class="note">${esc(row.note || "")}</td>
      <td><span class="status ${esc(row.status)}">${esc(row.status)}</span></td>
      <td class="mono code">${row.code ? esc(row.code) : ""}</td>
      <td></td>`;
    const actions = tr.querySelector("td:last-child");
    if (row.status !== "approved") {
      const approve = document.createElement("button");
      approve.className = "good";
      approve.textContent = "Approve";
      approve.onclick = () => approveRow(row).catch((e) => toast(e.message, true));
      actions.appendChild(approve);
    }
    if (row.code) {
      const copy = document.createElement("button");
      copy.textContent = "Copy";
      copy.onclick = async () => { await navigator.clipboard.writeText(row.code); toast("Code copied."); };
      actions.appendChild(copy);
    }
    if (row.status === "pending") {
      const reject = document.createElement("button");
      reject.className = "danger";
      reject.textContent = "Reject";
      reject.onclick = () => rejectRow(row).catch((e) => toast(e.message, true));
      actions.appendChild(reject);
    }
    body.appendChild(tr);
  }
  $("list").textContent = "";
  $("list").appendChild(table);
}
async function load() {
  if (!token()) { $("list").innerHTML = '<div class="empty">Enter the owner token to load requests.</div>'; return; }
  try {
    const stats = await api("/api/admin/stats");
    const rows = await api("/api/admin/requests");
    renderStats(stats);
    render(rows);
  } catch (error) {
    toast(error.message, true);
  }
}
async function approveRow(row) {
  const answer = prompt("Days until expiry (0 = never)", "365");
  if (answer === null) return;
  const days = Number(answer);
  if (!Number.isInteger(days) || days < 0 || days > 3650) { toast("Enter 0 or a number up to 3650.", true); return; }
  const result = await api("/api/admin/requests/" + encodeURIComponent(row.id) + "/approve", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({days: days})
  });
  await navigator.clipboard.writeText(result.code).catch(() => {});
  toast("Approved. Code copied to clipboard.");
  await load();
}
async function rejectRow(row) {
  if (!confirm("Reject the request from " + (row.name || row.install_id) + "?")) return;
  await api("/api/admin/requests/" + encodeURIComponent(row.id) + "/reject", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({note: ""})
  });
  toast("Request rejected.");
  await load();
}
$("save").onclick = () => {
  localStorage.setItem("deepcode_owner_token", $("token").value.trim());
  load();
};
$("refresh").onclick = () => load();
$("filter").onchange = () => load();
$("token").value = localStorage.getItem("deepcode_owner_token") || "";
if (token()) load();
timer = setInterval(() => { if (token()) load(); }, 15000);
</script>
</body>
</html>
"""



