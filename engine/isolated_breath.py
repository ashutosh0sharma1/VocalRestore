"""Keep PyMSS/PyTorch inference separate from ONNX and native VST hosting."""

from pathlib import Path
import json
import os
import subprocess
import sys
import time

import numpy as np
import psutil
import soundfile as sf
import vocal_restore as vr


def file_hash(path):
    import hashlib

    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def model_worker(request):
    start, cpu = time.perf_counter(), time.process_time()
    source, raw, aspiration = [
        Path(request[k]) for k in ["source", "raw", "aspiration"]
    ]
    args = request["model_kwargs"]
    args["model_dir"] = Path(args["model_dir"])
    captured = vr.run_model_stage(source, raw, removed_output_path=aspiration, **args)
    if captured is None:
        x, rate = vr.load_audio(source)
        y, _ = vr.load_audio(raw)
        vr.save_audio(aspiration, x - y, rate)
    original = sf.info(source)
    hashes = {}
    for path in [raw, aspiration]:
        info = sf.info(path)
        if (info.frames, info.channels, info.samplerate) != (
            original.frames,
            original.channels,
            original.samplerate,
        ):
            raise ValueError("Separator cache format mismatch")
        with sf.SoundFile(path) as handle:
            for block in handle.blocks(
                blocksize=65536, dtype="float32", always_2d=True
            ):
                if not np.isfinite(block).all():
                    raise ValueError("Non-finite separator cache")
        hashes[path.name] = file_hash(path)
    memory = psutil.Process().memory_info()
    result = dict(
        signature=request["signature"],
        hashes=hashes,
        wall_seconds=time.perf_counter() - start,
        cpu_core_seconds=time.process_time() - cpu,
        peak_process_bytes=getattr(memory, "peak_wset", memory.rss),
        cpu_threads=args["inference_params"]["cpu_threads"],
    )
    Path(request["receipt"]).write_text(json.dumps(result, indent=2), encoding="utf-8")


def run_breath_stage(
    input_path, output_path, *, breath_params, removed_output_path=None, **model_kwargs
):
    """Same automatic algorithm, with a persistent isolated aspiration cache."""
    if breath_params.get("mode", "automatic") != "automatic":
        raise ValueError("Only the automatic breath workflow is supported")
    input_path, output_path = Path(input_path), Path(output_path)
    cache = output_path.parent / "aspiration-cache"
    cache.mkdir(parents=True, exist_ok=True)
    args = dict(model_kwargs)
    args["model_dir"] = str(args["model_dir"])
    args["inference_params"] = dict(args.get("inference_params") or {})
    args["inference_params"]["cpu_threads"] = 8
    signature = dict(source_sha256=file_hash(input_path), model_kwargs=args)
    raw, aspiration = cache / "raw.wav", cache / "aspiration.wav"
    receipt_path = cache / "worker.json"
    valid = False
    if receipt_path.is_file() and raw.is_file() and aspiration.is_file():
        worker = json.loads(receipt_path.read_text(encoding="utf-8"))
        valid = worker.get("signature") == signature and all(
            file_hash(p) == worker["hashes"].get(p.name) for p in [raw, aspiration]
        )
    if not valid:
        request = dict(
            source=str(input_path.resolve()),
            raw=str(raw.resolve()),
            aspiration=str(aspiration.resolve()),
            receipt=str(receipt_path.resolve()),
            signature=signature,
            model_kwargs=args,
        )
        env = dict(
            os.environ,
            PYTHONIOENCODING="utf-8",
            PYTHONUTF8="1",
            PYTHONFAULTHANDLER="1",
            OMP_NUM_THREADS="8",
            MKL_NUM_THREADS="8",
        )
        with (cache / "worker.log").open("w", encoding="utf-8") as log:
            child = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--model-worker"],
                input=json.dumps(request),
                text=True,
                encoding="utf-8",
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        if child.returncode != 0:
            raise vr.PipelineError(
                f"Isolated aspiration worker exited {child.returncode}; see {cache / 'worker.log'}"
            )
        worker = json.loads(receipt_path.read_text(encoding="utf-8"))
    else:
        print("REUSE isolated aspiration cache", flush=True)
    # No VST or ONNX library is loaded until the PyTorch worker has exited.
    from breath_control import automatic_breaths
    from respiro_detector import breath_probabilities
    from audio_plugins import nectar_breaths

    audio, rate = vr.load_audio(input_path)
    estimated, _ = vr.load_audio(aspiration)
    probabilities = breath_probabilities(
        audio, rate, checkpoint=breath_params.get("respiro_model")
    )
    nectar_audio = nectar_report = None
    if breath_params.get("nectar_enabled", True):
        nectar_audio, nectar_report = nectar_breaths(audio, rate, breath_params)
    result, _, report = automatic_breaths(
        audio, estimated, rate, probabilities, breath_params, nectar_audio=nectar_audio
    )
    report.update(
        nectar=nectar_report,
        separator=model_kwargs.get("model_name"),
        detector="Respiro-en ONNX CPU",
        separator_worker=worker,
        native_isolation="PyMSS child completes before ONNX/VST loading",
    )
    vr.save_audio(output_path, result, rate)
    output_path.with_suffix(".breaths.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    if removed_output_path is not None:
        vr.save_audio(removed_output_path, audio - result, rate)
        return removed_output_path
    return None


if __name__ == "__main__":
    if sys.argv[1:] != ["--model-worker"]:
        raise SystemExit("This worker is called by the restoration workflow")
    model_worker(json.load(sys.stdin))
