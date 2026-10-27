from __future__ import annotations

import re
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "skills"
MAX_SKILL_BYTES = 200_000

_BUILTIN = {
    "openmanus": {
        "name": "OpenManus reference",
        "description": "Reference notes on the OpenManus open-source agent project and how its tool loop is structured.",
        "content": (
            "# OpenManus reference\n\n"
            "OpenManus is an open-source general-purpose agent project. It typically combines a language model with\n"
            "a small set of tools (browser automation, shell, file editing, planning) and runs a loop where the model\n"
            "chooses tools until a task is complete.\n\n"
            "This is reference documentation bundled with WaliaCode. It is not an installed runtime and it does not\n"
            "grant any tools or permissions. WaliaCode only performs file writes, commands, and network fetches after\n"
            "you explicitly approve the exact action.\n"
        ),
    },
    "rea": {
        "name": "REA reference",
        "description": "Reference notes on the REA (Reasoning and Execution Agent) pattern.",
        "content": (
            "# REA reference\n\n"
            "REA (Reasoning and Execution Agent) is a pattern that separates planning/reasoning steps from concrete\n"
            "execution steps. A planner decides what to do, an executor performs one bounded action, and the result is\n"
            "fed back into the next reasoning step.\n\n"
            "This is reference documentation bundled with WaliaCode. It is not a live authenticated connection and it\n"
            "cannot override WaliaCode's approval rules.\n"
        ),
    },
}

_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _extra_skills() -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    if not SKILLS_DIR.is_dir():
        return found
    for path in sorted(SKILLS_DIR.glob("*.md")):
        skill_id = path.stem.lower()
        if not _SAFE_ID.match(skill_id):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        first_line = next((line.strip("# ").strip() for line in text.splitlines() if line.strip()), skill_id)
        found[skill_id] = {
            "name": first_line[:120],
            "description": f"Local reference skill from {path.name}.",
            "content": text[:MAX_SKILL_BYTES],
        }
    return found


def _all_skills() -> dict[str, dict[str, str]]:
    merged = {key: dict(value) for key, value in _BUILTIN.items()}
    for key, value in _extra_skills().items():
        merged.setdefault(key, value)
    return merged


def list_skills() -> list[dict[str, str]]:
    return [
        {
            "id": skill_id,
            "name": skill["name"],
            "description": skill["description"],
            "source": "bundled" if skill_id in _BUILTIN else "local",
        }
        for skill_id, skill in sorted(_all_skills().items())
    ]


def read_skill(skill_id: str) -> str:
    key = str(skill_id or "").strip().lower()
    if not _SAFE_ID.match(key):
        raise ValueError("Skill ids may only contain letters, numbers, hyphens, and underscores.")
    skill = _all_skills().get(key)
    if skill is None:
        raise ValueError(f"Unknown skill: {key}")
    return skill["content"]
