#!/usr/bin/env python3
"""Repository safety checks that need no camera, cloud account, or secrets."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"aws_secret_access_key\s*=", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"),
)
FORBIDDEN_TRACKED_SUFFIXES = {".avi", ".db", ".jpeg", ".jpg", ".mjpg", ".mp4", ".onnx", ".png", ".pt", ".sqlite3", ".tflite"}
MARKDOWN_LINK = re.compile(r"\[[^]]*\]\(([^)]+)\)")


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    )
    return [ROOT / part.decode() for part in result.stdout.split(b"\0") if part]


def check_tracked_artifacts(files: list[Path]) -> None:
    prohibited = [path.relative_to(ROOT) for path in files if path.suffix.lower() in FORBIDDEN_TRACKED_SUFFIXES]
    if prohibited:
        fail(f"large/runtime artifacts must not be committed: {', '.join(map(str, prohibited))}")


def check_text_for_secrets(files: list[Path]) -> None:
    for path in files:
        if path.suffix.lower() not in {".md", ".py", ".service", ".txt", ".yml", ".yaml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                fail(f"possible secret pattern in {path.relative_to(ROOT)}")


def check_python_syntax(files: list[Path]) -> None:
    for path in files:
        if path.suffix == ".py":
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as error:
                fail(f"Python syntax error in {path.relative_to(ROOT)}:{error.lineno}: {error.msg}")


def check_markdown_links(files: list[Path]) -> None:
    for path in files:
        if path.suffix.lower() != ".md":
            continue
        for destination in MARKDOWN_LINK.findall(path.read_text(encoding="utf-8")):
            destination = destination.split("#", 1)[0]
            if not destination or "://" in destination or destination.startswith(("mailto:", "/")):
                continue
            target = (path.parent / destination).resolve()
            if not target.exists() or not target.is_relative_to(ROOT):
                fail(f"broken local Markdown link in {path.relative_to(ROOT)}: {destination}")


def main() -> None:
    files = tracked_files()
    check_tracked_artifacts(files)
    check_text_for_secrets(files)
    check_python_syntax(files)
    check_markdown_links(files)
    print(f"OK: verified {len(files)} tracked files")


if __name__ == "__main__":
    main()
