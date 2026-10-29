from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from . import security

PRODUCT = "deep-code-by-cwalia"
PRODUCT_LABEL = "Deep Code by C.Walia"
OWNER_EMAIL = "chandandeepsinghwalia@gmail.com"
CODE_PREFIX = "WALIA1"
PUBLIC_KEY_PATH = Path(__file__).with_name("activation_public_key.pem")


class ActivationError(ValueError):
    pass


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _machine_guid() -> str:
    if os.name == "nt":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            )
            try:
                value, _ = winreg.QueryValueEx(key, "MachineGuid")
                if value:
                    return str(value)
            finally:
                winreg.CloseKey(key)
        except OSError:
            pass
    node = platform.node() or "unknown-machine"
    return hashlib.sha256(node.encode("utf-8")).hexdigest()


def make_install_id() -> str:
    digest = hashlib.sha256(f"{PRODUCT}|{_machine_guid()}".encode("utf-8")).hexdigest()[:12].upper()
    return "DC-" + "-".join(digest[i : i + 4] for i in range(0, 12, 4))


@lru_cache(maxsize=1)
def _public_key():
    if not PUBLIC_KEY_PATH.is_file():
        raise ActivationError("Activation public key is missing. Reinstall the app or contact the owner.")
    try:
        from cryptography.hazmat.primitives import serialization

        return serialization.load_pem_public_key(PUBLIC_KEY_PATH.read_bytes())
    except ImportError as exc:
        raise ActivationError("Activation support is unavailable. Install the 'cryptography' package.") from exc
    except Exception as exc:
        raise ActivationError("Activation public key is invalid.") from exc


def verify_code(code: str) -> dict[str, Any]:
    cleaned = "".join((code or "").split())
    if not cleaned:
        raise ActivationError("Paste the access code you received from the owner.")
    parts = cleaned.split(".")
    if len(parts) != 3 or parts[0] != CODE_PREFIX:
        raise ActivationError("That does not look like a Deep Code access code.")
    try:
        payload_bytes = _b64decode(parts[1])
        signature = _b64decode(parts[2])
    except (ValueError, TypeError) as exc:
        raise ActivationError("The access code is malformed.") from exc
    try:
        from cryptography.exceptions import InvalidSignature

        _public_key().verify(signature, payload_bytes)
    except ImportError as exc:
        raise ActivationError("Activation support is unavailable. Install the 'cryptography' package.") from exc
    except InvalidSignature as exc:
        raise ActivationError("The access code signature is invalid.") from exc
    except Exception as exc:
        if isinstance(exc, ActivationError):
            raise
        raise ActivationError("The access code could not be verified.") from exc
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ActivationError("The access code payload is invalid.") from exc
    if not isinstance(payload, dict):
        raise ActivationError("The access code payload is invalid.")
    if payload.get("v") != 1 or payload.get("product") != PRODUCT:
        raise ActivationError("This access code is for a different product.")
    expected_id = make_install_id()
    if str(payload.get("install_id", "")).upper() != expected_id:
        raise ActivationError("This access code was issued for a different installation.")
    expires = payload.get("expires")
    if expires:
        try:
            expiry = date.fromisoformat(str(expires))
        except ValueError as exc:
            raise ActivationError("The access code has an invalid expiry date.") from exc
        if expiry < date.today():
            raise ActivationError(f"This access code expired on {expiry.isoformat()}.")
    return payload


