from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PRODUCT = "deep-code-by-cwalia"
CODE_PREFIX = "WALIA1"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_KEY = ROOT / "app" / "walia" / "activation_public_key.pem"


def default_private_key() -> Path:
    configured = os.environ.get("WALIACODE_OWNER_KEY")
    if configured:
        return Path(configured).expanduser()
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / ".local" / "share"
    return base / "Deep Code by C.Walia" / "owner_private_key.pem"


def b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def load_private_key(path: Path) -> Ed25519PrivateKey:
    if not path.is_file():
        raise SystemExit(f"Owner private key not found: {path}\nRun: python scripts/activation_owner.py init")
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except Exception as exc:
        raise SystemExit(f"Could not read owner private key: {exc}") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit("Owner private key is not an Ed25519 key.")
    return key


def command_init(args: argparse.Namespace) -> None:
    private_path = Path(args.private_key).expanduser()
    public_path = Path(args.public_key).expanduser()
    if private_path.exists() and not args.force:
        raise SystemExit(f"Private key already exists: {private_path}\nUse --force only if you intend to invalidate every existing access code.")
    if public_path.exists() and not args.force:
        raise SystemExit(f"Public key already exists: {public_path}\nUse --force only if you intend to invalidate every existing access code.")
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    private_bytes = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    private_path.write_bytes(private_bytes)
    try:
        private_path.chmod(0o600)
    except OSError:
        pass
    public_path.write_bytes(public_bytes)
    fingerprint = b64encode(key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ))
    print("Owner keypair created.")
    print(f"Private key: {private_path}  (never share or commit this file)")
    print(f"Public key:  {public_path}")
    print(f"Public fingerprint: {fingerprint}")


def command_issue(args: argparse.Namespace) -> None:
    key = load_private_key(Path(args.private_key).expanduser())
    install_id = args.install_id.strip().upper()
    if not install_id.startswith("DC-"):
        raise SystemExit("Install ID must look like DC-XXXX-XXXX-XXXX.")
    issued = date.today()
    if args.days < 0:
        raise SystemExit("--days must be 0 (never expires) or a positive number.")
    expires = None if args.days == 0 else (issued + timedelta(days=args.days)).isoformat()
    payload = {
        "v": 1,
        "product": PRODUCT,
        "install_id": install_id,
        "name": args.name.strip(),
        "email": args.email.strip(),
        "issued": issued.isoformat(),
        "expires": expires,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = key.sign(raw)
    code = f"{CODE_PREFIX}.{b64encode(raw)}.{b64encode(signature)}"
    print(code)


def command_verify(args: argparse.Namespace) -> None:
    sys.path.insert(0, str(ROOT / "app"))
    from walia.activation import ActivationError, verify_code

    try:
        payload = verify_code(args.code)
    except ActivationError as exc:
        raise SystemExit(f"INVALID: {exc}") from exc
    print(json.dumps(payload, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deep Code owner activation tool")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create the owner Ed25519 keypair")
    init.add_argument("--private-key", default=str(default_private_key()))
    init.add_argument("--public-key", default=str(DEFAULT_PUBLIC_KEY))
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=command_init)

    issue = sub.add_parser("issue", help="Issue an access code for one install ID")
    issue.add_argument("--install-id", required=True)
    issue.add_argument("--name", default="")
    issue.add_argument("--email", default="")
    issue.add_argument("--days", type=int, default=365, help="Days until expiry; 0 means never")
    issue.add_argument("--private-key", default=str(default_private_key()))
    issue.set_defaults(func=command_issue)

    verify = sub.add_parser("verify", help="Verify a code against this computer's install ID")
    verify.add_argument("--code", required=True)
    verify.set_defaults(func=command_verify)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
