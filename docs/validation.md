# Validation and known limits

## Release checks — 4 November 2026

- Final local suite: **54 passed**, including installed native plugins and detector weights. Public CI skips those four installation-dependent cases.
- Python and JavaScript source checks, JSON parsing, and an allowlisted source/private-material scan.
- Unit/API tests cover foreign Origin/Host rejection, mutation tokens, upload validation, one-job ownership, byte-range audio playback, media/path allowlists, cancellation, crash detection, configuration overrides, checkpoint integrity and Unicode audio decoding.
- Audio tests cover no gain riding from paired Nectar renders, voiced guards, silence/antiphase inputs, exact bypass, injected impulse reconstruction, frame preservation, export ceiling and transient Windows JSON locks.
- Installed X-Click, Nectar and Respiro tests are opt-in; public CI does not include proprietary plugins or weights.
- Real browser upload → all studio stages → WAV/MP3 completion on an 8-second stereo vocal excerpt. Reload recovered the job, A/B switched while playing, and a 390px mobile viewport showed no horizontal overflow.
- Public Python dependency pins resolved successfully for Python 3.13. A complete clean-machine installation and non-Windows compatibility have not been tested.
- The rebuilt Windows launcher starts the app and reuses its existing instance. Both installed launcher locations were checked. Original launchers were backed up before replacement.

## Actual short-clip smoke run

An 8.000-second, 44.1 kHz stereo vocal was decoded and processed through the default studio configuration. Output retained 352,800 frames, stereo layout and 44.1 kHz; PCM24 WAV plus MP3 export completed. Measured delivery loudness was −18.00 LUFS and true peak −7.23 dBTP. The original upload was retained.

| Stage | Wall seconds | CPU core-seconds |
| --- | ---: | ---: |
| Noise | 99.63 | 575.09 |
| Echo | 86.94 | 544.53 |
| Breaths | 107.91 | 434.83 |
| Mouth | 18.25 | 9.39 |
| Finish | 5.33 | 2.19 |
| WAV export | 1.54 | 0.16 |

Worker elapsed including decode and export: **323.85 seconds**. Sum of stage CPU time including isolated model/click workers: **1,566.19 core-seconds**. Largest recorded process peak: **2.58 GiB**. This is not total concurrent system RAM and excludes FFmpeg child CPU. Short recordings pay substantial startup/model-chunk costs; this run is not a universal duration multiplier.

## Lightweight click alternative

`@audio/denoise-declick` 0.4.0 is a pinned local MIT-licensed Node engine. Synthetic impulse repair and preservation checks pass. Earlier 40/44-second vocal trials at threshold 8 took about **3.3/4.4 seconds**, **3.7/4.8 CPU core-seconds**, and **133/140 MiB** process peak.

A new blind comparison used the same 10-second chant passage four times: baseline, X-Click, AudioJS and an exact duplicate baseline, with equal boundaries and no independent normalization. Gemini 3.6 Flash reported all passages perceptually indistinguishable. That result **does not establish equal click-removal quality**; earlier comparisons also failed to establish AudioJS as a superior singing default. It remains an explicit experimental option. The studio default stays X-Click 50/60.

A small derivative/smoothing VST alternative changed sustained audio too broadly in earlier trials and was rejected. It is not distributed or used here. Recordings and private listening reports are not included in this repository.

## Limits

Preservation checks cannot certify that every breath is removed or every word is untouched. Fricatives and aspirated consonants can resemble breath noise. Source clipping and lossy watery artifacts may be irreversible. The configured models were not newly trained here; default studio audio behavior is retained from the established workflow. The optional portable profile does not have full perceptual equivalence or a commercial-use clearance.

The new app uses no Gemini/API requests in ordinary cleanup. One development-only listening request used 2,344 tokens; it is not part of the application's runtime or configuration.
