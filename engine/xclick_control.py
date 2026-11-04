"""Click reconstruction without the broad voiced-phrase attenuation veto."""

from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import soundfile as sf

PLUGIN = Path(r"C:\Program Files\Common Files\VST3\WaveShell1-VST3 15.5_x64.vst3")


def repair_clicks(audio, rate, params=None):
    params = dict(params or {})
    source = np.asarray(audio, np.float32)
    if (
        source.ndim != 2
        or source.shape[0] not in (1, 2)
        or not source.shape[-1]
        or not np.isfinite(source).all()
    ):
        raise ValueError("Finite channel-first mono/stereo audio required")
    threshold, shape = (
        float(params.get("threshold", 50)),
        float(params.get("shape", 60)),
    )
    if (
        not np.isfinite(threshold)
        or not np.isfinite(shape)
        or not 0 <= threshold <= 100
        or not 0 <= shape <= 100
    ):
        raise ValueError("X-Click threshold and shape must be in [0,100]")
    plugin = Path(params.get("plugin_path", PLUGIN))
    if not plugin.exists():
        raise ValueError(f"Required installed X-Click plugin missing: {plugin}")
    with tempfile.TemporaryDirectory(prefix="vocal_xclick_") as folder:
        folder = Path(folder)
        before, after, report_path = (
            folder / "source.wav",
            folder / "repaired.wav",
            folder / "report.json",
        )
        sf.write(before, source.T, rate, subtype="FLOAT")
        request = dict(
            source=str(before),
            output=str(after),
            report=str(report_path),
            plugin_path=str(plugin),
            threshold=threshold,
            shape=shape,
        )
        env = dict(
            os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONFAULTHANDLER="1"
        )
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("xclick_worker.py"))],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raise RuntimeError(
                f"X-Click worker failed ({result.returncode}): " + result.stderr[-1500:]
            )
        fixed, out_rate = sf.read(after, dtype="float32", always_2d=True)
        if (
            out_rate != rate
            or fixed.T.shape != source.shape
            or not np.isfinite(fixed).all()
        ):
            raise RuntimeError("X-Click changed source format or duration")
        report = json.loads(report_path.read_text(encoding="utf-8"))
    return fixed.T, report
