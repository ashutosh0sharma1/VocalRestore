import os
from functools import partial
import settings
import numpy as np
import pytest
from breath_control import automatic_breaths
from respiro_detector import breath_probabilities

breath_probabilities = partial(
    breath_probabilities, checkpoint=settings.load()["respiro_model"]
)
from audio_plugins import nectar_breaths


def test_consensus_preserves_singing_rejected_by_other_detector():
    rate = 16000
    t = np.arange(rate * 3) / rate
    source = np.zeros((2, len(t)), np.float32)
    source[:, rate : 2 * rate] = 0.15 * np.sin(2 * np.pi * 220 * t[rate : 2 * rate])
    source[1] *= -1
    noise = np.random.default_rng(3).normal(0, 0.02, 4000).astype(np.float32)
    source[:, 3200:7200] = noise
    aspiration = source.copy()  # separator wrongly removes singing too
    # Independent detector rejects vowels, accepts only breath.
    probability = np.zeros(301, np.float32)
    probability[20:45] = 0.95
    result, mask, report = automatic_breaths(source, aspiration, rate, probability)
    np.testing.assert_array_equal(
        result[:, rate : 2 * rate], source[:, rate : 2 * rate]
    )
    np.testing.assert_array_equal(result[:, mask == 0], source[:, mask == 0])
    assert (
        np.linalg.norm(result[:, 4000:6000])
        < np.linalg.norm(source[:, 4000:6000]) * 0.002
    )
    assert report["regions"]
    np.testing.assert_allclose(result + (source - result), source, atol=1e-8)


def test_respiro_false_positive_on_retained_vowel_is_vetoed():
    rate = 16000
    source = (0.1 * np.sin(2 * np.pi * 330 * np.arange(rate) / rate))[None].astype(
        np.float32
    )
    result, mask, report = automatic_breaths(
        source, np.zeros_like(source), rate, np.ones(101)
    )
    np.testing.assert_array_equal(result, source)
    assert not mask.any()


def test_silence_never_becomes_a_removal_event():
    source = np.zeros((1, 16000), np.float32)
    result, mask, report = automatic_breaths(source, source, 16000, np.ones(101))
    assert not mask.any()
    assert not report["regions"]


def test_confirmed_breath_extends_into_faint_tails_without_crossing_word():
    rate = 16000
    source = np.zeros((1, rate * 2), np.float32)
    rng = np.random.default_rng(72)
    source[:, 4000:11200] = rng.normal(0, 0.004, (1, 7200))
    source[:, 4800:10400] *= 4
    t = np.arange(8000) / rate
    source[:, 12000:20000] = 0.1 * np.sin(2 * np.pi * 220 * t)
    aspiration = source.copy()
    aspiration[:, 12000:20000] = 0
    probability = np.zeros(201, np.float32)
    probability[30:65] = 0.95
    probability[25:30] = 0.01
    probability[65:70] = 0.01
    nectar = source.copy()
    nectar[:, 4000:11200] *= 0.01
    y, mask, report = automatic_breaths(
        source, aspiration, rate, probability, nectar_audio=nectar
    )
    assert mask[4300] > 0.99 and mask[10900] > 0.99
    np.testing.assert_array_equal(y[:, 12000:20000], source[:, 12000:20000])
    np.testing.assert_array_equal(y[:, mask == 0], source[:, mask == 0])
    assert report["boundary_extension_ms"] == 60


def test_detector_boundary_does_not_expand_into_louder_consonant():
    rate = 16000
    source = np.zeros((1, rate), np.float32)
    rng = np.random.default_rng(73)
    source[:, 3200:7200] = rng.normal(0, 0.01, (1, 4000))
    source[:, 7360:8960] = rng.normal(0, 0.1, (1, 1600))
    p = np.zeros(101, np.float32)
    p[20:45] = 0.95
    p[45:56] = 0.01
    y, mask, _ = automatic_breaths(source, source.copy(), rate, p)
    np.testing.assert_array_equal(y[:, 7520:8960], source[:, 7520:8960])


def test_invalid_boundary_extension_rejected():
    with pytest.raises(ValueError, match="boundary_extension_ms"):
        automatic_breaths(
            np.zeros((1, 16000)),
            np.zeros((1, 16000)),
            16000,
            np.zeros(101),
            {"boundary_extension_ms": float("nan")},
        )


