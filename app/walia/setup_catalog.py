"""User-approved setup recipes for components installed inside DeepCode home."""
from __future__ import annotations

SETUP_COMPONENTS = (
    {
        "id": "local-runtime",
        "label": "Local model runtime",
        "installs_to": "runtime/",
        "required_for_full_workstation": True,
        "requires_confirmation": True,
        "note": "Downloads are not started automatically.",
    },
    {
        "id": "training-env",
        "label": "LoRA / QLoRA environment",
        "installs_to": "env/",
        "requires_confirmation": True,
        "note": "Training requires a compatible base model and enough GPU memory.",
    },
    {
        "id": "sandbox",
        "label": "Project execution sandbox",
        "installs_to": "sandbox/",
        "requires_confirmation": True,
        "note": "A real OS sandbox depends on the host platform and is never silently enabled.",
    },
    {
        "id": "ide-integration",
        "label": "Optional IDE integration",
        "installs_to": "ide/",
        "requires_confirmation": True,
        "note": "DeepCode does not install a system IDE without approval.",
    },
    {
        "id": "developer-workstation",
        "label": "Git, Windows Terminal, Spyder, VS Code, and Docker Desktop",
        "installs_to": "system applications",
        "required_for_full_workstation": True,
        "requires_confirmation": True,
        "note": "These are system-level applications and cannot be installed inside the DeepCode data folder.",
    },
)
