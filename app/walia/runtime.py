"""DeepCode-owned runtime paths and model metadata.

Cloud models run online. One small GGUF model can also be downloaded online on
demand and used offline through llama.cpp. No model is bundled, and Ollama is
not used or required.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

RUNTIME_FOLDERS = (
    "bin",
    "runtime",
    "models",
    "env",
    "sandbox",
    "ide",
    "plugins",
    "data",
    "training/adapters",
    "training/datasets",
    "training/evaluations",
    "cache",
    "licenses",
)

MODEL_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "id": "big-pickle",
        "label": "Big Pickle",
        "provider": "OpenCode Zen",
        "location": "cloud",
        "base_url": "https://opencode.ai/zen/v1",
        "access": "free",
        "free": True,
        "requires_key": False,
        "download_gb": None,
        "ram_gb": None,
        "can_finetune": False,
        "note": "Default free coding model. Provider limits and terms still apply.",
    },
    {
        "id": "openai-fast",
        "label": "Pollinations OpenAI Fast",
        "provider": "Pollinations",
        "location": "cloud",
        "base_url": "https://text.pollinations.ai/v1",
        "access": "free",
        "free": True,
        "requires_key": False,
        "download_gb": None,
        "ram_gb": None,
        "can_finetune": False,
        "note": "Keyless fallback when OpenCode free models are rate-limited.",
    },
    {
        "id": "qwen/qwen3-coder:free",
        "label": "Qwen3 Coder (OpenRouter free)",
        "provider": "OpenRouter",
        "location": "cloud",
        "base_url": "https://openrouter.ai/api/v1",
        "access": "key",
        "free": True,
        "requires_key": True,
        "download_gb": None,
        "ram_gb": None,
        "can_finetune": False,
        "note": "Free tier on OpenRouter; an OpenRouter API key is required.",
    },
    {
        "id": "openai/gpt-4o-mini",
        "label": "GPT-4o mini (GitHub Models)",
        "provider": "GitHub Models",
        "location": "cloud",
        "base_url": "https://models.github.ai/inference",
        "access": "key",
        "free": False,
        "requires_key": True,
        "download_gb": None,
        "ram_gb": None,
        "can_finetune": False,
        "note": "Uses a GitHub token and GitHub Models quota.",
    },
    {
        "id": "gpt-4o-mini",
        "label": "GPT-4o mini (OpenAI)",
        "provider": "OpenAI",
        "location": "cloud",
        "base_url": "https://api.openai.com/v1",
        "access": "key",
        "free": False,
        "requires_key": True,
        "download_gb": None,
        "ram_gb": None,
        "can_finetune": False,
        "note": "Paid OpenAI API key required. Billing is handled by OpenAI.",
    },
    {
        "id": "qwen2.5-coder-3b-instruct-q4",
        "label": "Qwen2.5 Coder 3B (offline)",
        "provider": "Offline llama.cpp",
        "location": "local",
        "base_url": "http://127.0.0.1:11435/v1",
        "access": "free",
        "free": True,
        "requires_key": False,
        "download_gb": 1.96,
        "ram_gb": 4,
        "can_finetune": True,
        "note": "Small GGUF model downloaded online, then runs offline. No Ollama required.",
    },
)


def model_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in MODEL_CATALOG]


def runtime_home() -> Path:
    configured = os.environ.get("DEEPCODE_HOME") or os.environ.get("WALIACODE_HOME")
    root = Path(configured).expanduser() if configured else Path.home() / ".deepcode"
    if not root.is_absolute():
        root = Path.cwd() / root
    return root.resolve()


def ensure_runtime_layout() -> Path:
    root = runtime_home()
    root.mkdir(parents=True, exist_ok=True)
    for folder in RUNTIME_FOLDERS:
        (root / folder).mkdir(parents=True, exist_ok=True)
    return root


def runtime_status() -> dict[str, Any]:
    root = ensure_runtime_layout()
    return {
        "root": str(root),
        "folders": list(RUNTIME_FOLDERS),
        "models": "cloud models plus one optional 4 GB offline GGUF model; no Ollama required",
        "sandbox": "project-scoped approval sandbox",
        "training": "optional LoRA/QLoRA tools; no training is installed or run automatically",
        "ide": "optional integration directory; no IDE is installed automatically",
    }