def test_medium_confidence_false_breath_does_not_swallow_adjacent_pitched_voice():
    rate = 16000
    source = np.zeros((1, rate * 2), np.float32)
    source[:, 3200:8000] = np.random.default_rng(74).normal(0, 0.02, (1, 4800))
    t = np.arange(8000) / rate
    source[:, 8000:16000] = 0.1 * np.sin(2 * np.pi * 220 * t)
    probability = np.zeros(201, np.float32)
    probability[20:50] = 0.95
    probability[50:100] = 0.3
    y, mask, _ = automatic_breaths(source, source.copy(), rate, probability)
    np.testing.assert_array_equal(y[:, 8320:16000], source[:, 8320:16000])


def test_continuous_model_gain_removes_soft_tail_but_restores_retained_voice():
    rate = 16000
    source = np.zeros((1, rate * 3), np.float32)
    source[:, 3200:11200] = np.random.default_rng(75).normal(0, 0.02, (1, 8000))
    t = np.arange(rate) / rate
    source[:, rate : 2 * rate] = 0.1 * np.sin(2 * np.pi * 220 * t)
    aspiration = source.copy()
    aspiration[:, rate : 2 * rate] = 0
    detector = source.copy()
    detector[:, 3200:9600] *= 0.01
    detector[:, 9600:11200] *= 0.65  # no hard threshold event, but audible soft tail
    detector[:, rate : 2 * rate] *= 0.2  # adversarial plugin attenuates wanted singing
    probability = np.zeros(301, np.float32)
    probability[20:60] = 0.95
    y, mask, report = automatic_breaths(
        source,
        aspiration,
        rate,
        probability,
        {"continuous_gain": True},
        nectar_audio=detector,
    )
    assert (
        np.linalg.norm(y[:, 10000:10800]) < np.linalg.norm(source[:, 10000:10800]) * 0.4
    )
    np.testing.assert_array_equal(
        y[:, rate + 1600 : 2 * rate - 1600], source[:, rate + 1600 : 2 * rate - 1600]
    )
    np.testing.assert_array_equal(y[:, mask == 0], source[:, mask == 0])
    assert report["strategy"] == "continuous_model_gain_with_retained_voice_guard"
    assert report["regions"] and report["consensus_core_regions"]


def test_continuous_zero_reduction_is_exact_passthrough():
    x = np.random.default_rng(76).normal(0, 0.02, (2, 16000)).astype(np.float32)
    y, mask, _ = automatic_breaths(
        x,
        x,
        16000,
        np.ones(101),
        {"continuous_gain": True, "reduction_db": 0},
        nectar_audio=x * 0.1,
    )
    np.testing.assert_array_equal(x, y)
    assert not mask.any()


@pytest.mark.parametrize(
    "probability", [np.array([np.nan]), np.array([-1]), np.ones(3)]
)
def test_invalid_detector_results_fail_closed(probability):
    with pytest.raises(ValueError):
        automatic_breaths(
            np.zeros((1, 16000)), np.zeros((1, 16000)), 16000, probability
        )


@pytest.mark.skipif(
    os.getenv("RESTORE_NATIVE_TESTS") != "1", reason="Opt-in installed detector test"
)
def test_real_respiro_handles_tiny_antiphase_and_full_length():
    # Real checkpoint, two contexts including an internal20s boundary.
    t = np.arange(16000 * 22) / 16000
    tone = (0.05 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    probability = breath_probabilities(np.stack([tone, -tone]), 16000)
    assert len(probability) == 2201
    assert np.isfinite(probability).all()
    tiny = breath_probabilities(np.zeros((1, 800), np.float32), 16000)
    assert len(tiny) == 6


@pytest.mark.skipif(
    os.getenv("RESTORE_NATIVE_TESTS") != "1",
    reason="Opt-in installed studio plugin test",
)
def test_real_nectar_sustained_voice_is_timing_aligned():
    rate = 44100
    t = np.arange(rate * 2) / rate
    x = (0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)[None]
    y, report = nectar_breaths(x, rate)
    assert y.shape == x.shape
    # Middle of a sustained vowel, excluding warm-up and tail.
    np.testing.assert_allclose(
        y[:, rate // 2 : rate], x[:, rate // 2 : rate], atol=2e-6
    )
    assert report["reported_latency_samples"] > 0
