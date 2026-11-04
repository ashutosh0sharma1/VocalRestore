"""Resumable delivery of the approved V3 cleanup chain, from an original file."""

from pathlib import Path
import argparse
import hashlib
import json
import logging
import shutil
import subprocess
import sys
import time

import numpy as np
import psutil
import soundfile as sf
import vocal_restore as vr
from isolated_breath import run_breath_stage
from file_io import atomic_json


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def metrics(path):
    result = subprocess.run(
        [
            shutil.which("ffmpeg"),
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            "loudnorm=I=-18:TP=-1:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return json.loads(
        result.stderr[result.stderr.rfind("{") : result.stderr.rfind("}") + 1]
    )


def export_delivery(source, output):
    """V3 constant gain export: at most +3dB, at most -1dBTP, PCM24."""
    audio, rate = vr.load_audio(Path(source))
    measured = metrics(source)
    loudness, peak = float(measured["input_i"]), float(measured["input_tp"])
    if np.isfinite(loudness) and np.isfinite(peak):
        gain = min(3.0, -18.0 - loudness, -1.0 - peak)
    else:
        gain = 0.0  # Digital silence must not receive an infinite gain.
    output = Path(output)
    sf.write(output, (audio * 10 ** (gain / 20)).T, rate, subtype="PCM_24")
    after = metrics(output)
    # Roundoff at quantized export may differ by a few hundredths of a dB.
    if float(after["input_tp"]) > -0.95:
        raise ValueError("True peak exceeds delivery limit")
    return dict(gain_db=gain, metrics=after, sha256=digest(output))


def deliver(source, output, config=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if config is None:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from settings import load

        config = load()
    config["studio_finish"]["enabled"] = True
    source_sha = digest(source)
    signature = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    receipt_path = output / "receipt.json"
    info = sf.info(source)
    receipt = dict(
        source=str(source),
        source_sha256=source_sha,
        config_sha256=signature,
        rate=info.samplerate,
        channels=info.channels,
        frames=info.frames,
        duration_seconds=info.duration,
        stages=[],
        status="running",
        gemini_requests=0,
        additional_api_cost_usd=0,
        manual_cuts=0,
        pitch_correction=False,
    )
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (
            receipt["source_sha256"] != source_sha
            or receipt["config_sha256"] != signature
        ):
            raise ValueError("Existing delivery belongs to a different source/config")
    (output / "delivery-config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )

    def persist():
        atomic_json(receipt_path, receipt)

    def stage(name, fn):
        path = output / (name + ".wav")
        prior = next((s for s in receipt["stages"] if s["stage"] == name), None)
        if prior:
            if not path.is_file() or digest(path) != prior["sha256"]:
                raise ValueError(f"Checkpoint altered or missing: {name}")
            print("REUSE", name, flush=True)
            return path
        receipt["current_stage"] = name
        persist()
        start, cpu = time.perf_counter(), time.process_time()
        print("START", name, flush=True)
        fn(path)
        a, rate = vr.load_audio(path)
        if (
            rate != info.samplerate
            or a.shape != (info.channels, info.frames)
            or not np.isfinite(a).all()
        ):
            raise ValueError(f"Invalid audio format/length/data after {name}")
        m = psutil.Process().memory_info()
        row = dict(
            stage=name,
            wall_seconds=time.perf_counter() - start,
            cpu_core_seconds=time.process_time() - cpu,
            peak_process_bytes=getattr(m, "peak_wset", m.rss),
            sha256=digest(path),
        )
        if name == "03-breaths" and path.with_suffix(".breaths.json").is_file():
            report = json.loads(
                path.with_suffix(".breaths.json").read_text(encoding="utf-8")
            )
            worker = report.get("separator_worker", {})
            row["worker"] = worker
            row["cpu_core_seconds"] += worker.get("cpu_core_seconds", 0)
            row["peak_process_bytes"] = max(
                row["peak_process_bytes"], worker.get("peak_process_bytes", 0)
            )
        if name == "04-mouth" and path.with_suffix(".clicks.json").is_file():
            worker = (
                json.loads(
                    path.with_suffix(".clicks.json").read_text(encoding="utf-8")
                ).get("click_repair")
                or {}
            )
            row["cpu_core_seconds"] += worker.get("cpu_core_seconds", 0)
            row["peak_process_bytes"] = max(
                row["peak_process_bytes"], worker.get("peak_process_bytes", 0)
            )
        receipt["stages"].append(row)
        persist()
        print("DONE", json.dumps(row), flush=True)
        return path

    params = config["runtime"]["inference_params"]
    model_args = dict(
        model_dir=vr.PROJECT_ROOT / config["model_dir"],
        device="cpu",
        source=config["source"],
        inference_params=params,
        download=False,
    )
    current = source
    for name, key in [("01-denoise", "denoise_safe"), ("02-dereverb", "dereverb_safe")]:
        spec = config["models"][key]
        before = current
        current = stage(
            name,
            lambda p: vr.run_model_stage(
                before,
                p,
                model_name=spec["name"],
                output_stem=spec["output_stem"],
                **model_args,
            ),
        )
    before = current
    spec = config["models"]["aspiration_strong"]
    current = stage(
        "03-breaths",
        lambda p: run_breath_stage(
            before,
            p,
            model_name=spec["name"],
            output_stem=spec["output_stem"],
            **model_args,
            breath_params=config["breath_control"],
            removed_output_path=output / "03-breaths-removed.wav",
        ),
    )
    before = current
    current = stage(
        "04-mouth", lambda p: vr.run_declick(before, p, config["dsp"]["declick"])
    )
    before = current
    current = stage(
        "05-finish", lambda p: vr.run_studio_finish(before, p, config["studio_finish"])
    )
    before = current
    final = stage("cleaned", lambda p: export_delivery(before, p))
    mp3 = output / "cleaned.mp3"
    subprocess.run(
        [
            shutil.which("ffmpeg"),
            "-v",
            "error",
            "-y",
            "-i",
            str(final),
            "-c:a",
            "libmp3lame",
            "-b:a",
            "320k",
            str(mp3),
        ],
        check=True,
    )
    subprocess.run(
        [shutil.which("ffmpeg"), "-v", "error", "-i", str(mp3), "-f", "null", "-"],
        check=True,
    )
    if digest(source) != source_sha:
        raise ValueError("Original file changed")
    receipt.update(
        status="complete",
        final_wav=str(final),
        final_mp3=str(mp3),
        output_metrics=metrics(final),
        original_unchanged=True,
        total_stage_wall_seconds=sum(s["wall_seconds"] for s in receipt["stages"]),
        total_cpu_core_seconds=sum(s["cpu_core_seconds"] for s in receipt["stages"]),
    )
    persist()
    print("COMPLETE", str(final), flush=True)
    return final


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    deliver(args.source, args.output)
