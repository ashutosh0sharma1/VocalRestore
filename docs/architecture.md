# Architecture

```text
web/                    Vanilla UI, real waveform, synchronized A/B
  ↓ loopback HTTP
restore.py              Upload limits, local-only checks, job ownership
  ↓ one fresh subprocess per recording
worker.py               Decode, validation, explicit success/failure
  ↓
engine/approved_delivery.py
  ├─ PyMSS noise / echo
  ├─ isolated_breath.py → PyMSS child → Respiro / Nectar / voice guard
  ├─ mouth_control.py → Nectar → isolated Waves (or optional AudioJS)
  ├─ audio_plugins.py → light finish
  └─ PCM24 / MP3 / source-bound receipt
```

`settings.py` merges JSON and validates/preflights runtime dependencies. The server does not load model weights into its own process. A job owns its upload, frozen configuration, worker log, decoded original, stage WAVs and receipt. Native crashes are detected from process exit; cancelling terminates the owned worker tree. A parent watchdog prevents surviving inference children after the app is abruptly closed. A filesystem lock prevents two servers managing the same job directory.

Only loopback is supported. Host/Origin checks, same-origin resource policy, a per-launch mutation token, extension/demuxer restrictions and explicit static/media allowlists constrain the local HTTP surface. There is no arbitrary filesystem browser, remote path input or HTTP configuration mutation. This is not a multi-user server or a supported public deployment.

The source release builder uses an allowlist and a private-material scan. CI runs without recordings, model weights, VST binaries or cloud credentials. Native plugin checks and real-model acceptance are separate local gates.
