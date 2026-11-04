import shutil
import numpy as np
import pytest
import settings
from light_click import repair_clicks


@pytest.mark.skipif(
    not shutil.which("node")
    or not (settings.ROOT / "vendor/audiojs/node_modules").is_dir(),
    reason="AudioJS install required",
)
def test_light_repair_fixes_impulse_without_changing_duration():
    rate = 44100
    t = np.arange(rate * 2) / rate
    voice = (
        0.1 * np.sin(2 * np.pi * 220 * t) + 0.03 * np.sin(2 * np.pi * 440 * t)
    ).astype(np.float32)[None]
    damaged = voice.copy()
    at = rate
    damaged[0, at : at + 3] += [0.4, -0.35, 0.2]
    repaired, report = repair_clicks(damaged, rate)
    assert repaired.shape == voice.shape and np.isfinite(repaired).all()
    assert (
        np.linalg.norm(repaired[:, at - 30 : at + 50] - voice[:, at - 30 : at + 50])
        < np.linalg.norm(damaged[:, at - 30 : at + 50] - voice[:, at - 30 : at + 50])
        * 0.5
    )
    outside = np.ones(voice.shape[-1], bool)
    outside[at - 1000 : at + 1000] = False
    assert (
        np.linalg.norm(repaired[:, outside] - voice[:, outside])
        / np.linalg.norm(voice[:, outside])
        < 0.005
    )
    assert report["peak_process_bytes"] > 0


def test_portable_bypass_does_not_require_plugins():
    from mouth_control import clean_mouth_noises

    x = np.ones((2, 1000), np.float32) * 0.1
    y, report = clean_mouth_noises(
        x, 16000, {"nectar_enabled": False, "click_repair": {"enabled": False}}
    )
    np.testing.assert_array_equal(x, y)
    assert report["engine"] == "bypass"


@pytest.mark.parametrize("bad", [float("nan"), 2, 21])
def test_light_invalid_settings(bad):
    with pytest.raises(ValueError):
        repair_clicks(np.zeros((1, 100), np.float32), 44100, {"light_threshold": bad})
