"""Bounded CPU inference for Respiro-en's MIT-licensed ONNX export.

Original model: ydqmkkx/Respiro-en. Export provenance and license accompany
models/respiro/respiro-en.onnx. Trained on English speech, not singing.
"""

from pathlib import Path
import hashlib
import math
import numpy as np
from scipy.signal import resample_poly

MODEL_SHA256 = "3ccc55d4130b2465f8a7975178a30317d45babb7de5e7b3533fae1810c9b7138"


def features(wave):
    import librosa

    wave = np.asarray(wave, dtype=np.float32)
    mel = librosa.feature.melspectrogram(
        y=wave, sr=16000, n_fft=400, hop_length=160, n_mels=128
    )
    mel = librosa.power_to_db(mel, ref=np.max)
    padded = np.pad(wave, (200, 200))
    frames = np.lib.stride_tricks.sliding_window_view(padded, 400)[::160]
    zcr = np.abs(np.diff(np.sign(frames), axis=1)).sum(axis=1) * 0.5 / 400
    # Upstream uses torch.var with its default unbiased=True (ddof=1).
    variance = np.var(mel, axis=0, ddof=1)
    return np.stack(
        [mel, np.broadcast_to(variance, mel.shape), np.broadcast_to(zcr, mel.shape)]
    )[None].astype(np.float32)


def breath_probabilities(audio, rate, checkpoint=None, threads=4):
    import onnxruntime as ort

    audio = np.asarray(audio, dtype=np.float32)
    if (
        audio.ndim != 2
        or audio.shape[-1] == 0
        or rate < 8000
        or not np.isfinite(audio).all()
    ):
        raise ValueError(
            "Respiro requires finite nonempty channel-first audio at >=8kHz"
        )
    model = Path(checkpoint or Path(__file__).parent / "models/respiro/respiro-en.onnx")
    if (
        not model.is_file()
        or hashlib.sha256(model.read_bytes()).hexdigest() != MODEL_SHA256
    ):
        raise ValueError("Respiro checkpoint is missing or has an unverified hash")
    options = ort.SessionOptions()
    options.intra_op_num_threads = int(threads)
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model), sess_options=options, providers=["CPUExecutionProvider"]
    )
    channel = int(np.argmax(np.mean(audio.astype(np.float64) ** 2, axis=1)))
    divisor = math.gcd(int(rate), 16000)
    wave = resample_poly(audio[channel], 16000 // divisor, int(rate) // divisor)
    # 20-second retained cores, 2-second context. Attention memory stays bounded.
    count = len(wave) // 160 + 1
    result = np.zeros(count, dtype=np.float32)
    for begin in range(0, count, 2000):
        end = min(count, begin + 2000)
        left, right = max(0, begin - 200), min(count, end + 200)
        snippet = wave[left * 160 : min(len(wave), right * 160)]
        if len(snippet) < 1600:
            snippet = np.pad(snippet, (0, 1600 - len(snippet)))
        pred = session.run(None, {"feat": features(snippet)})[0][0]
        core = pred[begin - left : end - left]
        if len(core) != end - begin:
            raise RuntimeError("Respiro output length mismatch")
        result[begin:end] = core
    if not np.isfinite(result).all() or np.min(result) < 0 or np.max(result) > 1:
        raise RuntimeError("Invalid Respiro probabilities")
    return result
