# Common questions

## Is Restore free?

The complete application source, interface, workflow and configuration are free under GPL-3.0-only. There is no Restore subscription, per-file fee or paid feature tier. You provide the computer and separately installed dependencies.

The established Studio profile needs paid or otherwise legitimately licensed Nectar 4, Waves X-Click and soothe2. Portable needs no proprietary plugins but uses different processing and is experimental. **Both use a non-commercial Sucial aspiration model**, and the denoise checkpoint's commercial terms still need clarification. Free source code is not a blanket license for every external tool. See [model terms](models.md).

## Can I use it for monetized videos or client work?

This release does not establish that permission for the full configured chain. The app's GPL license permits commercial use of the code subject to its terms, but the Sucial model is labelled CC BY-NC-SA 4.0. Review the model and plugin rights separately and obtain appropriate permission or use a validated, appropriately licensed replacement. Switching to Portable does not remove the model restriction.

## Does it need Gemini, an API key or a GPU subscription?

No. Gemini was used for some development listening comparisons; it is not a processing stage. Normal cleanup runs locally on CPU and makes no API requests. Setup downloads packages and weights; that is separate from processing your recordings.

## What is new here if the models already exist?

Restore packages the tested stage order and settings into a repeatable workflow, adds voice-protection logic, paired plugin renders, host latency handling, process isolation, resumable jobs and a simple comparison interface. Upstream model and tool authors are credited. Restore does not claim to have trained those models.

## Does it remove every click or breath?

No universal guarantee is possible from the validation here. Quiet consonants and intentional aspiration can resemble unwanted breath, while clicks may overlap singing. The chain balances suppression with preservation. Compare the result before replacing a take; retain the original.

## Can it separate a singer from a full song or correct pitch?

The shipped workflow is intended for isolated vocals. It does not include instrumental separation, scale detection or pitch correction. Mixed music may be affected unpredictably. There are no manually labelled breath cuts or recording-specific timestamps in the normal workflow.

## Is Portable a tiny or portable executable?

No. It is the configuration name for the profile without proprietary VSTs. It still requires Python, FFmpeg, Node.js and the separation models. Its AudioJS click step is light; the complete model chain is still computationally expensive.

## Where do my recordings go?

By default, only into `output/jobs` on your computer. That includes the original upload, decoded WAV, intermediate stages, final WAV/MP3 and timing receipts. The app has no telemetry or cloud audio upload. You manage job retention. A local browser interface does not make this a hosted web service; do not expose it to the internet.

## Can I change the chain or contribute a model?

Settings live in `config.json` and an optional ignored `.config.local.json`; stage order is fixed. A model replacement needs both suitable licensing and listening/preservation evidence. [Configuration](configuration.md) · [Contribution guide](../CONTRIBUTING.md) · [Roadmap](roadmap.md)
