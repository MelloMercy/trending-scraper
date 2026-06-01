#!/usr/bin/env python3
"""Preflight checks before publishing this project to a public repository.

The script intentionally reports only file paths and detector names. It does
not print matched secret values.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_GITIGNORE_LINES = [
    "config.json",
    "data/",
    ".env",
    ".env.*",
    "webui/node_modules/",
    "webui/*.tsbuildinfo",
    "static/assets/",
    "publish/latest*",
]

LOCAL_ONLY_PATHS = [
    "config.json",
    "data",
    ".env",
    ".env.local",
]

SECRET_PATTERNS = [
    ("openai_or_deepseek_key", re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_\-]{18,}\b")),
    ("bearer_token", re.compile(r"Authorization\s*:\s*Bearer\s+[A-Za-z0-9._\-]{16,}", re.IGNORECASE)),
    ("api_key_assignment", re.compile(r"\b(api[_-]?key|deepseek_api_key)\b\s*[:=]\s*[\"'][^\"']{8,}[\"']", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(app[_-]?secret|client[_-]?secret|secret[_-]?key)\b\s*[:=]\s*[\"'][^\"']{8,}[\"']", re.IGNORECASE)),
    ("token_assignment", re.compile(r"\b(access[_-]?token|refresh[_-]?token)\b\s*[:=]\s*[\"'][^\"']{12,}[\"']", re.IGNORECASE)),
]


def main() -> int:
    errors: list[str] = []
    notes: list[str] = []

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8") if (ROOT / ".gitignore").exists() else ""
    for line in REQUIRED_GITIGNORE_LINES:
        if line not in gitignore:
            errors.append(f".gitignore missing required rule: {line}")

    for rel in LOCAL_ONLY_PATHS:
        path = ROOT / rel
        if path.exists():
            notes.append(f"local-only present: {rel}")

    for path in iter_public_candidate_files():
        scan_file(path, errors)

    for note in notes:
        print(f"NOTE {note}")
    if errors:
        for err in errors:
            print(f"FAIL {err}")
        return 1
    print("OK public release audit passed")
    return 0


def iter_public_candidate_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if should_skip(rel):
            continue
        yield path


def should_skip(rel: Path) -> bool:
    parts = rel.parts
    name = rel.name
    rel_s = rel.as_posix()
    if any(part in {".git", ".venv", "__pycache__", "node_modules"} for part in parts):
        return True
    if parts and parts[0] == "data":
        return True
    if parts and parts[0] == "publish" and (name.startswith("latest") or _is_date_dir(parts[1] if len(parts) > 1 else "")):
        return True
    if rel_s.startswith("static/assets/") or rel_s == "static/index.html":
        return True
    if name.endswith((".pyc", ".db", ".db-shm", ".db-wal", ".sqlite", ".sqlite3", ".log", ".tsbuildinfo")):
        return True
    if name in {"config.json"} or name.startswith(".env"):
        return True
    if name.endswith(".trace.zip"):
        return True
    return False


def scan_file(path: Path, errors: list[str]) -> None:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        errors.append(f"{path.relative_to(ROOT)}: unreadable: {exc}")
        return
    if b"\0" in raw[:4096]:
        return
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return
    rel = path.relative_to(ROOT)
    for line_no, line in enumerate(text.splitlines(), 1):
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                errors.append(f"{rel}:{line_no}: matched {name}")


def _is_date_dir(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))


if __name__ == "__main__":
    raise SystemExit(main())
