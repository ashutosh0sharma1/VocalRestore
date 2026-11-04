import numpy as np
from click_control import protect_click_repairs
from audio_plugins import studio_finish


def test_destructive_click_repair_is_tempered_around_voiced_stereo():
    rate = 16000
    tone = (0.1 * np.sin(2 * np.pi * 220 * np.arange(rate * 2) / rate)).astype(
        np.float32
    )
    source = np.stack([tone, -tone])
    repaired = source.copy()
    repaired[:, rate : rate + 160] = 0
    result, report = protect_click_repairs(source, repaired, rate)
    np.testing.assert_array_equal(result[:, :rate], source[:, :rate])
    assert (
        np.linalg.norm(result[:, rate : rate + 160])
        > np.linalg.norm(source[:, rate : rate + 160]) * 0.5
    )
    assert report["tempered_frames"] > 0
    np.testing.assert_array_equal(result[0], -result[1])


def test_click_passthrough_and_zero_finish_are_exact():
    x = np.random.default_rng(1).normal(0, 0.01, (2, 16000)).astype(np.float32)
    y, _ = protect_click_repairs(x, x, 16000)
    np.testing.assert_array_equal(x, y)
    y, _ = studio_finish(x, 16000, {"amount": 0})
    np.testing.assert_array_equal(x, y)
