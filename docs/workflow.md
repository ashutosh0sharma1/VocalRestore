# The fixed workflow

[Overview](../README.md#the-workflow) · [Setup](getting-started.md) · [Configuration](configuration.md) · [Model terms](models.md)

The Studio profile is the established chain below. Restore contributes the integration and protection/recovery logic; the underlying models and plugins are credited separately. Processing preserves the timeline rather than deleting intervals.

1. **Decode** to a separate float WAV, preserving rate and mono/stereo layout. Reject invalid samples, unsupported channel counts, disguised playlists and excessive durations.
2. **Noise model:** established aufr33 safe MelBand Roformer.
3. **Echo model:** established anvuew less aggressive MelBand Roformer.
4. **Automatic breath cleanup:** an isolated Sucial separator process produces aspiration evidence, then exits. Respiro ONNX and (studio profile) Nectar Breath Control provide additional evidence. Voiced guards protect retained singing; attenuation changes amplitude without shortening the timeline.
5. **Mouth cleanup:** paired Nectar Tame Noises renders cancel unwanted level riding. A strict voiced guard limits this suppression. Waves X-Click then reconstructs short impulses, including clicks during voiced passages. The optional AudioJS engine uses autoregressive impulse repair instead.
6. **Gentle finish:** default 35% soothe2 blend, a 30 Hz high-pass and restrained adaptive parallel compression. Portable omits soothe2.
7. **Export:** constant gain toward −18 LUFS, maximum +3 dB boost and −1 dBTP ceiling, PCM24 WAV and 320 kbps MP3. Original frames/rate/channels and finite samples are checked at every stage.

There are no hand-labelled cuts in the normal workflow, no scale-dependent pitch correction, and no hardcoded recording timestamps. All results need listening review; stronger suppression is not automatically better.

## What changes in Portable?

| Stage | Studio | Portable |
| --- | --- | --- |
| Noise / echo | aufr33 / anvuew | Same models |
| Breaths | Sucial + Respiro + Nectar with voiced guards | Sucial + Respiro with voiced guards; no Nectar |
| Mouth clicks | Protected paired Nectar suppression, then Waves X-Click | AudioJS autoregressive click repair; no Nectar or Waves |
| Finish | 35% soothe2 blend, high-pass and parallel dynamics | High-pass and parallel dynamics; no soothe2 |
| Export / saved jobs | WAV + MP3, validated checkpoints and receipts | Same app/export/recovery features |

Portable is experimental and has not demonstrated Studio-equivalent listening results. Both profiles retain the Sucial non-commercial restriction. [Validation](validation.md) explains what has actually been tested.

## Native host details

The aspiration separator runs in a fresh eight-thread process before loading ONNX/VST libraries. This preserves the tested recovery from a historical Windows `torch_cpu.dll` access violation. The precise native trigger was not proved; the app does not pretend it was a model or recording defect.

DawDreamer warms plugins, drains their tails and compensates their reported latency. Waves uses an isolated Pedalboard worker because exact shell-class selection is required. Pedalboard already compensates Waves latency; the worker verifies zero host lag and zero-threshold transparency before repair. Never subtract that latency twice.

Receipts bind the source and frozen configuration to SHA-256-verified checkpoints. A missing or changed stage fails closed instead of silently being reused. JSON replacement retries transient Windows file locks without corrupting the previous receipt.
