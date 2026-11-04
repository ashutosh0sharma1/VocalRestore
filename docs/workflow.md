# The fixed workflow

1. **Decode** to a separate float WAV, preserving rate and mono/stereo layout. Reject invalid samples, unsupported channel counts, disguised playlists and excessive durations.
2. **Noise model:** established aufr33 safe MelBand Roformer.
3. **Echo model:** established anvuew less aggressive MelBand Roformer.
4. **Automatic breath cleanup:** an isolated Sucial separator process produces aspiration evidence, then exits. Respiro ONNX and (studio profile) Nectar Breath Control provide additional evidence. Voiced guards protect retained singing; attenuation changes amplitude without shortening the timeline.
5. **Mouth cleanup:** paired Nectar Tame Noises renders cancel unwanted level riding. A strict voiced guard limits this suppression. Waves X-Click then reconstructs short impulses, including clicks during voiced passages. The optional AudioJS engine uses autoregressive impulse repair instead.
6. **Gentle finish:** default 35% soothe2 blend, a 30 Hz high-pass and restrained adaptive parallel compression. Portable omits soothe2.
7. **Export:** constant gain toward −18 LUFS, maximum +3 dB boost and −1 dBTP ceiling, PCM24 WAV and 320 kbps MP3. Original frames/rate/channels and finite samples are checked at every stage.

There are no hand-labelled cuts in the normal workflow, no scale-dependent pitch correction, and no hardcoded recording timestamps. All results need listening review; stronger suppression is not automatically better.

## Native host details

The aspiration separator runs in a fresh eight-thread process before loading ONNX/VST libraries. This preserves the tested recovery from a historical Windows `torch_cpu.dll` access violation. The precise native trigger was not proved; the app does not pretend it was a model or recording defect.

DawDreamer warms plugins, drains their tails and compensates their reported latency. Waves uses an isolated Pedalboard worker because exact shell-class selection is required. Pedalboard already compensates Waves latency; the worker verifies zero host lag and zero-threshold transparency before repair. Never subtract that latency twice.

Receipts bind the source and frozen configuration to SHA-256-verified checkpoints. A missing or changed stage fails closed instead of silently being reused. JSON replacement retries transient Windows file locks without corrupting the previous receipt.
