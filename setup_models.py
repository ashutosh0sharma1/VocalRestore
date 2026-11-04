"""Download external weights explicitly; normal cleanup never downloads models."""

import hashlib
import json
from pathlib import Path
import shutil
import urllib.request
import settings

REVISION = "c6901b7500c78b8274a140d59a0ecbecc205959b"
RESPIRO_SHA = "3ccc55d4130b2465f8a7975178a30317d45babb7de5e7b3533fae1810c9b7138"


def main():
    from pymss.model_download import download_model

    config = settings.load()
    manifest = json.loads(
        (settings.ROOT / "docs/model-manifest.json").read_text(encoding="utf-8")
    )
    print(
        "Downloading external models. Their terms are separate from the app; see docs/models.md."
    )
    for spec in config["models"].values():
        print(spec["name"], flush=True)
        download_model(
            spec["name"],
            model_dir=config["model_dir"],
            source=config["source"],
            verify=True,
        )
        expected = next(
            (entry for entry in manifest if entry["name"] == spec["name"]), None
        )
        if expected:
            path = Path(config["model_dir"]) / expected["relative_path"]
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != expected["sha256"]:
                raise ValueError(
                    "Downloaded checkpoint differs from the tested release: "
                    + spec["name"]
                )
    destination = Path(config["respiro_model"])
    if (
        not destination.is_file()
        or hashlib.sha256(destination.read_bytes()).hexdigest() != RESPIRO_SHA
    ):
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".download")
        url = f"https://huggingface.co/pbTechLab/respiro-en-onnx/resolve/{REVISION}/respiro-en.onnx"
        with (
            urllib.request.urlopen(url, timeout=120) as response,
            temporary.open("wb") as output,
        ):
            shutil.copyfileobj(response, output)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != RESPIRO_SHA:
            raise ValueError(
                "Respiro checksum mismatch; original detector was not replaced"
            )
        temporary.replace(destination)
    for name in ["LICENSE", "README.md"]:
        url = f"https://huggingface.co/pbTechLab/respiro-en-onnx/resolve/{REVISION}/{name}"
        with urllib.request.urlopen(url, timeout=30) as response:
            (destination.parent / name).write_bytes(response.read())
    print("Model setup complete. Run python restore.py")


if __name__ == "__main__":
    main()
