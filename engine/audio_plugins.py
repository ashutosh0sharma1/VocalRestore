"""Offline adapters for already-installed vocal plugins; no activation/downloads."""

from pathlib import Path
import math
import numpy as np

NECTAR = Path(
    r"C:\Program Files\Common Files\VST3\iZotope\Nectar 4 Breath Control.vst3"
)
SOOTHE = Path(r"C:\Program Files\Common Files\VST3\oeksound\soothe2_x64.vst3")


def render_plugin(audio, rate, path, settings):
    from daw_host import render_vst

    return render_vst(audio, rate, path, settings)


def nectar_breaths(audio, rate, params=None):
    params = dict(params or {})
    sensitivity = float(params.get("nectar_sensitivity", 60))
    reduction = float(params.get("reduction_db", 60))
    if not math.isfinite(sensitivity) or not 0 <= sensitivity <= 100:
        raise ValueError("nectar_sensitivity must be between0 and100")
    if not math.isfinite(reduction) or not 0 <= reduction <= 80:
        raise ValueError("reduction_db must be between0 and80")
    return render_plugin(
        audio,
        rate,
        params.get("nectar_path", NECTAR),
        dict(
            breath_algorithm="Gain",
            breath_gain_db=-reduction,
            breath_sensitivity=sensitivity,
            breath_listen=False,
            breath_bypass=False,
        ),
    )


def studio_finish(audio, rate, params=None):
    """Optional light adaptive resonance and restrained dynamics, without reverb."""
    from scipy.signal import butter, sosfiltfilt

    params = dict(params or {})
    amount = float(params.get("amount", 0.35))
    if not math.isfinite(amount) or not 0 <= amount <= 1:
        raise ValueError("Finish amount must be in [0,1]")
    original = np.asarray(audio, dtype=np.float32)
    if amount == 0:
        return original.copy(), dict(mode="bypass", amount=0)
    from pedalboard import Compressor

    if params.get("soothe_enabled", True):
        softened, report = render_plugin(
            original,
            rate,
            params.get("soothe_path", SOOTHE),
            dict(
                mode="soft",
                depth=-6,
                sharpness=3,
                selectivity=4,
                mix=100,
                trim_db=0,
                input_trim_db=0,
                bypass=False,
                delta=False,
                sidechain=False,
                stereo_link=100,
            ),
        )
    else:
        softened, report = original, {"mode": "no_soothe"}
    # Blend limits the maximum spectral change; no static nasal-notch EQ.
    result = original + amount * (softened - original)
    if result.shape[-1] > 32:
        result = sosfiltfilt(
            butter(2, 30, btype="highpass", fs=rate, output="sos"), result, axis=1
        ).astype(np.float32)
    hop = max(1, int(rate * 0.05))
    # Adapt threshold to this recording instead of assuming a fixed vocal level.
    length = result.shape[-1] // hop * hop
    rms = (
        np.sqrt(
            np.mean(
                result[:, :length].reshape(result.shape[0], -1, hop) ** 2, axis=(0, 2)
            )
        )
        if length
        else np.array([0.0])
    )
    active = rms[rms > max(1e-5, float(rms.max()) * 0.02)]
    threshold = float(
        20
        * np.log10(max(float(np.percentile(active, 80)) if len(active) else 1e-4, 1e-6))
    )
    comp = Compressor(threshold_db=threshold, ratio=1.35, attack_ms=20, release_ms=150)
    compressed = comp(result, rate)
    # Parallel dynamics avoid making already quiet consonants louder.
    result = result + 0.5 * (compressed - result)
    return result.astype(np.float32), dict(
        mode="light_adaptive",
        amount=amount,
        resonance=report,
        highpass_hz=30,
        compressor=dict(
            threshold_db=threshold, ratio=1.35, attack_ms=20, release_ms=150, wet=0.5
        ),
    )
