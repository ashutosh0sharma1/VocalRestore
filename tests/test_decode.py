import shutil
import numpy as np
import pytest
import soundfile as sf
from worker import decode

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)


def test_decode_unicode_source_preserves_format_and_samples(tmp_path):
    source = tmp_path / "श्री.wav"
    target = tmp_path / "decoded.wav"
    x = np.random.default_rng(7).normal(0, 0.05, (48000, 2)).astype(np.float32)
    sf.write(source, x, 48000, subtype="FLOAT")
    report = decode(source, target)
    actual, rate = sf.read(target, dtype="float32", always_2d=True)
    assert rate == 48000 and report["frames"] == 48000
    np.testing.assert_array_equal(actual, x)
    np.testing.assert_array_equal(sf.read(source, dtype="float32")[0], x)


def test_reject_multichannel(tmp_path):
    source = tmp_path / "four.wav"
    sf.write(source, np.zeros((16000, 4)), 16000)
    with pytest.raises(ValueError, match="mono or stereo"):
        decode(source, tmp_path / "out.wav")


def test_reject_playlist_disguised_as_audio(tmp_path):
    source = tmp_path / "fake.wav"
    source.write_text("#EXTM3U\nhttps://invalid.example/audio.ts\n")
    import subprocess

    with pytest.raises(subprocess.CalledProcessError):
        decode(source, tmp_path / "out.wav")
