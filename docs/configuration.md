# Configuration

`config.json` is the complete fixed-chain configuration. An ignored sibling `.config.local.json` can override only the fields you need. Restart the server after editing. Existing jobs retain their own configuration; new settings apply to new jobs.

Example local override:

```json
{
  "model_dir": "D:/AudioModels",
  "respiro_model": "D:/AudioModels/respiro/respiro-en.onnx",
  "output_dir": "D:/RestoreJobs",
  "runtime": {"inference_params": {"cpu_threads": 8}}
}
```

Paths are resolved relative to the configuration file. The app uses CPU inference; `cpu_threads` controls noise/echo. Aspiration runs in its own eight-thread process to preserve the tested native-runtime isolation.

## Profiles

| Profile | Breath / mouth / finish | Status |
| --- | --- | --- |
| `studio` (default) | Sucial + Respiro + Nectar breath; paired Nectar mouth suppression + Waves X-Click; light soothe2 and dynamics | Established local workflow, proprietary VST licenses required |
| `portable` | Sucial + Respiro, AudioJS clicks, gentle high-pass/dynamics | Experimental; different behavior, no proprietary VST required |

Both profiles use the same noise and echo models, and **both currently use the non-commercial Sucial aspiration weight**. Portable does not mean commercially unrestricted or equivalent audio quality. No automatic fallback occurs when a studio plugin is missing.

To try portable, install Node.js 18+ and run `npm ci --prefix vendor/audiojs --ignore-scripts`, then set `"profile": "portable"`. This overrides Nectar/soothe flags and sets the click engine to `audiojs`.

To try only AudioJS while retaining the rest of the studio chain:

```json
{"dsp":{"declick":{"click_repair":{"engine":"audiojs","light_threshold":8}}}}
```

Studio plugin paths live under `plugins`. Waves is a shell: the worker selects the exact `X-Click Mono` / `X-Click Stereo` class. DawDreamer hosts Nectar and soothe2; Pedalboard hosts this shell in an isolated child.

## Useful settings

- `studio_finish.amount`: default `0.35`; zero bypasses finishing.
- `dsp.declick.amount`: default `1.0`; zero bypasses mouth cleanup.
- `dsp.declick.click_repair.enabled`: enables dedicated click reconstruction after protected mouth suppression.
- `dsp.declick.click_repair.threshold/shape`: Waves defaults `50/60`.
- `dsp.declick.click_repair.light_threshold`: AudioJS default `8`; lower thresholds can mistake vocal transients for clicks.
- `breath_control`: the established consensus/voice-guard settings. Aggressive changes may remove aspirated consonants or word tails. Do not assume every detected gap is an unwanted breath.

There is no reordering, pitch correction, manual timestamp cutting, hidden cloud service, or Gemini key in this configuration. Export applies constant gain targeting −18 LUFS, capped at +3 dB and −1 dBTP; a very quiet source may remain below the loudness target.
