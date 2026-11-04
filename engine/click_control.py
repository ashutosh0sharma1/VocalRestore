"""Temper automatic short-click repairs around periodic singing and word edges."""

import math
import numpy as np
from scipy.ndimage import binary_dilation, minimum_filter1d
from scipy.signal import resample_poly


def protect_click_repairs(
    source, repaired, rate, max_relative=0.20, strict_voiced=False
):
    source = np.asarray(source, dtype=np.float32)
    repaired = np.asarray(repaired, dtype=np.float32)
    if (
        source.ndim != 2
        or source.shape != repaired.shape
        or not source.shape[-1]
        or rate < 8000
    ):
        raise ValueError("Matching nonempty channel-first audio required")
    if (
        not np.isfinite(source).all()
        or not np.isfinite(repaired).all()
        or not np.isfinite(max_relative)
        or not 0.02 <= max_relative <= 1
    ):
        raise ValueError("Finite audio and repair limit in [.02,1] required")
    channel = int(np.argmax(np.mean(source.astype(np.float64) ** 2, axis=1)))
    divisor = math.gcd(int(rate), 16000)
    x = resample_poly(source[channel], 16000 // divisor, int(rate) // divisor)
    d = resample_poly(
        (source - repaired)[channel], 16000 // divisor, int(rate) // divisor
    )
    count = len(x) // 160 + 1

    def frames(a):
        return np.lib.stride_tricks.sliding_window_view(np.pad(a, (320, 640)), 640)[
            ::160
        ][:count]

    xf, df = frames(x), frames(d)
    rms = np.sqrt(np.mean(xf**2, axis=1))
    drms = np.sqrt(np.mean(df**2, axis=1))
    periodicity = np.zeros(count, np.float32)
    for begin in range(0, count, 512):
        block = xf[begin : begin + 512]
        spec = np.fft.rfft(
            (block - block.mean(axis=1, keepdims=True)) * np.hanning(640),
            n=2048,
            axis=1,
        )
        corr = np.fft.irfft(np.abs(spec) ** 2, n=2048, axis=1)
        periodicity[begin : begin + len(block)] = np.max(
            corr[:, 16:229], axis=1
        ) / np.maximum(corr[:, 0], 1e-12)
    protect = binary_dilation((periodicity > 0.55) & (rms > 1e-5), iterations=6)
    weights = np.ones(count, np.float32)
    if strict_voiced:
        weights[protect] = 0
    else:
        weights[protect] = np.minimum(
            1, max_relative * rms[protect] / np.maximum(drms[protect], 1e-12)
        )
    weights = minimum_filter1d(weights, size=5, mode="nearest")
    gain = np.interp(
        np.arange(source.shape[-1]) / rate, np.arange(count) / 100, weights
    ).astype(np.float32)
    result = source - (source - repaired) * gain[None]
    return result.astype(np.float32), dict(
        max_relative_repair=max_relative,
        strict_voiced=strict_voiced,
        tempered_frames=int(np.sum(weights < 0.999)),
        frame_hop_seconds=0.01,
        note="Relative RMS repair cap around periodic voice/60ms word edges; heuristic, not phoneme certification.",
    )
