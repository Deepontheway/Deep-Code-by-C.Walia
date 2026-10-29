"""Language detection and optional toolchain guidance.

This catalog never executes installers. The UI can use it to explain what a
project needs and then create an approval request for a chosen setup recipe.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

LANGUAGES: tuple[dict[str, Any], ...] = (
    {"id": "python", "label": "Python", "files": (".py", ".pyi"), "tooling": ("Python", "venv or Conda", "pytest"), "ide": ("Spyder", "VS Code")},
    {"id": "typescript", "label": "TypeScript", "files": (".ts", ".tsx"), "tooling": ("Node.js", "npm or pnpm"), "ide": ("VS Code",)},
    {"id": "javascript", "label": "JavaScript", "files": (".js", ".jsx", ".mjs", ".cjs"), "tooling": ("Node.js", "npm or pnpm"), "ide": ("VS Code",)},
    {"id": "rust", "label": "Rust", "files": (".rs",), "tooling": ("Rust toolchain", "Cargo"), "ide": ("VS Code", "RustRover")},
    {"id": "cpp", "label": "C++", "files": (".cpp", ".cc", ".cxx", ".hpp", ".hxx"), "tooling": ("CMake", "C++ compiler"), "ide": ("Visual Studio", "CLion")},
    {"id": "c", "label": "C", "files": (".c", ".h"), "tooling": ("CMake", "C compiler"), "ide": ("Visual Studio", "CLion")},
    {"id": "java", "label": "Java", "files": (".java",), "tooling": ("JDK", "Maven or Gradle"), "ide": ("IntelliJ IDEA", "VS Code")},
    {"id": "csharp", "label": "C#", "files": (".cs",), "tooling": (".NET SDK",), "ide": ("Visual Studio", "Rider")},
    {"id": "go", "label": "Go", "files": (".go",), "tooling": ("Go toolchain",), "ide": ("VS Code", "GoLand")},
    {"id": "php", "label": "PHP", "files": (".php",), "tooling": ("PHP", "Composer"), "ide": ("PhpStorm", "VS Code")},
    {"id": "ruby", "label": "Ruby", "files": (".rb",), "tooling": ("Ruby", "Bundler"), "ide": ("RubyMine", "VS Code")},
    {"id": "kotlin", "label": "Kotlin", "files": (".kt", ".kts"), "tooling": ("JDK", "Gradle"), "ide": ("IntelliJ IDEA",)},
    {"id": "swift", "label": "Swift", "files": (".swift",), "tooling": ("Swift toolchain",), "ide": ("Xcode", "VS Code")},
    {"id": "dart", "label": "Dart / Flutter", "files": (".dart",), "tooling": ("Dart or Flutter SDK",), "ide": ("Android Studio", "VS Code")},
    {"id": "web", "label": "Web markup and styles", "files": (".html", ".css", ".scss", ".sass", ".mdx", ".astro"), "tooling": ("Node.js when the project uses a build tool",), "ide": ("VS Code",)},
    {"id": "data", "label": "Data / SQL", "files": (".sql", ".r", ".jl"), "tooling": ("Project-specific runtime",), "ide": ("Spyder", "VS Code")},
)


def catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in LANGUAGES]


def detect_project_languages(root: str | Path, limit: int = 500) -> list[dict[str, Any]]:
    base = Path(root)
    found: set[str] = set()
    suffixes = {suffix: item["id"] for item in LANGUAGES for suffix in item["files"]}
    try:
        candidates = base.rglob("*")
        for index, path in enumerate(candidates):
            if index >= limit:
                break
            if path.is_file() and path.suffix.lower() in suffixes:
                found.add(suffixes[path.suffix.lower()])
    except OSError:
        return []
    return [dict(item) for item in LANGUAGES if item["id"] in found]
