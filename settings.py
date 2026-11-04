"""One validated JSON configuration, with an optional ignored local override."""

from pathlib import Path
import copy
import json
import math

ROOT = Path(__file__).resolve().parent


def merge(base, override):
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = value
    return result


def load(path=None, local=True):
    path = Path(path or ROOT / "config.json").resolve()
    config = json.loads(path.read_text(encoding="utf-8"))
    override = path.with_name(".config.local.json")
    if local and override.is_file():
        config = merge(config, json.loads(override.read_text(encoding="utf-8")))
    if config.get("profile") not in ("studio", "portable"):
        raise ValueError("profile must be studio or portable")
    threads = config["runtime"]["inference_params"]["cpu_threads"]
    if type(threads) is not int or not 1 <= threads <= 64:
        raise ValueError("cpu_threads must be an integer from 1 to 64")
    for name, value, lo, hi in [
        ("finish amount", config["studio_finish"]["amount"], 0, 1),
        ("mouth amount", config["dsp"]["declick"]["amount"], 0, 1),
        ("breath reduction", config["breath_control"]["reduction_db"], 0, 80),
    ]:
        if (
            not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not lo <= value <= hi
        ):
            raise ValueError(f"Invalid {name}")
    repair = config["dsp"]["declick"]["click_repair"]
    if repair.get("engine", "waves") not in ("waves", "audiojs"):
        raise ValueError("click_repair.engine must be waves or audiojs")
    if config["profile"] == "portable":
        config["breath_control"]["nectar_enabled"] = False
        config["dsp"]["declick"]["nectar_enabled"] = False
        repair["engine"] = "audiojs"
        config["studio_finish"]["soothe_enabled"] = False
    for key in ("model_dir", "respiro_model", "output_dir"):
        p = Path(config[key]).expanduser()
        config[key] = str(
            (path.parent / p).resolve() if not p.is_absolute() else p.resolve()
        )
    config["breath_control"]["respiro_model"] = config["respiro_model"]
    config["breath_control"]["nectar_path"] = config["plugins"]["nectar_breath"]
    config["dsp"]["declick"]["plugin_path"] = config["plugins"]["nectar_mouth"]
    repair["plugin_path"] = config["plugins"]["xclick"]
    config["studio_finish"]["soothe_path"] = config["plugins"]["soothe"]
    if config["breath_control"].get("mode") != "automatic":
        raise ValueError("The fixed workflow requires automatic breath mode")

    def finite_tree(value):
        if isinstance(value, dict):
            for item in value.values():
                finite_tree(item)
        elif isinstance(value, list):
            for item in value:
                finite_tree(item)
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Configuration numbers must be finite")

    finite_tree(config)
    return config


def preflight(config):
    import importlib.util
    import shutil

    issues = []
    for module in (
        "numpy",
        "scipy",
        "soundfile",
        "pymss",
        "onnxruntime",
        "librosa",
        "psutil",
        "pedalboard",
    ):
        if importlib.util.find_spec(module) is None:
            issues.append(f"Install Python dependency: {module}")
    if not shutil.which("ffmpeg"):
        issues.append("Install FFmpeg and add it to PATH")
    model_dir = Path(config["model_dir"])
    for key in ("denoise_safe", "dereverb_safe", "aspiration_strong"):
        name = config["models"][key]["name"]
        if not model_dir.is_dir() or not any(model_dir.rglob(name + ".ckpt")):
            issues.append(f"Missing model: {name}. Run python setup_models.py")
    if not Path(config["respiro_model"]).is_file():
        issues.append("Missing Respiro ONNX detector. Run python setup_models.py")
    mouth = config["dsp"]["declick"]
    plugin_paths = []
    if config["breath_control"].get("nectar_enabled", True):
        plugin_paths.append(config["plugins"]["nectar_breath"])
    if mouth.get("nectar_enabled", True):
        plugin_paths.append(config["plugins"]["nectar_mouth"])
    if (
        mouth["click_repair"].get("enabled", True)
        and mouth["click_repair"].get("engine", "waves") == "waves"
    ):
        plugin_paths.append(config["plugins"]["xclick"])
    if config["studio_finish"].get("soothe_enabled", True):
        plugin_paths.append(config["plugins"]["soothe"])
    if plugin_paths and importlib.util.find_spec("dawdreamer") is None:
        issues.append("Install DawDreamer for the studio profile")
    issues.extend(
        f"Missing studio plugin: {Path(p).name}"
        for p in plugin_paths
        if not Path(p).exists()
    )
    if mouth["click_repair"].get("engine") == "audiojs":
        if (
            not shutil.which("node")
            or not (
                ROOT / "vendor/audiojs/node_modules/@audio/denoise-declick/package.json"
            ).is_file()
        ):
            issues.append(
                "Install Node.js, then npm ci --prefix vendor/audiojs --ignore-scripts"
            )
    return issues
