# Validation and known limits

## 2.0.1 repository and setup checks — 4 November 2026

- **56 local tests passed**, including the installed X-Click, Nectar and Respiro checks and two new missing-tool preflight cases. Lint and source build passed.
- Public CI now installs and verifies both FFmpeg and ffprobe before testing. Only the four proprietary-plugin/detector installation tests are intentionally opt-in. Actual hosted results are linked from [Source checks](https://github.com/ashutosh0sharma1/VocalRestore/actions/workflows/checks.yml) and the [2.0.1 release](https://github.com/ashutosh0sharma1/VocalRestore/releases/tag/v2.0.1).
- Local documentation links and GitHub YAML were checked. The README image is a real, unedited app screenshot with no recording content.
- No audio-engine files, model choices or default configuration changed. No new full-recording render or perceptual-quality claim is implied by this documentation/setup patch.
- An initial test attempt inside a restricted Windows sandbox failed on loopback socket access and temporary-file permissions. The same suite passed with normal local access; those failures were test-environment restrictions. Separately, preflight's missing ffprobe check was an application setup gap and is fixed here.

## Original 2.0.0 release checks — 4 November 2026

- Final local suite: **54 passed**, including installed native plugins and detector weights. The [first public CI run](https://github.com/ashutosh0sharma1/VocalRestore/actions/runs/41825418541) passed **45 tests and skipped 9**: four native-installation cases and five FFmpeg-dependent cases. The 2.0.1 CI configuration installs and verifies FFmpeg/ffprobe to close the latter gap.
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

For a marked vocal repair, use scripts/repair_marked.py with a WAV, an ordered
JSON list of reviewed time ranges, and a new output WAV path. Each range has
start and end in seconds, with optional attenuation_db, highpass_hz, or
resonances (lists of frequency in Hz, Q, and reduction in dB). Inspect the
marked locations before choosing a treatment. Quiet isolated breaths can
take much stronger attenuation than a region overlapping a sung word.
Compare the same timestamps at the same playback gain. Keep uncertain
voiced sounds as review items when gentle EQ does not resolve them.

Restore makes downloads available when rendering finishes. Playback and A/B
comparison are optional. For deliveries that need listening sign-off, record
review coverage separately. Export checks and spot samples cannot clear the
whole file.

For voiced damage, compare saved stages before applying any reduction.
A reviewed range may use donor_mix (0 to 1) with --donor pointing to an
earlier, time-aligned WAV. Restore matches the donor level per range and
crossfades the boundaries. Listen for any backing bleed returning with
the earlier stem. Use mute only on confirmed isolated breath/noise
ranges with room for the short edge fades.
