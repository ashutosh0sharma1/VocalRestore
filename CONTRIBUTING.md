# Contributing

Keep Restore small: one fixed workflow, one JSON configuration and a simple local interface. Avoid controls that make users tune model internals before cleaning a recording.

## Where to start

Read the [setup guide](docs/getting-started.md), [architecture](docs/architecture.md) and [roadmap](docs/roadmap.md). Small documentation, accessibility and setup fixes are welcome. For an audio-engine replacement, first explain the defect, the proposed alternative and its license before investing in a broad rewrite.

Use the [issue forms](https://github.com/ashutosh0sharma1/VocalRestore/issues/new/choose) for setup failures or audio-quality reports. Include the version/commit, OS, Python version, profile, reproduction steps and a redacted error. For audio, give a time range and distinguish a remaining artifact from a damaged intended sound. An AI label alone is not ground truth.

## Validate a change

Run `npm run lint`, `npm test` and `npm run build`. Audio behavior changes also need a controlled listening comparison and frame/rate/channel preservation checks. Keep an identical audio control in subjective comparisons. Never describe a sample interval as a verified breath solely because a model detected it.

Do not commit recordings, weights, plugin binaries, API keys, logs, local configuration or generated jobs. Use synthetic fixtures in tests. If you want to share a real recording, obtain the right to publish it first.

Explain the specific problem, resulting behavior, validation and limitations in pull requests. Preserve existing native-worker isolation and latency calibration. Do not add telemetry, automatic cloud audio upload or plugin/license activation workarounds.

Small improvements to accessibility, platform compatibility, reproducibility and licensed alternatives are welcome. A commercially permitted breath model with held-out singing validation is a useful future contribution; lower compute alone is not enough to promote a new default.

CI installs FFmpeg and the test dependencies, but deliberately excludes proprietary plugins and model weights. Run native checks locally with `RESTORE_NATIVE_TESTS=1` only when those dependencies are present. Clearly report skipped checks; a green synthetic test does not prove equal perceptual quality.

## Working together

Be specific and respectful in issues and reviews. Critique the behavior or evidence, not the person. Do not post another person's private information or recordings. Contributions use the repository's GPL-3.0-only code license; preserve attribution and document any new dependency's separate terms. No response-time or platform-support guarantee is implied.
