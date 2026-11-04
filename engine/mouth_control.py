"""Automatic mouth-noise suppression plus optional isolated click reconstruction.

Paired Tame Noises ON/OFF renders cancel Nectar Auto-Level's gain riding.
Only the model's differential noise suppression is applied to original audio.
"""

from pathlib import Path
import math
import numpy as np
from click_control import protect_click_repairs

PLUGIN = Path(r"C:\Program Files\Common Files\VST3\iZotope\Nectar 4 Auto-Level.vst3")


def render_vst(*args, **kwargs):
    from daw_host import render_vst as render

    return render(*args, **kwargs)


def clean_mouth_noises(audio, rate, params=None):
    params = dict(params or {})
    amount = float(params.get("amount", 1))
    power = float(params.get("suppression_power", 5))
    maximum = float(params.get("reduction_db", 60))
    for name, value, low, high in [
        ("amount", amount, 0, 1),
        ("suppression_power", power, 1, 10),
        ("reduction_db", maximum, 0, 80),
    ]:
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{name} must be between{low} and{high}")
    source = np.asarray(audio, dtype=np.float32)
    if (
        source.ndim != 2
        or not source.shape[-1]
        or rate < 8000
        or not np.isfinite(source).all()
    ):
        raise ValueError("Finite nonempty channel-first source required")
    if amount == 0:
        return source.copy(), dict(engine="dawdreamer_nectar_tame", mode="bypass")
    if not params.get("nectar_enabled", True):
        repair_params = params.get("click_repair") or {}
        if not repair_params.get("enabled", True):
            return source.copy(), dict(engine="bypass")
        if repair_params.get("engine", "audiojs") == "waves":
            from xclick_control import repair_clicks
        else:
            from light_click import repair_clicks
        repaired, report = repair_clicks(source, rate, repair_params)
        return source + amount * (repaired - source), dict(
            engine=repair_params.get("engine", "audiojs"), click_repair=report
        )
    settings = dict(
        alm_range=12,
        alm_strength=50,
        alm_target_level=-18,
        alm_mix=100,
        alm_bypass=False,
        global_bypass=False,
        global_match=False,
        input_gain=0,
        output_gain=0,
        output_pan=0,
        output_width=0,
    )
    off, off_report = render_vst(
        source,
        rate,
        params.get("plugin_path", PLUGIN),
        {**settings, "alm_tame_noises": False},
    )
    on, on_report = render_vst(
        source,
        rate,
        params.get("plugin_path", PLUGIN),
        {**settings, "alm_tame_noises": True},
    )
    hop = max(1, round(rate * 0.002))
    size = source.shape[-1]
    pad = (-size) % hop

    def energy(x):
        return np.mean(
            np.pad(x, ((0, 0), (0, pad))).reshape(x.shape[0], -1, hop) ** 2, axis=(0, 2)
        )

    original_energy = energy(source)
    off_energy, on_energy = energy(off), energy(on)
    gain = np.sqrt(on_energy / np.maximum(off_energy, 1e-20))
    gain = np.clip(gain, 10 ** (-maximum / 20), 1)
    gain[(gain > 0.995) | (original_energy < 1e-12)] = 1
    gain = np.maximum(gain**power, 10 ** (-maximum / 20))
    # Common stereo gain preserves image. Smooth interpolation avoids new clicks.
    centers = (np.arange(len(gain)) + 0.5) * hop
    envelope = np.interp(np.arange(size), centers, gain).astype(np.float32)
    raw = source * (1 - amount * (1 - envelope[None]))
    if params.get("protect_singing", True):
        result, guard = protect_click_repairs(
            source,
            raw,
            rate,
            float(params.get("max_relative_repair", 0.20)),
            strict_voiced=True,
        )
    else:
        result, guard = raw, None
    repair_report = None
    repair_params = dict(params.get("click_repair") or {})
    if repair_params.get("enabled", False):
        if repair_params.get("engine", "waves") == "audiojs":
            from light_click import repair_clicks
        else:
            from xclick_control import repair_clicks
        repaired, repair_report = repair_clicks(result, rate, repair_params)
        result = result + amount * (repaired - result)
    return result, dict(
        engine="nectar_tame_plus_" + repair_params.get("engine", "waves")
        if repair_report
        else "dawdreamer_nectar_tame",
        paired_render=True,
        amount=amount,
        suppression_power=power,
        reduction_db=maximum,
        changed_seconds=round(
            float(np.sum(np.max(np.abs(source - result), axis=0) > 1e-7) / rate), 4
        ),
        detector_on=on_report,
        detector_off=off_report,
        protection=guard,
        click_repair=repair_report,
        note="Nectar suppression protects singing; optional X-Click reconstructs short impulses, including during singing. No manual timestamps or Audacity.",
    )
