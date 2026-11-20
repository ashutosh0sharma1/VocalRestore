"""Apply explicit, reviewed repairs to a time-aligned vocal WAV."""

import argparse
import json

import numpy as np
import soundfile as sf
from scipy.signal import butter, iirpeak, sosfilt, tf2sos


def repair(audio, rate, edits, donor=None):
    if donor is not None and donor.shape != audio.shape:
        raise ValueError("Donor must match source duration and channels")
    result = audio.copy()
    previous_end = 0
    for edit in edits:
        start, end = (round(edit[key] * rate) for key in ("start", "end"))
        if not previous_end <= start < end <= len(audio):
            raise ValueError("Edits must be ordered, disjoint, and inside the WAV")
        previous_end = end
        dry = audio[start:end]
        wet = dry.copy()
        donor_mix = edit.get("donor_mix", 0)
        if not 0 <= donor_mix <= 1:
            raise ValueError("Donor mix must be between zero and one")
        if donor_mix:
            if donor is None:
                raise ValueError("This edit needs a time-aligned donor")
            reference = donor[start:end]
            reference_norm = np.linalg.norm(reference)
            if reference_norm <= 1e-8:
                raise ValueError("Donor is silent in a requested repair")
            matched = reference * (np.linalg.norm(dry) / reference_norm)
            wet = (1 - donor_mix) * wet + donor_mix * matched
        if "highpass_hz" in edit:
            sos = butter(2, edit["highpass_hz"], "highpass", fs=rate, output="sos")
            wet = sosfilt(sos, wet, axis=0)
        for frequency, quality, reduction in edit.get("resonances", []):
            b, a = iirpeak(frequency, quality, fs=rate)
            band = sosfilt(tf2sos(b, a), wet, axis=0)
            wet = wet - (1 - 10 ** (-reduction / 20)) * band
        wet *= 10 ** (-edit.get("attenuation_db", 0) / 20)
        if edit.get("mute"):
            wet.fill(0)
        fade_seconds = 0.04 if donor_mix else 0.015
        fade = min(round(rate * fade_seconds), len(dry) // 2)
        blend = np.ones((len(dry), 1))
        if fade:
            ramp = np.sin(np.linspace(0, np.pi / 2, fade)) ** 2
            blend[:fade, 0] = ramp
            blend[-fade:, 0] = ramp[::-1]
        result[start:end] = dry + blend * (wet - dry)
    if not np.isfinite(result).all() or np.max(np.abs(result)) >= 1:
        raise ValueError("Repair would produce nonfinite or clipped samples")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("edits")
    parser.add_argument("output")
    parser.add_argument("--donor", help="Earlier WAV on the same sample timeline")
    args = parser.parse_args()
    with open(args.edits, encoding="utf-8") as handle:
        edits = json.load(handle)
    audio, rate = sf.read(args.source, always_2d=True)
    donor = None
    if args.donor:
        donor, donor_rate = sf.read(args.donor, always_2d=True)
        if donor_rate != rate:
            raise ValueError("Donor and source sample rates must match")
    repaired = repair(audio, rate, edits, donor)
    with open(args.output, "xb") as handle:
        sf.write(handle, repaired, rate, format="WAV", subtype="FLOAT")
