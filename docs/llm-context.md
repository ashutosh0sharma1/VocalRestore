# Maintainer handoff

Restore 2.0 is a standalone local Python application with a vanilla retro browser UI. It is separate from any parent repository. Preserve the studio defaults and fixed order; all tuning is in config.json plus an ignored .config.local.json override.

Verified 4 November 2026: 54 local tests passed including installed X-Click/Nectar/Respiro checks; real 8-second studio workflow completed, format/frames retained, browser-downloaded WAV matched the rendered file. Desktop/mobile A/B, help and reload were checked. Source lint/build and Python 3.13 dependency resolution pass. See docs/validation.md for timings and limitations. No claim of universal artifact-free audio or clean-machine/non-Windows acceptance.

Native isolation and host latency calibration are deliberate. Do not weaken the voice guard to reach a desired breath count. Preserve source/config-bound hashes and explicit process failures. The HTTP server must remain loopback-only, with Origin/Host checks, mutation token and media allowlists. Launcher and worker watchdogs terminate owned descendants when their parent closes.

AudioJS is an optional pinned lightweight click engine. It passes synthetic repair tests, but blind listening has not established equivalent singing repair quality. Waves remains the studio default. Portable omits Nectar/soothe and is experimental.

Licensing: application GPL-3.0-only; plugins separately licensed. Sucial aspiration weights are CC BY-NC-SA 4.0, including in portable; do not describe the full chain as commercially unrestricted. aufr33 checkpoint-specific commercial terms remain unverified. Weights/audio/plugin binaries/keys/local settings never go into Git or source release archives.

Future priorities: appropriately licensed breath separation with held-out singing validation; broader real-world click labels; clean-machine Windows installation; independent non-Windows testing. No new service, cloud upload or automatic download is needed for normal processing.
