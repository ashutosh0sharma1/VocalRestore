"""Syntax and publication boundaries, without importing native audio runtimes."""

import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ["engine", "scripts", "tests", "web", ".github", "docs", "vendor/audiojs"]


def source_files():
    paths = [
        p
        for p in ROOT.iterdir()
        if p.is_file()
        and not p.name.startswith(".config")
        and p.name != "restore-launcher.json"
        and p.suffix in {".py", ".json", ".md", ".txt", ".cmd"}
    ]
    paths += [ROOT / "LICENSE", ROOT / ".gitignore", ROOT / ".gitattributes"]
    for name in FOLDERS:
        paths += [
            p
            for p in (ROOT / name).rglob("*")
            if p.is_file()
            and not set(p.relative_to(ROOT).parts) & {"node_modules", "__pycache__"}
        ]
    return sorted(set(paths))


def verify():
    files = source_files()
    for p in files:
        if p.suffix in {".png", ".jpg", ".svg"}:
            continue
        text = p.read_text(encoding="utf-8")
        if p.suffix == ".py":
            ast.parse(text, filename=str(p))
        if p.suffix == ".json":
            json.loads(text)
        # Keep recordings, credentials and machine-specific paths out of release sources.
        for pattern in [
            r"gh[pousr]_[A-Za-z0-9]{30,}",
            r"github_pat_[A-Za-z0-9_]{30,}",
            r"AIza[A-Za-z0-9_-]{30,}",
            r"C:[/\\]Users[/\\][A-Za-z0-9]",
        ]:
            if re.search(pattern, text):
                raise ValueError(f"Potential private material in {p.relative_to(ROOT)}")
    print(f"Checked {len(files)} source files; syntax and publication boundaries pass.")
    return files


if __name__ == "__main__":
    verify()
