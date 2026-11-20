# Maintainer handoff

Bedroom ReStore 2.1.0 adds the native Windows desktop host and a multi-resolution microphone icon embedded in the executable. Keep the executable filename stable for existing taskbar pins. Source and Windows bundles use the same external audio environment and configuration.

Earlier release 2.0.1. Repository review improved the README with an actual UI screenshot, fixed-workflow diagram, free/separate dependency tables, profile-specific setup, FAQ, roadmap and structured issue/PR templates. See docs/repository-review.md for the assessment against current Pedalboard/UVR/DawDreamer onboarding. No ranking or comparative audio-quality claim.

56 local tests passed, including native checks; lint/build and local documentation links/YAML pass. CI now installs/verifies FFmpeg/ffprobe to eliminate five accidental decode/export skips; four native installation cases remain opt-in. Startup preflight now checks ffprobe as well as ffmpeg. Earlier sandbox-only socket/temp failures are environmental, not audio regressions. Engine files, model choices and config.json were unchanged. The source release remains separate from weights/plugins; no all-in-one installer or public listening corpus is claimed.

Restore 2.0 is a standalone local Python application with a vanilla retro browser UI. It is separate from any parent repository. Preserve the studio defaults and fixed order; all tuning is in config.json plus an ignored .config.local.json override.

Verified 4 November 2026: 54 local tests passed including installed X-Click/Nectar/Respiro checks; real 8-second studio workflow completed, format/frames retained, browser-downloaded WAV matched the rendered file. Desktop/mobile A/B, help and reload were checked. Source lint/build and Python 3.13 dependency resolution pass. See docs/validation.md for timings and limitations. No claim of universal artifact-free audio or clean-machine/non-Windows acceptance.

Native isolation and host latency calibration are deliberate. Do not weaken the voice guard to reach a desired breath count. Preserve source/config-bound hashes and explicit process failures. The HTTP server must remain loopback-only, with Origin/Host checks, mutation token and media allowlists. Launcher and worker watchdogs terminate owned descendants when their parent closes.

AudioJS is an optional pinned lightweight click engine. It passes synthetic repair tests, but blind listening has not established equivalent singing repair quality. Waves remains the studio default. Portable omits Nectar/soothe and is experimental.

Licensing: application GPL-3.0-only; plugins separately licensed. Sucial aspiration weights are CC BY-NC-SA 4.0, including in portable; do not describe the full chain as commercially unrestricted. aufr33 checkpoint-specific commercial terms remain unverified. Weights/audio/plugin binaries/keys/local settings never go into Git or source release archives.

Future priorities: appropriately licensed breath separation with held-out singing validation; broader real-world click labels; clean-machine Windows installation; independent non-Windows testing. No new service, cloud upload or automatic download is needed for normal processing.

The optional marked-WAV helper uses an intact full take, reviewed time ranges and an optional aligned donor. Use sparse annotation exports only to identify timestamps. Completed recordings can be saved immediately, with optional Before/Cleaned playback.

## Windows desktop window

The x64 WinForms/WebView2 host in desktop/ uses the same web assets and local audio engine. Its teal title bar is the native drag region. Source builds use desktop/build.ps1. Both installed launchers use their existing private sidecars. Dropping a replacement asks for confirmation and stopping an active job preserves verified stages. Completed export controls support native Save As and persistent Windows FileDrop copies. Verified native movement, maximize/restore, both incoming replacement choices, and external receipt of byte-identical WAV/MP3 files from a completed studio job.
