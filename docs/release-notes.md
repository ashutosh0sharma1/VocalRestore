# Restore 2.0.1

Clearer onboarding and a more transparent public repository, with the same established audio workflow.

- Shows the real interface, the full workflow, and exactly which application features and source are free.
- Adds separate Studio and Portable setup instructions, troubleshooting, FAQ, contribution forms and an evidence-based roadmap.
- Fixes a setup check: `ffprobe` is now required before processing, alongside FFmpeg. Previously an incomplete FFmpeg installation could pass that check and fail when decoding began.
- Installs FFmpeg in public CI so decode and export tests run; proprietary-plugin/model tests remain opt-in.
- Preserves all audio-engine code, model choices and default processing settings.

This remains a **source release**. Studio effects are separately licensed, Portable is experimental, and both profiles use a non-commercial Sucial model. See [setup](getting-started.md), [model terms](models.md), [validation](validation.md) and the [repository review](repository-review.md).

---

# Restore 2.0.0

A small local vocal-cleanup app with a retro interface. Drop a recording, run the fixed workflow, compare Before / Cleaned at the same position, and save a 24-bit WAV or 320 kbps MP3.

- Replaces the Streamlit editor with vanilla HTML/CSS/JavaScript and a local Python server.
- Retains the established studio processing and moves settings into JSON.
- Adds saved jobs, verified resume, explicit crash reporting, cancellation, single-instance protection and owned-process shutdown.
- Adds an optional pinned MIT AudioJS click-repair engine, labelled experimental for singing.
- Includes source, setup instructions, configuration/model documentation, tests and an allowlisted release builder.

Validation: 54 local tests passed, including installed plugin/detector checks. A real studio audio run and browser upload/playback/download checks completed; source lint/build and dependency resolution passed.

**This is a source release, not a bundled one-click model/plugin installer.** Windows/Python 3.13 is tested. Install dependencies and external weights as described in the README. Studio needs your own licensed Nectar, X-Click and soothe2 plugins. No recordings, model weights, proprietary binaries or credentials are included.

**Model terms matter:** both profiles currently use the non-commercial Sucial aspiration checkpoint. The app's GPL-3.0 license does not override that restriction. AudioJS is not claimed to equal X-Click on all singing. See docs/models.md and docs/validation.md.
