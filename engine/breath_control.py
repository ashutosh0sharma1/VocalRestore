"""Use a separator as a breath detector while protecting nearby sung phonemes.

The input waveform is unchanged outside detected breath regions. This is a
conservative heuristic, not a guarantee that an unvoiced sound is an inhale.
"""

from __future__ import annotations

import math
import numpy as np
from scipy.ndimage import binary_closing, binary_dilation, uniform_filter1d
from scipy.signal import resample_poly


def automatic_breaths(
    audio, aspiration, rate, probabilities, params=None, nectar_audio=None
):
    """Combine independent learned breath detection with the aspiration stem.

    No recording timestamps or lyric assumptions. The original waveform is used
    throughout; no separator reconstruction is substituted for sung vowels.
    """
    params = dict(params or {})
    reduction = float(params.get("reduction_db", 80))
    threshold = float(params.get("detector_threshold", 0.5))
    edge_ms = float(params.get("protection_ms", 30))
    extension_ms = float(params.get("boundary_extension_ms", 60))
    gain_power = float(params.get("nectar_gain_power", 3))
    for name, value, lo, hi in [
        ("reduction_db", reduction, 0, 80),
        ("detector_threshold", threshold, 0.1, 0.95),
        ("protection_ms", edge_ms, 10, 300),
        ("boundary_extension_ms", extension_ms, 0, 150),
        ("nectar_gain_power", gain_power, 1, 6),
    ]:
        if not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f"{name} must be between {lo} and {hi}")
    audio = np.asarray(audio, dtype=np.float32)
    aspiration = np.asarray(aspiration, dtype=np.float32)
    probabilities = np.asarray(probabilities, dtype=np.float32)
    if (
        audio.ndim != 2
        or audio.shape != aspiration.shape
        or not audio.shape[-1]
        or rate < 8000
    ):
        raise ValueError("Matching nonempty channel-first audio at >=8kHz required")
    if not np.isfinite(audio).all() or not np.isfinite(aspiration).all():
        raise ValueError("Audio must be finite")
    if (
        probabilities.ndim != 1
        or not len(probabilities)
        or not np.isfinite(probabilities).all()
        or np.min(probabilities) < 0
        or np.max(probabilities) > 1
    ):
        raise ValueError("Finite detector probabilities in [0,1] required")
    channel = int(np.argmax(np.mean(audio.astype(np.float64) ** 2, axis=1)))
    divisor = math.gcd(int(rate), 16000)
    source = resample_poly(audio[channel], 16000 // divisor, int(rate) // divisor)
    breath = resample_poly(aspiration[channel], 16000 // divisor, int(rate) // divisor)
    count = len(source) // 160 + 1
    if abs(len(probabilities) - count) > 1:
        raise ValueError("Detector frame count does not match audio")
    probability = np.interp(
        np.arange(count), np.arange(len(probabilities)), probabilities
    )

    def frames(x):
        return np.lib.stride_tricks.sliding_window_view(np.pad(x, (320, 640)), 640)[
            ::160
        ][:count]

    signal, estimated = frames(source), frames(breath)
    rms = np.sqrt(np.mean(signal**2, axis=1))
    ratio = np.sqrt(np.mean(estimated**2, axis=1)) / np.maximum(rms, 1e-8)
    periodicity = np.zeros(count, np.float32)
    for start in range(0, count, 512):
        block = signal[start : start + 512]
        centered = block - block.mean(axis=1, keepdims=True)
        spectrum = np.fft.rfft(centered * np.hanning(640), n=2048, axis=1)
        corr = np.fft.irfft(np.abs(spectrum) ** 2, n=2048, axis=1)
        periodicity[start : start + len(block)] = np.max(
            corr[:, 16:229], axis=1
        ) / np.maximum(corr[:, 0], 1e-12)
    retained_rms = np.sqrt(np.mean((signal - estimated) ** 2, axis=1))
    retained_ratio = retained_rms / np.maximum(rms, 1e-8)
    # A resonant inhale can itself be periodic. Veto voiced material retained by
    # the singing separator; do not mistake every colored inhale for a vowel.
    # A low speech-detector score alone must not turn an aspiration-dominant
    # resonant inhale into protected singing. Retained voice still vetoes it.
    voiced = (
        (periodicity > 0.65)
        & (rms > 1e-5)
        & ((retained_ratio > 0.30) | (probability < 0.15))
    )
    voiced |= (periodicity > 0.85) & (rms > 1e-5) & (probability < threshold)
    protected = binary_dilation(voiced, iterations=max(1, math.ceil(edge_ms / 10)))
    low = (probability >= 0.03) & (ratio >= 0.5) & (rms > 3e-5) & ~protected
    low = binary_closing(low, iterations=2) & ~protected
    seeds = (probability >= threshold) & (ratio >= 0.6) & ~protected
    # The language-independent singing separator can corroborate lower-probability
    # speech-detector results, but requires a strongly unpitched signal.
    seeds |= (probability >= 0.15) & (ratio >= 0.9) & (periodicity < 0.45) & ~protected
    if nectar_audio is not None:
        nectar_audio = np.asarray(nectar_audio, dtype=np.float32)
        if nectar_audio.shape != audio.shape or not np.isfinite(nectar_audio).all():
            raise ValueError("Nectar detector output must match source audio")
        nectar = resample_poly(
            nectar_audio[channel], 16000 // divisor, int(rate) // divisor
        )
        nectar_ratio = np.sqrt(np.mean(frames(nectar) ** 2, axis=1)) / np.maximum(
            rms, 1e-8
        )
        endorsed = (
            (nectar_ratio < 0.5)
            & (ratio >= 0.8)
            & (periodicity < 0.65)
            & (rms > 3e-5)
            & ~protected
        )
        seeds |= endorsed
        low |= endorsed
    low |= seeds
    edges = np.diff(np.r_[False, low, False].astype(np.int8))
    mask = np.zeros(audio.shape[-1], np.float32)
    events = []
    core_events = []
    for begin, end in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        minimum_frames = 4 if params.get("continuous_gain", False) else 8
        if (
            end - begin < minimum_frames
            or end - begin > 150
            or np.count_nonzero(seeds[begin:end]) < 2
        ):
            continue
        # Grow only an already corroborated breath. Low-probability tails are
        # common in a speech detector applied to singing. Never grow across the
        # retained-voice guard or a louder consonant, or seed new events here.
        core_begin, core_end = begin, end
        reach = math.ceil(extension_ms / 10)
        ceiling = max(float(np.max(rms[begin:end])) * 1.5, 3e-5)
        support = (ratio >= 0.65) & (rms <= ceiling) & ~protected
        if nectar_audio is not None:
            support &= (probability >= 0.005) | (nectar_ratio < 0.8) | (rms < 1e-5)
        else:
            support &= (probability >= 0.005) | (rms < 1e-5)
        while begin > max(0, core_begin - reach) and support[begin - 1]:
            begin -= 1
        while end < min(count, core_end + reach) and support[end]:
            end += 1
        left = int(begin * rate / 100)
        right = min(audio.shape[-1], int(end * rate / 100))
        if right <= left:
            continue
        envelope = np.ones(right - left, np.float32)
        fade = min(round(rate * 0.005), len(envelope) // 2)
        if fade:
            envelope[:fade] = np.linspace(0, 1, fade)
            envelope[-fade:] = np.linspace(1, 0, fade)
        mask[left:right] = np.maximum(mask[left:right], envelope)
        events.append(
            dict(
                start_seconds=round(left / rate, 4),
                end_seconds=round(right / rate, 4),
                mean_detector_probability=round(
                    float(probability[begin:end].mean()), 3
                ),
                mean_model_ratio=round(float(ratio[begin:end].mean()), 3),
            )
        )
    strategy = "consensus_regions"
    if params.get("continuous_gain", False) and nectar_audio is not None:
        # Follow the dedicated model's full gain envelope, not only frames that
        # pass a binary consensus threshold. A short energy window avoids
        # unstable division at waveform zero crossings and stereo cancellation.
        window = max(1, round(rate * 0.003))
        energy = uniform_filter1d(
            np.mean(audio.astype(np.float64) ** 2, axis=0), window
        )
        clean_energy = uniform_filter1d(
            np.mean(nectar_audio.astype(np.float64) ** 2, axis=0), window
        )
        model_gain = np.clip(
            np.sqrt(np.maximum(clean_energy, 0) / np.maximum(energy, 1e-14)), 0, 1
        )
        model_gain[energy < 1e-12] = 1
        model_gain[model_gain > 0.995] = 1
        gain = np.minimum(
            model_gain**gain_power, 1 - mask * (1 - 10 ** (-reduction / 20))
        )
        # Preserve retained periodic voice even when the breath plugin attenuates
        # a trailing syllable. Ten-ms protection plus interpolated transitions
        # protects the word without reinstating the old thirty-ms mask hole.
        voice_guard = binary_dilation(voiced, iterations=1).astype(np.float32)
        protection = np.interp(
            np.arange(audio.shape[-1]) * 100 / rate, np.arange(count), voice_guard
        )
        gain = np.maximum(gain, protection)
        gain = np.maximum(gain, 10 ** (-reduction / 20))
        mask = (
            ((1 - gain) / (1 - 10 ** (-reduction / 20))).astype(np.float32)
            if reduction
            else np.zeros_like(mask)
        )
        # No attenuation of numerical plugin residue on untouched material.
        mask[mask < 1e-5] = 0
        core_events = events
        events = []
        hop = max(1, round(rate / 100))
        activity = np.array(
            [np.any(mask[i : i + hop] > 0.001) for i in range(0, len(mask), hop)]
        )
        report_edges = np.diff(np.r_[False, activity, False].astype(np.int8))
        for begin, end in zip(
            np.flatnonzero(report_edges == 1), np.flatnonzero(report_edges == -1)
        ):
            events.append(
                dict(
                    start_seconds=round(begin * hop / rate, 4),
                    end_seconds=round(min(len(mask), end * hop) / rate, 4),
                    evidence="Continuous dedicated-model gain and/or corroborated aspiration region",
                )
            )
        strategy = "continuous_model_gain_with_retained_voice_guard"
    result = audio * (1 - mask[None] * (1 - 10 ** (-reduction / 20)))
    return (
        result.astype(np.float32),
        mask,
        dict(
            mode="automatic",
            reduction_db=reduction,
            protection_ms=edge_ms,
            detector_threshold=threshold,
            boundary_extension_ms=extension_ms,
            regions=events,
            affected_seconds=round(float(np.count_nonzero(mask) / rate), 4),
            strategy=strategy,
            nectar_gain_power=gain_power,
            consensus_core_regions=core_events,
            nectar_detector=nectar_audio is not None,
            note="Automatic model consensus with retained-voice protection. Singing-domain accuracy is not guaranteed.",
        ),
    )


def protected_breaths(audio, aspiration, rate, params=None):
    params = dict(params or {})
    reduction = float(params.get("reduction_db", 60))
    protection_ms = float(params.get("protection_ms", 100))
    ratio_threshold = float(params.get("ratio_threshold", 0.6))
    min_ms = float(params.get("min_breath_ms", 70))
    for name, value, low, high in [
        ("reduction_db", reduction, 0, 80),
        ("protection_ms", protection_ms, 30, 300),
        ("ratio_threshold", ratio_threshold, 0.1, 2),
        ("min_breath_ms", min_ms, 30, 500),
    ]:
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{name} must be between {low} and {high}")
    audio = np.asarray(audio, dtype=np.float32)
    aspiration = np.asarray(aspiration, dtype=np.float32)
    if audio.ndim != 2 or audio.shape != aspiration.shape or audio.shape[-1] == 0:
        raise ValueError(
            "Breath control requires matching nonempty channel-first audio"
        )
    if not np.isfinite(audio).all() or not np.isfinite(aspiration).all() or rate < 8000:
        raise ValueError("Breath control requires finite audio at 8 kHz or above")
    # Use the loudest channel for voicing, avoiding anti-phase stereo cancellation.
    channel = int(np.argmax(np.mean(audio.astype(np.float64) ** 2, axis=1)))
    divisor = math.gcd(int(rate), 16000)
    signal = resample_poly(audio[channel], 16000 // divisor, int(rate) // divisor)
    breath = resample_poly(aspiration[channel], 16000 // divisor, int(rate) // divisor)
    hop, frame = 160, 640
    count = max(1, int(math.ceil(len(signal) / hop)))
    pad = frame // 2
    needed = (count - 1) * hop + frame

    def frames(x):
        x = np.pad(x, (pad, max(pad, needed - len(x) - pad)))
        return np.lib.stride_tricks.sliding_window_view(x, frame)[::hop][:count]

    source_frames, breath_frames = frames(signal), frames(breath)
    rms = np.sqrt(np.mean(source_frames**2, axis=1))
    breath_rms = np.sqrt(np.mean(breath_frames**2, axis=1))
    periodicity = np.zeros(count, dtype=np.float32)
    for offset in range(0, count, 512):
        chunk = source_frames[offset : offset + 512]
        centered = chunk - chunk.mean(axis=1, keepdims=True)
        spectrum = np.fft.rfft(centered * np.hanning(frame), n=2048, axis=1)
        correlation = np.fft.irfft(np.abs(spectrum) ** 2, n=2048, axis=1)
        periodicity[offset : offset + len(chunk)] = np.max(
            correlation[:, 16:229], axis=1
        ) / np.maximum(correlation[:, 0], 1e-12)
    voiced = (periodicity > 0.5) & (rms > 1e-5)
    protected = binary_dilation(
        voiced, iterations=max(1, math.ceil(protection_ms / 10))
    )
    ratio = breath_rms / np.maximum(rms, 1e-8)
    # Only model-dominant, non-pitched regions away from voiced attacks/releases.
    candidates = binary_closing((ratio >= ratio_threshold) & (rms > 3e-5), iterations=1)
    candidates &= ~protected
    edges = np.diff(np.r_[False, candidates, False].astype(np.int8))
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    mask = np.zeros(audio.shape[-1], dtype=np.float32)
    events = []
    for begin, end in zip(starts, ends):
        if (end - begin) * 10 < min_ms:
            continue
        # Frame centers map to source time. All fades stay inside detected regions.
        left, right = (
            int(begin * rate / 100),
            min(audio.shape[-1], int(end * rate / 100)),
        )
        if right <= left:
            continue
        envelope = np.ones(right - left, dtype=np.float32)
        fade = min(int(0.015 * rate), len(envelope) // 2)
        if fade:
            envelope[:fade] = np.linspace(0, 1, fade, dtype=np.float32)
            envelope[-fade:] = np.linspace(1, 0, fade, dtype=np.float32)
        mask[left:right] = envelope
        events.append(
            {
                "start_seconds": round(left / rate, 4),
                "end_seconds": round(right / rate, 4),
                "mean_model_ratio": round(float(ratio[begin:end].mean()), 3),
            }
        )
    gain = 1 - mask * (1 - 10 ** (-reduction / 20))
    output = audio * gain[None, :]
    return (
        output.astype(np.float32),
        mask,
        {
            "mode": "between_phrases",
            "reduction_db": reduction,
            "protection_ms": protection_ms,
            "regions": events,
            "affected_seconds": round(float(np.count_nonzero(mask) / rate), 4),
            "note": "Detection is heuristic; review removed audio for unvoiced consonants.",
        },
    )
