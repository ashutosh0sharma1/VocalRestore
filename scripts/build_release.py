"""Allowlisted source release; never includes jobs, recordings, plugins or weights."""

from pathlib import Path
import hashlib
import json
import zipfile
from verify_source import ROOT, verify


def main():
    files = verify()
    required = [
        "README.md",
        "LICENSE",
        "config.json",
        "restore.py",
        "worker.py",
        "web/index.html",
        "docs/models.md",
    ]
    for name in required:
        if not (ROOT / name).is_file():
            raise ValueError("Missing release file: " + name)
    version = json.loads((ROOT / "package.json").read_text())["version"]
    folder = ROOT / "dist"
    folder.mkdir(exist_ok=True)
    archive = folder / f"Restore-{version}-source.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as target:
        for p in files:
            target.write(p, Path(f"Restore-{version}") / p.relative_to(ROOT))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (folder / "SHA256SUMS.txt").write_text(
        f"{checksum}  {archive.name}\n", encoding="utf-8"
    )
    print(f"Built {archive.name}: {archive.stat().st_size:,} bytes, {len(files)} files")


if __name__ == "__main__":
    main()
