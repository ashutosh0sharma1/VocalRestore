"""A fresh process per recording: decode, restore, verify, export."""

from pathlib import Path
import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "engine"))
from file_io import atomic_json


def decode(source, destination):
    import numpy as np
    import soundfile as sf

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise ValueError("FFmpeg and ffprobe must be installed and on PATH.")
    demuxer = {
        ".wav": "wav",
        ".mp3": "mp3",
        ".flac": "flac",
        ".m4a": "mov",
        ".ogg": "ogg",
        ".aif": "aiff",
        ".aiff": "aiff",
    }[source.suffix.lower()]
    input_options = ["-protocol_whitelist", "file,pipe", "-f", demuxer]
    probe = subprocess.run(
        [
            shutil.which("ffprobe"),
            "-v",
            "error",
            *input_options,
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=channels,sample_rate:format=duration",
            "-of",
            "json",
            str(source),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=True,
    )
    metadata = json.loads(probe.stdout)
    streams = metadata.get("streams", [])
    if not streams or streams[0].get("channels") not in (1, 2):
        raise ValueError("Please choose a mono or stereo audio recording.")
    rate = int(streams[0].get("sample_rate", 0))
    if not 16000 <= rate <= 96000:
        raise ValueError("Supported sample rates are 16 kHz to 96 kHz.")
    if float(metadata.get("format", {}).get("duration", 0)) > 1800:
        raise ValueError("Please use a recording shorter than 30 minutes.")
    temporary = destination.with_name("decoded.part.wav")
    subprocess.run(
        [
            shutil.which("ffmpeg"),
            "-nostdin",
            "-v",
            "error",
            "-y",
            *input_options,
            "-i",
            str(source),
            "-map",
            "0:a:0",
            "-vn",
            "-map_metadata",
            "-1",
            "-t",
            "1801",
            "-c:a",
            "pcm_f32le",
            str(temporary),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=True,
    )
    info = sf.info(temporary)
    if not 1 <= info.duration <= 1800 or info.channels not in (1, 2):
        raise ValueError(
            "Choose a mono/stereo recording between 1 second and 30 minutes."
        )
    with sf.SoundFile(temporary) as handle:
        for block in handle.blocks(65536, dtype="float32", always_2d=True):
            if not np.isfinite(block).all():
                raise ValueError("The recording contains invalid audio samples.")
    temporary.replace(destination)
    return dict(
        duration_seconds=info.duration,
        rate=info.samplerate,
        channels=info.channels,
        frames=info.frames,
    )


def run(job):
    job = Path(job).resolve()
    state_path = job / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    started = time.perf_counter()
    stop_guard = threading.Event()
    if os.environ.get("RESTORE_PARENT_PID"):
        threading.Thread(
            target=guard_parent, args=(job, stop_guard), daemon=True
        ).start()
    try:
        state.update(status="running", message="Preparing your recording")
        atomic_json(state_path, state)
        config = json.loads((job / "config.json").read_text(encoding="utf-8"))
        original = job / "original.wav"
        if not original.is_file():
            state.update(decode(job / ("upload" + state["extension"]), original))
            atomic_json(state_path, state)
        from approved_delivery import deliver

        deliver(original, job / "result", config)
        state.update(
            status="complete",
            message="Your cleaned vocal is ready.",
            elapsed_seconds=time.perf_counter() - started,
        )
        atomic_json(state_path, state)
        return 0
    except Exception as exc:
        logging.exception("Restoration failed")
        # Full diagnostics remain in the local log; HTTP never returns a stack trace.
        message = (
            str(exc)
            if isinstance(exc, ValueError)
            else "Processing stopped. See this job’s worker.log for details; completed stages are saved."
        )
        state.update(
            status="failed",
            message=message[:500],
            elapsed_seconds=time.perf_counter() - started,
        )
        atomic_json(state_path, state)
        return 1
    finally:
        stop_guard.set()


def guard_parent(job, stop):
    """An abruptly closed launcher must not leave model workers running."""
    import psutil

    pid = int(os.environ["RESTORE_PARENT_PID"])
    created = float(os.environ["RESTORE_PARENT_CREATED"])
    while not stop.wait(2):
        try:
            if psutil.Process(pid).create_time() == created:
                continue
        except psutil.NoSuchProcess:
            pass
        owned = psutil.Process().children(recursive=True)
        for process in reversed(owned):
            try:
                process.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(owned, timeout=3)
        for process in alive:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass
        state = json.loads((job / "state.json").read_text(encoding="utf-8"))
        state.update(
            status="interrupted",
            message="Restore was closed. Resume to reuse verified stages.",
        )
        atomic_json(job / "state.json", state)
        os._exit(130)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(run(args.job))
