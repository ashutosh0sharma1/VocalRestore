"""DawDreamer offline VST3 host with explicit delay compensation and readback."""

from pathlib import Path
import re
import math
import numpy as np
import dawdreamer as daw


def normalized_name(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def render_vst(audio, rate, path, settings):
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim != 2 or not audio.shape[-1] or not np.isfinite(audio).all():
        raise ValueError("Finite nonempty channel-first audio required")
    if not Path(path).exists():
        raise ValueError(f"Required installed VST3 missing: {path}")
    engine = daw.RenderEngine(float(rate), 512)
    effect = engine.make_plugin_processor("effect", str(path))
    effect.disable_nonmain_buses()
    original_channels = audio.shape[0]
    layout = (effect.get_num_input_channels(), effect.get_num_output_channels())
    if layout != (original_channels, original_channels):
        if effect.can_set_bus(original_channels, original_channels):
            effect.set_bus(original_channels, original_channels)
        elif original_channels == 1 and layout[1] == 2 and layout[0] >= 2:
            audio = np.repeat(audio, 2, axis=0)
        elif layout[1] == original_channels and layout[0] >= original_channels:
            pass  # Fixed main layout with extra sidechain inputs.
        else:
            raise ValueError("VST3 cannot preserve source channel layout")
    descriptions = effect.get_parameters_description()
    by_name = {normalized_name(p["name"]): p for p in descriptions}
    applied = {}
    for key, value in settings.items():
        name = key if key in by_name else re.sub(r"_(db|hz)$", "", key)
        if name not in by_name:
            raise ValueError(f"VST3 parameter is missing: {key}")
        index = by_name[name]["index"]
        if isinstance(value, bool):
            target = "on" if value else "off"
            matches = (
                [0.0]
                if by_name[name]["min"].lower() == target
                else ([1.0] if by_name[name]["max"].lower() == target else [])
            )
        elif isinstance(value, str):
            choices = effect.get_parameter_range(index, 1000, convert=False)
            matches = [
                (lo + hi) / 2
                for (lo, hi), text in choices.items()
                if str(text).strip().lower() == value.lower()
            ]
        else:
            if not math.isfinite(float(value)):
                raise ValueError("Plugin parameter must be finite")

            def numeric(text):
                match = re.match(
                    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+|inf)", str(text).lower()
                )
                if not match:
                    raise ValueError(f"Non-numeric parameter: {key}")
                return float(match.group())

            low, high = 0.0, 1.0
            # Plugin text readback handles nonlinear mappings and avoids tiny
            # accidental gain/pan offsets from coarse parameter-range bins.
            try:
                default = numeric(by_name[name]["defaultValueText"])
            except ValueError:
                default = None
            if default is not None and default == float(value):
                middle = by_name[name]["defaultValue"]
            else:
                for _ in range(28):
                    middle = (low + high) / 2
                    effect.set_parameter(index, middle)
                    actual = numeric(effect.get_parameter_text(index))
                    if abs(actual - float(value)) < 0.005:
                        break
                    if actual < float(value):
                        low = middle
                    else:
                        high = middle
            matches = [middle]
        if not matches:
            raise ValueError(f"Unsupported VST3 parameter value: {key}={value}")
        effect.set_parameter(index, matches[0])
        applied[key] = dict(
            requested=value,
            normalized=float(effect.get_parameter(index)),
            readback=effect.get_parameter_text(index),
        )
    # DawDreamer exposes plugin latency but does not compensate it. Warm up
    # with1s silence, drain2s, then crop reported delay AFTER preparation/render.
    warm = int(rate)
    main_channels = audio.shape[0]
    inputs = effect.get_num_input_channels()
    padded = np.pad(audio, ((0, max(0, inputs - main_channels)), (warm, 2 * int(rate))))
    playback = engine.make_playback_processor("source", padded)
    effect.record = True
    if not engine.load_graph([(playback, []), (effect, ["source"])]):
        raise RuntimeError("DawDreamer rejected VST3 processing graph")
    if not engine.render(padded.shape[-1] / rate):
        raise RuntimeError("DawDreamer render failed")
    output = effect.get_audio()
    latency = effect.get_latency_samples()
    result = output[:, warm + latency : warm + latency + audio.shape[-1]]
    if (
        result.shape != (main_channels, audio.shape[-1])
        or not np.isfinite(result).all()
    ):
        raise RuntimeError("DawDreamer returned incomplete or invalid audio")
    result = result[:original_channels]
    return result.astype(np.float32), dict(
        host="DawDreamer",
        host_version=daw.__version__,
        plugin_path=str(path),
        latency_samples_compensated=latency,
        reported_latency_samples=latency,
        parameters=applied,
    )
