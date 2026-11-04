import shutil
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

import approved_delivery as delivery


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_delivery_export_bounds_gain_and_preserves_format(tmp_path):
    rate = 44100
    x = 0.01 * np.sin(np.arange(rate) * (2 * np.pi * 440 / rate))
    # FFmpeg prints this path as UTF-8; Windows' default cp1252 decoder fails
    # on the Devanagari virama unless the metrics reader sets its encoding.
    source, output = tmp_path / "श्री-quiet.wav", tmp_path / "export.wav"
    sf.write(source, np.column_stack([x, x]), rate, subtype="FLOAT")
    report = delivery.export_delivery(source, output)
    assert report["gain_db"] <= 3
    assert float(report["metrics"]["input_tp"]) <= -0.95
    assert sf.info(output).frames == rate
    assert sf.info(output).channels == 2
    assert sf.info(output).subtype == "PCM_24"
    silent = tmp_path / "silence.wav"
    sf.write(silent, np.zeros((rate, 2)), rate, subtype="PCM_24")
    report = delivery.export_delivery(silent, tmp_path / "silent-export.wav")
    assert report["gain_db"] == 0
    assert np.count_nonzero(sf.read(tmp_path / "silent-export.wav")[0]) == 0


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_delivery_resumes_bound_checkpoints_and_rejects_tampering(
    tmp_path, monkeypatch
):
    source, output = tmp_path / "input.wav", tmp_path / "job"
    sf.write(source, np.zeros((44100, 2)), 44100, subtype="PCM_24")
    calls = []

    def passthrough(src, dst, *args, **kwargs):
        calls.append(Path(dst).stem)
        delivery.shutil.copyfile(src, dst)

    monkeypatch.setattr(delivery.vr, "run_model_stage", passthrough)
    monkeypatch.setattr(delivery, "run_breath_stage", passthrough)
    monkeypatch.setattr(delivery.vr, "run_declick", passthrough)
    monkeypatch.setattr(delivery.vr, "run_studio_finish", passthrough)
    final = delivery.deliver(source, output)
    assert calls == ["01-denoise", "02-dereverb", "03-breaths", "04-mouth", "05-finish"]
    assert final.is_file()
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["original_unchanged"]
    assert receipt["status"] == "complete"
    calls.clear()
    delivery.deliver(source, output)
    assert not calls
    with (output / "02-dereverb.wav").open("ab") as f:
        f.write(b"changed checkpoint")
    with pytest.raises(ValueError, match="Checkpoint altered"):
        delivery.deliver(source, output)