class Activation:
    def __init__(self, home: Path, public_key_path: Path = PUBLIC_KEY_PATH) -> None:
        self.home = Path(home)
        self.license_path = self.home / "license.json"
        self.request_path = self.home / "activation_request.json"
        self.config_path = self.home / "config.json"
        self.install_id = make_install_id()

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write_json(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)

    def server_url(self) -> str:
        configured = os.environ.get("WALIACODE_ACTIVATION_SERVER", "").strip()
        if not configured:
            configured = str(self._read_json(self.config_path).get("activation_server", "")).strip()
        if not configured:
            return ""
        try:
            return security.validate_provider_url(configured)
        except security.PolicyError:
            return ""

    def pending_ticket(self) -> dict[str, Any]:
        pending = self._read_json(self.request_path)
        if pending.get("install_id") != self.install_id:
            return {}
        return pending

    def _license_code(self) -> str:
        return str(self._read_json(self.license_path).get("code", "")).strip()

    def status(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "activated": False,
            "required": True,
            "install_id": self.install_id,
            "owner_email": OWNER_EMAIL,
            "product": PRODUCT_LABEL,
            "server_configured": bool(self.server_url()),
            "pending": self.pending_ticket(),
            "error": None,
        }
        code = self._license_code()
        if not code:
            return base
        try:
            payload = verify_code(code)
        except ActivationError as exc:
            base["error"] = str(exc)
            return base
        expires = payload.get("expires")
        days_left = None
        if expires:
            try:
                days_left = max(0, (date.fromisoformat(str(expires)) - date.today()).days)
            except ValueError:
                days_left = None
        base.update(
            {
                "activated": True,
                "name": payload.get("name", ""),
                "email": payload.get("email", ""),
                "issued": payload.get("issued"),
                "expires": expires,
                "days_left": days_left,
            }
        )
        return base

    def is_active(self) -> bool:
        return bool(self.status().get("activated"))

    def activate(self, code: str) -> dict[str, Any]:
        payload = verify_code(code)
        self._write_json(
            self.license_path,
            {
                "code": "".join(code.split()),
                "activated_at": datetime.now(timezone.utc).isoformat(),
                "install_id": self.install_id,
                "name": payload.get("name", ""),
                "email": payload.get("email", ""),
            },
        )
        self.request_path.unlink(missing_ok=True)
        return self.status()

    def _mailto(self, name: str, email: str, note: str) -> str:
        subject = f"Deep Code activation request - {self.install_id}"
        body = (
            f"Install ID: {self.install_id}\n"
            f"Name: {name or '(not provided)'}\n"
            f"Email: {email or '(not provided)'}\n"
            f"Note: {note or '(none)'}\n\n"
            "Please approve this installation and send me the access code."
        )
        return f"mailto:{OWNER_EMAIL}?subject={quote(subject)}&body={quote(body)}"

    async def request_access(self, name: str, email: str, note: str) -> dict[str, Any]:
        mailto = self._mailto(name, email, note)
        server = self.server_url()
        if not server:
            return {"mode": "email", "mailto": mailto, "install_id": self.install_id}
        payload = {
            "install_id": self.install_id,
            "name": name,
            "email": email,
            "note": note,
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(12.0), follow_redirects=False) as client:
                response = await client.post(server.rstrip("/") + "/api/requests", json=payload)
                response.raise_for_status()
                data = response.json()
            ticket = str(data.get("id") or data.get("ticket") or "").strip()
            if not ticket:
                raise ActivationError("The activation server returned no request id.")
        except (httpx.HTTPError, ValueError, ActivationError) as exc:
            return {
                "mode": "email",
                "mailto": mailto,
                "install_id": self.install_id,
                "server_error": f"The activation server could not be reached: {exc}",
            }
        self._write_json(
            self.request_path,
            {
                "ticket": ticket,
                "server": server,
                "install_id": self.install_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {"mode": "server", "ticket": ticket, "install_id": self.install_id, "mailto": mailto}

    async def check_pending(self) -> dict[str, Any]:
        pending = self.pending_ticket()
        if not pending:
            return {"status": "none", **self.status()}
        ticket = str(pending.get("ticket", "")).strip()
        server = str(pending.get("server", "")).strip()
        if not ticket or not server:
            return {"status": "none", **self.status()}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(12.0), follow_redirects=False) as client:
                response = await client.get(server.rstrip("/") + f"/api/requests/{quote(ticket)}")
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return {"status": "error", "message": f"Could not check approval status: {exc}", **self.status()}
        state = str(data.get("status", "pending")).lower()
        if state == "approved" and data.get("code"):
            try:
                result = self.activate(str(data["code"]))
            except ActivationError as exc:
                return {"status": "error", "message": str(exc), **self.status()}
            return {"status": "approved", **result}
        if state == "rejected":
            self.request_path.unlink(missing_ok=True)
            return {"status": "rejected", "message": "The owner rejected this activation request.", **self.status()}
        return {"status": state, **self.status()}
