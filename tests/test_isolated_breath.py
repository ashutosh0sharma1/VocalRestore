import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

import isolated_breath as isolated


def test_worker_finishes_before_plugins_and_cache_is_source_bound(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.wav"
    rate = 16000
    x = np.sin(np.arange(rate) * 2 * np.pi * 220 / rate).astype(np.float32) * 0.1
    sf.write(source, np.column_stack([x, x]), rate, subtype="FLOAT")
    events = []

    def separator(src, dst, *, removed_output_path, **kwargs):
        audio, sr = isolated.vr.load_audio(src)
        isolated.vr.save_audio(dst, audio, sr)
        isolated.vr.save_audio(removed_output_path, np.zeros_like(audio), sr)
        return removed_output_path

    def child(command, *, input, env, **kwargs):
        events.append("worker")
        assert command[-1] == "--model-worker"
        request = json.loads(input)
        assert request["model_kwargs"]["inference_params"]["cpu_threads"] == 8
        assert env["PYTHONFAULTHANDLER"] == "1"
        isolated.model_worker(request)
        events.append("worker-exited")
        return subprocess.CompletedProcess(command, 0)

    def probabilities(audio, sr, **kwargs):
        assert "worker-exited" in events
        return np.zeros(audio.shape[-1] // 160 + 1, np.float32)

    def nectar(audio, sr, controls):
        assert "worker-exited" in events
        events.append("vst")
        return audio.copy(), {"host": "test"}

    import respiro_detector, audio_plugins

    monkeypatch.setattr(isolated.vr, "run_model_stage", separator)
    monkeypatch.setattr(isolated.subprocess, "run", child)
    monkeypatch.setattr(respiro_detector, "breath_probabilities", probabilities)
    monkeypatch.setattr(audio_plugins, "nectar_breaths", nectar)
    settings = dict(
        model_name="test",
        output_stem="other",
        model_dir=tmp_path,
        device="cpu",
        source="huggingface",
        inference_params={"cpu_threads": 16},
        download=False,
    )

    def run():
        isolated.run_breath_stage(
            source,
            tmp_path / "clean.wav",
            breath_params={"mode": "automatic"},
            removed_output_path=tmp_path / "removed.wav",
            **settings,
        )

    run()
    assert events.index("worker-exited") < events.index("vst")
    original, _ = sf.read(source)
    result, _ = sf.read(tmp_path / "clean.wav")
    np.testing.assert_array_equal(result, original)
    run()
    assert events.count("worker") == 1
    sf.write(source, np.column_stack([x * 0.5, x * 0.5]), rate, subtype="FLOAT")
    run()
    assert events.count("worker") == 2
    with (tmp_path / "aspiration-cache/aspiration.wav").open("ab") as f:
        f.write(b"changed")
    run()
    assert events.count("worker") == 3
