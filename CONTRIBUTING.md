# Contributing

Keep Restore small: one fixed workflow, one JSON configuration and a simple local interface. Avoid controls that make users tune model internals before cleaning a recording.

Run `npm run lint`, `npm test` and `npm run build`. Audio behavior changes also need a controlled listening comparison and frame/rate/channel preservation checks. Keep an identical audio control in subjective comparisons. Never describe a sample interval as a verified breath solely because a model detected it.

Do not commit recordings, weights, plugin binaries, API keys, logs, local configuration or generated jobs. Use synthetic fixtures in tests. If you want to share a real recording, obtain the right to publish it first.

Explain the specific problem, resulting behavior, validation and limitations in pull requests. Preserve existing native-worker isolation and latency calibration. Do not add telemetry, automatic cloud audio upload or plugin/license activation workarounds.

Small improvements to accessibility, platform compatibility, reproducibility and licensed alternatives are welcome. A commercially permitted breath model with held-out singing validation is a useful future contribution; lower compute alone is not enough to promote a new default.
