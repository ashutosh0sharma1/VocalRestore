"""Fixed-chain audio primitives; model and waveform behavior retained from Restore."""

from __future__ import annotations
import gc
import json
import logging
import math
from pathlib import Path
from typing import Any
import numpy as np
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGGER = logging.getLogger("vocal_restore")


class PipelineError(RuntimeError):
    """Raised when a stage cannot be run safely."""


def load_audio(path: Path) -> tuple[np.ndarray, int]:
    """Load through PyMSS's decoder when available, preserving channel-first."""
    try:
        from pymss.audio_io import load_audio as pymss_load_audio

        audio, sample_rate = pymss_load_audio(str(path), sr=None, mono=False)
        return _channel_first(audio), int(sample_rate)
    except Exception:
        # SoundFile is a useful fallback for ordinary WAV/FLAC input.
        audio, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
        return np.ascontiguousarray(audio.T, dtype=np.float32), int(sample_rate)


def _channel_first(audio: Any) -> np.ndarray:
    array = np.asarray(audio, dtype=np.float32)
    if array.ndim == 1:
        return np.ascontiguousarray(array[None, :])
    if array.ndim != 2:
        raise PipelineError(f"Expected mono/stereo audio, got shape {array.shape}")
    if array.shape[0] <= 8 and array.shape[1] > array.shape[0]:
        return np.ascontiguousarray(array)
    if array.shape[1] <= 8:
        return np.ascontiguousarray(array.T)
    raise PipelineError(f"Cannot infer channel layout for audio shape {array.shape}")


def _match_channels(audio: np.ndarray, channels: int) -> np.ndarray:
    audio = _channel_first(audio)
    channels = max(1, int(channels))
    if audio.shape[0] == channels:
        return audio
    if channels == 1:
        return np.mean(audio, axis=0, keepdims=True, dtype=np.float32)
    if audio.shape[0] == 1:
        return np.repeat(audio, channels, axis=0)
    if audio.shape[0] > channels:
        return audio[:channels]
    repeats = int(math.ceil(channels / audio.shape[0]))
    return np.tile(audio, (repeats, 1))[:channels]


