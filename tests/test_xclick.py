import os
import numpy as np
import pytest
from xclick_control import repair_clicks


@pytest.mark.skipif(
    os.getenv("RESTORE_NATIVE_TESTS") != "1",
    reason="Opt-in installed studio plugin test",
)
def test_real_xclick_repairs_impulse_over_sustained_voice():
    rate = 44100
    t = np.arange(rate * 3) / rate
    voice = (
        0.1 * np.sin(2 * np.pi * 220 * t) + 0.03 * np.sin(2 * np.pi * 440 * t)
    ).astype(np.float32)[None]
    damaged = voice.copy()
    at = rate + rate // 2
    damaged[0, at : at + 3] += [0.4, -0.35, 0.2]
    repaired, report = repair_clicks(damaged, rate)
    assert repaired.shape == voice.shape
    assert report["measured_host_lag_samples"] == 0
    assert report["zero_repair_max_error"] <= 1e-6
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


@pytest.mark.parametrize("params", [{"threshold": 101}, {"shape": float("nan")}])
def test_invalid_settings(params):
    with pytest.raises(ValueError):
        repair_clicks(np.zeros((1, 100), np.float32), 44100, params)


def test_mouth_dispatches_reconstruction_after_protected_suppression(monkeypatch):
    import mouth_control, xclick_control

    x = np.ones((1, 1000), np.float32) * 0.1
    monkeypatch.setattr(mouth_control, "render_vst", lambda x, *args: (x.copy(), {}))
    monkeypatch.setattr(
        mouth_control,
        "protect_click_repairs",
        lambda x, y, *args, **kwargs: (x.copy(), {}),
    )
    monkeypatch.setattr(
        xclick_control, "repair_clicks", lambda y, *args: (y * 0.9, {"engine": "test"})
    )
    result, report = mouth_control.clean_mouth_noises(
        x, 16000, {"amount": 0.5, "click_repair": {"enabled": True}}
    )
    np.testing.assert_allclose(result, x * 0.95)
    assert report["click_repair"]["engine"] == "test"
