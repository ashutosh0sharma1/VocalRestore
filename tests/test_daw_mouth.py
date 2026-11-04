import os
import numpy as np
import pytest
import mouth_control


def test_paired_renders_cancel_level_riding(monkeypatch):
    rate = 16000
    x = np.random.default_rng(43).normal(0, 0.02, (2, rate)).astype(np.float32)

    def plugin(source, rate, path, settings):
        output = source * 2  # unwanted Auto-Level gain, must cancel
        if settings["alm_tame_noises"]:
            output[:, 4000:8000] *= 0.5
        return output, {"host": "DawDreamer"}

    monkeypatch.setattr(mouth_control, "render_vst", plugin)
    y, report = mouth_control.clean_mouth_noises(
        x, rate, {"protect_singing": False, "suppression_power": 5}
    )
    np.testing.assert_array_equal(y[:, :3900], x[:, :3900])
    np.testing.assert_array_equal(y[:, 8100:], x[:, 8100:])
    assert np.linalg.norm(y[:, 4500:7500]) < np.linalg.norm(x[:, 4500:7500]) * 0.04
    assert report["detector_on"]["host"] == "DawDreamer"


def test_mouth_stage_never_launches_audacity(tmp_path, monkeypatch):
    import vocal_restore as vr
    import subprocess

    def reject(*args, **kwargs):
        pytest.fail("Mouth stage must not start an external process")

    monkeypatch.setattr(subprocess, "Popen", reject)
    monkeypatch.setattr(
        mouth_control,
        "clean_mouth_noises",
        lambda x, rate, params: (x.copy(), {"host": "DawDreamer"}),
    )
    source = tmp_path / "in.wav"
    target = tmp_path / "out.wav"
    x = np.zeros((1, 16000), np.float32)
    vr.save_audio(source, x, 16000)
    vr.run_declick(source, target, {})
    np.testing.assert_array_equal(vr.load_audio(target)[0], x)
    assert target.with_suffix(".clicks.json").is_file()


@pytest.mark.skipif(
    os.getenv("RESTORE_NATIVE_TESTS") != "1",
    reason="Opt-in installed studio plugin test",
)
def test_real_dawdreamer_tame_preserves_stable_voiced_tone():
    rate = 44100
    t = np.arange(rate * 2) / rate
    tone = (
        0.1 * np.sin(2 * np.pi * 220 * t) + 0.03 * np.sin(2 * np.pi * 440 * t)
    ).astype(np.float32)[None]
    result, report = mouth_control.clean_mouth_noises(tone, rate)
    assert result.shape == tone.shape and np.isfinite(result).all()
    assert np.linalg.norm(tone - result) / np.linalg.norm(tone) < 0.02
    assert report["detector_on"]["host"] == "DawDreamer"
