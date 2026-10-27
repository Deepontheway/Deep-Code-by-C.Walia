from __future__ import annotations

import ipaddress
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

MAX_READ_BYTES = 2 * 1024 * 1024
MAX_WRITE_BYTES = 2 * 1024 * 1024
MAX_COMMAND_SECONDS = 60


class PolicyError(ValueError):
    """Raised when a requested operation violates a local safety boundary."""


def workspace_root(root: str | Path | None) -> Path:
    if not root:
        raise PolicyError("Choose a project workspace before using project tools.")
    resolved = Path(root).expanduser().resolve(strict=True)
    if not resolved.is_dir():
        raise PolicyError("The selected workspace is not a directory.")
    return resolved


def workspace_path(root: str | Path | None, relative_path: str) -> Path:
    base = workspace_root(root)
    raw = Path(relative_path)
    if raw.is_absolute():
        raise PolicyError("Use a path relative to the selected workspace.")
    candidate = (base / raw).resolve(strict=False)
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise PolicyError("The requested path escapes the selected workspace.") from exc
    return candidate


def list_workspace_files(root: str | Path | None, limit: int = 300) -> list[str]:
    base = workspace_root(root)
    output: list[str] = []
    for path in base.rglob("*"):
        if len(output) >= limit:
            break
        try:
            if path.is_file() and not any(part.startswith(".") for part in path.relative_to(base).parts):
                output.append(path.relative_to(base).as_posix())
        except (OSError, ValueError):
            continue
    return sorted(output)


def read_workspace_file(root: str | Path | None, relative_path: str) -> str:
    path = workspace_path(root, relative_path)
    if not path.is_file():
        raise PolicyError("The requested workspace file does not exist.")
    size = path.stat().st_size
    if size > MAX_READ_BYTES:
        raise PolicyError(f"File is larger than the {MAX_READ_BYTES}-byte read limit.")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise PolicyError("Only UTF-8 text files can be read by this tool.") from exc


def write_workspace_file(root: str | Path | None, relative_path: str, content: str) -> str:
    path = workspace_path(root, relative_path)
    data = content.encode("utf-8")
    if len(data) > MAX_WRITE_BYTES:
        raise PolicyError(f"File is larger than the {MAX_WRITE_BYTES}-byte write limit.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path = workspace_path(root, relative_path)
    path.write_text(content, encoding="utf-8", newline="")
    return str(path)


def validate_command(command: list[str], cwd: str | None, root: str | Path | None) -> tuple[list[str], Path]:
    if not isinstance(command, list) or not command or len(command) > 64:
        raise PolicyError("Provide a non-empty argument list with at most 64 entries.")
    if any(not isinstance(part, str) or "\x00" in part for part in command):
        raise PolicyError("Every command argument must be a plain string without NUL bytes.")
    if any(len(part) > 8000 for part in command):
        raise PolicyError("A command argument exceeds the allowed length.")
    base = workspace_root(root)
    run_dir = workspace_path(base, cwd or ".")
    if not run_dir.is_dir():
        raise PolicyError("The command working directory must be an existing workspace folder.")
    return command, run_dir


def run_approved_command(command: list[str], cwd: str | None, root: str | Path | None) -> dict:
    argv, run_dir = validate_command(command, cwd, root)
    try:
        completed = subprocess.run(
            argv,
            cwd=run_dir,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=MAX_COMMAND_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PolicyError(f"Command exceeded the {MAX_COMMAND_SECONDS}-second limit.") from exc
    return {
        "return_code": completed.returncode,
        "stdout": completed.stdout[-12000:],
        "stderr": completed.stderr[-12000:],
        "cwd": str(run_dir),
    }


def validate_provider_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise PolicyError("Provider URL must be an HTTP(S) URL without embedded credentials.")
    if parsed.scheme == "http":
        host = parsed.hostname.lower().rstrip(".")
        try:
            address = ipaddress.ip_address(host)
            is_loopback = address.is_loopback
        except ValueError:
            is_loopback = host == "localhost"
        if not is_loopback:
            raise PolicyError("Use HTTPS for remote model providers; plain HTTP is allowed only on localhost.")
    return url.rstrip("/")


def validate_public_https_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise PolicyError("Network fetches require an HTTPS URL without embedded credentials.")
    host = parsed.hostname.rstrip(".")
    try:
        records = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise PolicyError("The HTTPS host could not be resolved.") from exc
    for record in records:
        address = ipaddress.ip_address(record[4][0].split("%", 1)[0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast:
            raise PolicyError("Network fetches to private, local, reserved, or link-local addresses are blocked.")
    return url.strip()
