"""Isolated class-aware host for the existing Waves X-Click VST3 installation."""

from pathlib import Path
import json
import sys
import time

import numpy as np
import pedalboard
import psutil
import soundfile as sf


def run(request):
    start, cpu = time.perf_counter(), time.process_time()
    x, rate = sf.read(request["source"], dtype="float32", always_2d=True)
    channels = x.shape[1]
    if channels not in (1, 2) or not len(x) or not np.isfinite(x).all():
        raise ValueError("Finite mono or stereo WAV required")
    threshold, shape = float(request["threshold"]), float(request["shape"])
    if not 0 <= threshold <= 100 or not 0 <= shape <= 100:
        raise ValueError("X-Click settings must be in [0,100]")
    name = "X-Click Stereo" if channels == 2 else "X-Click Mono"
    effect = pedalboard.load_plugin(
        request["plugin_path"], plugin_name=name, initialization_timeout=5
    )
    effect.thresh = 0.0
    effect.shape = shape
    effect.monitor = "Audio "
    effect.bypass = False
    # Verify host compensation rather than cropping its already-compensated
    # output by the plugin's reported latency a second time.
    impulse = np.zeros((channels, rate * 3), np.float32)
    impulse[:, rate + rate // 2] = 0.2
    calibrated = effect(impulse, rate, buffer_size=512)
    lag = int(np.argmax(np.abs(calibrated[0])) - (rate + rate // 2))
    if (
        calibrated.shape != impulse.shape
        or lag != 0
        or np.max(np.abs(calibrated - impulse)) > 1e-6
    ):
        raise RuntimeError("X-Click host failed zero-repair timing/transparency check")
    effect.thresh = threshold
    padded = np.pad(x.T, ((0, 0), (rate, 2 * rate)))
    rendered = effect(padded, rate, buffer_size=512)
    y = rendered[:, rate : rate + len(x)].T
    if y.shape != x.shape or not np.isfinite(y).all():
        raise RuntimeError("Incomplete X-Click render")
    sf.write(request["output"], y, rate, subtype="FLOAT")
    memory = psutil.Process().memory_info()
    report = dict(
        engine="waves_xclick",
        host="Pedalboard isolated worker",
        plugin=name,
        plugin_path=request["plugin_path"],
        threshold=float(effect.thresh),
        shape=float(effect.shape),
        monitor=str(effect.monitor),
        reported_latency_samples=effect.reported_latency_samples,
        measured_host_lag_samples=lag,
        zero_repair_max_error=float(np.max(np.abs(calibrated - impulse))),
        changed_seconds=float(np.count_nonzero(np.any(x != y, axis=1)) / rate),
        wall_seconds=time.perf_counter() - start,
        cpu_core_seconds=time.process_time() - cpu,
        peak_process_bytes=getattr(memory, "peak_wset", memory.rss),
        frames=len(x),
        rate=rate,
        channels=channels,
    )
    Path(request["report"]).write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    run(json.load(sys.stdin))
