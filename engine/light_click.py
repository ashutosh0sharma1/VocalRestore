"""Optional pinned MIT AudioJS AR repair; never a silent fallback for Waves."""

from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import numpy as np


def repair_clicks(audio, rate, params=None):
    params = params or {}
    threshold = float(params.get("light_threshold", 8))
    source = np.asarray(audio, dtype=np.float32)
    if (
        source.ndim != 2
        or source.shape[0] not in (1, 2)
        or not source.shape[1]
        or not np.isfinite(source).all()
    ):
        raise ValueError("Finite mono/stereo channel-first audio required")
    if not 3 <= threshold <= 20 or not 8000 <= rate <= 192000:
        raise ValueError("Invalid lightweight click settings")
    node = shutil.which("node")
    adapter = Path(__file__).resolve().parent.parent / "vendor/audiojs/process.mjs"
    if not node:
        raise RuntimeError("AudioJS requires Node.js; see setup instructions")
    with tempfile.TemporaryDirectory(prefix="restore_click_") as temp:
        before, after = Path(temp) / "in.f32", Path(temp) / "out.f32"
        source.T.astype("<f4").tofile(before)
        proc = subprocess.run(
            [
                node,
                str(adapter),
                str(before),
                str(after),
                str(rate),
                str(source.shape[0]),
                str(threshold),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(120, source.shape[1] / rate * 5),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode:
            raise RuntimeError("AudioJS repair failed: " + proc.stderr[-1000:])
        result = np.fromfile(after, dtype="<f4")
        if result.size != source.size or not np.isfinite(result).all():
            raise RuntimeError("Invalid AudioJS output")
        report = json.loads(proc.stdout)
        return result.reshape(-1, source.shape[0]).T, report