def save_audio(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    array = _channel_first(audio)
    sf.write(str(path), array.T, int(sample_rate), subtype="FLOAT", format="WAV")


def resample_audio(audio: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if int(source_rate) == int(target_rate):
        return np.ascontiguousarray(_channel_first(audio), dtype=np.float32)
    import librosa

    array = _channel_first(audio)
    channels = [
        librosa.resample(channel, orig_sr=int(source_rate), target_sr=int(target_rate))
        for channel in array
    ]
    length = max((len(channel) for channel in channels), default=0)
    result = np.zeros((len(channels), length), dtype=np.float32)
    for index, channel in enumerate(channels):
        result[index, : len(channel)] = channel
    return result


def _match_length(audio: np.ndarray, samples: int) -> np.ndarray:
    array = _channel_first(audio)
    samples = max(0, int(samples))
    if array.shape[-1] == samples:
        return array
    if array.shape[-1] > samples:
        return array[..., :samples]
    return np.pad(array, ((0, 0), (0, samples - array.shape[-1])))


def _find_stem(results: dict[str, Any], requested: str) -> np.ndarray:
    if requested in results:
        return np.asarray(results[requested], dtype=np.float32)
    lower = requested.lower()
    for name, value in results.items():
        if str(name).lower() == lower:
            return np.asarray(value, dtype=np.float32)
    raise PipelineError(
        f"PyMSS model did not return requested stem {requested!r}; "
        f"available stems: {list(results)}"
    )


def _find_removed_stem(results: dict[str, Any], requested: str) -> np.ndarray | None:
    """Find the complementary stem when a model exposes one."""
    aliases = {
        "vocals": ("instrumental", "instrument", "other"),
        "dry": ("other", "noise", "no noise"),
        "noreverb": ("reverb", "other"),
        "other": ("aspiration", "breath", "noise", "dry"),
        "restored": ("degraded", "other", "input"),
        "no noise": ("noise", "other"),
    }
    requested_lower = str(requested).lower()
    by_lower = {str(name).lower(): value for name, value in results.items()}
    for candidate in aliases.get(requested_lower, ()):
        if candidate in by_lower:
            return np.asarray(by_lower[candidate], dtype=np.float32)
    for name, value in results.items():
        if str(name).lower() != requested_lower:
            return np.asarray(value, dtype=np.float32)
    return None


def _cleanup_torch() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def run_model_stage(
    input_path: Path,
    output_path: Path,
    *,
    model_name: str,
    output_stem: str,
    model_dir: Path,
    device: str,
    source: str,
    inference_params: dict[str, Any],
    download: bool = False,
    removed_output_path: Path | None = None,
) -> Path | None:
    """Run one model and optionally save its complementary/removed stem."""
    try:
        from pymss import MSSeparator
    except Exception as exc:  # pragma: no cover - environment error
        raise PipelineError("PyMSS is not importable in this environment") from exc

    LOGGER.info("PyMSS: %s -> %s", model_name, output_stem)
    params = dict(inference_params or {})
    params.setdefault("normalize", False)
    params.setdefault("use_tta", False)
    params.setdefault("enable_tta", bool(params.get("use_tta", False)))
    # CPU has no CUDA attention backend.  PyMSS accepts this key and ignores it
    # on CPU; keeping it explicit makes GPU runs use the current auto probing.
    params.setdefault("cuda_attention_backend", "auto")
    cpu_threads = params.pop("cpu_threads", 16)
    if device == "cpu":
        if (
            isinstance(cpu_threads, bool)
            or not isinstance(cpu_threads, int)
            or not 1 <= cpu_threads <= 256
        ):
            raise PipelineError("cpu_threads must be an integer between1 and256")
        import torch

        torch.set_num_threads(cpu_threads)

    mix, sample_rate = load_audio(input_path)
    original_samples = mix.shape[-1]
    original_channels = mix.shape[0]
    separator = None
    try:
        separator = MSSeparator.from_model_name(
            model_name,
            model_dir=str(model_dir),
            download=download,
            source=source,
            device=device,
            output_format="wav",
            inference_params=params,
        )
        model_rate = int(separator.config.audio.get("sample_rate", sample_rate))
        model_mix = resample_audio(mix, sample_rate, model_rate)
        if removed_output_path is None:
            results = separator.separate(model_mix, pbar=False, stems=[output_stem])
        else:
            # Request all returned stems once so the UI can show both the
            # restored signal and the removed/complementary signal when the
            # model exposes one. The separator still performs one inference.
            results = separator.separate(model_mix, pbar=False)
        selected = _find_stem(results, output_stem)
        restored = _channel_first(selected)
        restored = resample_audio(restored, model_rate, sample_rate)
        restored = _match_length(
            restored, round(original_samples * sample_rate / sample_rate)
        )
        restored = _match_channels(restored, original_channels)
        save_audio(output_path, restored, sample_rate)
        if removed_output_path is not None:
            removed = _find_removed_stem(results, output_stem)
            if removed is not None:
                removed_audio = _channel_first(removed)
                removed_audio = resample_audio(removed_audio, model_rate, sample_rate)
                removed_audio = _match_length(removed_audio, original_samples)
                removed_audio = _match_channels(removed_audio, original_channels)
                save_audio(removed_output_path, removed_audio, sample_rate)
                return removed_output_path
    except Exception as exc:
        raise PipelineError(f"PyMSS stage {model_name!r} failed: {exc}") from exc
    finally:
        if separator is not None:
            try:
                separator.close()
            except Exception:
                pass
        _cleanup_torch()
    return None


def run_declick(input_path: Path, output_path: Path, params: dict[str, Any]) -> None:
    """Nectar suppression plus optional isolated X-Click; never starts Audacity."""
    from mouth_control import clean_mouth_noises

    audio, rate = load_audio(input_path)
    try:
        result, report = clean_mouth_noises(audio, rate, params)
    except (ValueError, RuntimeError) as exc:
        raise PipelineError(f"Mouth cleanup failed: {exc}") from exc
    save_audio(output_path, result, rate)
    output_path.with_suffix(".clicks.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )


def run_studio_finish(
    input_path: Path, output_path: Path, params: dict[str, Any]
) -> None:
    from audio_plugins import studio_finish

    audio, rate = load_audio(input_path)
    try:
        result, report = studio_finish(audio, rate, params)
    except (ValueError, RuntimeError) as exc:
        raise PipelineError(f"Studio finishing failed: {exc}") from exc
    save_audio(output_path, result, rate)
    output_path.with_suffix(".finish.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
