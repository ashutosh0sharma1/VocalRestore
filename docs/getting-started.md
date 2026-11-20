# Set up Restore on Windows

[Back to the overview](../README.md) · [Model terms](models.md) · [Configuration](configuration.md)

The source and Windows x64 release archives both contain the application source. The Windows archive also includes the compiled desktop host. It does not bundle Python, FFmpeg, models or commercial plugins. Windows x64 with Python 3.13 and CPU inference is the tested environment; the full Studio setup has not yet been repeated on a clean machine.

## 1. Get the source and prerequisites

Download and extract the source ZIP from [Releases](https://github.com/ashutosh0sharma1/VocalRestore/releases/latest), or clone:

```powershell
git clone https://github.com/ashutosh0sharma1/VocalRestore.git
cd VocalRestore
```

If you extracted a ZIP, open PowerShell in its folder containing `restore.py`. Run the following commands from that folder.

Install **64-bit Python 3.13** from [python.org](https://www.python.org/downloads/windows/) and **FFmpeg** from a Windows build linked by [ffmpeg.org](https://ffmpeg.org/download.html). Both `ffmpeg` and `ffprobe` must be on PATH. Reopen PowerShell after changing PATH, then check:

```powershell
python --version
ffmpeg -version
ffprobe -version
```

Use a modern multi-core CPU; 16 GB RAM is recommended. Allow about 2.66 GB for the separator weights, plus Respiro, Python dependencies, original audio and intermediate stages. This is not real-time cleanup; [measured times](validation.md) show the cost of the current models.

## 2. Install the Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python -m pip install -r requirements.txt
```

These commands use the environment directly, so no PowerShell activation-policy change is needed. Do not substitute an arbitrary Python version when reporting a reproducibility problem.

## 3. Choose one profile

Both profiles use the same noise, echo and aspiration weights. The Sucial aspiration model is **CC BY-NC-SA 4.0**; the denoise checkpoint's commercial-use permission is unresolved. Read [model terms](models.md) before downloading or using them. A profile without paid plugins is not automatically cleared for monetized work.

### Studio: established workflow

Studio is already selected in `config.json`. Install and activate your own VST3 copies of:

- iZotope Nectar 4 **Breath Control** and **Auto-Level** modules.
- Waves **X-Click**; the tested host uses WaveShell 15.5 and selects its exact Mono/Stereo class.
- oeksound **soothe2**.

The public defaults use standard Windows VST3 paths. If your paths differ, create `.config.local.json` next to `config.json` and override just the relevant paths. For example:

```json
{
  "plugins": {
    "xclick": "D:/VST3/WaveShell1-VST3 15.5_x64.vst3"
  }
}
```

Replace that example with your real location. A different plugin version or shell requires validation; changing the filename alone does not prove compatibility. Node.js is unnecessary for the default Studio runtime. Continue to step 4.

### Portable: no proprietary plugins

Portable uses Sucial + Respiro for breath cleanup, AudioJS for clicks, and a simpler finish. It omits Nectar and soothe2. It is **experimental**: listening comparisons have not established Studio-equivalent cleanup, and it retains the same model restrictions.

Install [Node.js](https://nodejs.org/) 18 or newer (a supported LTS is preferable), then:

```powershell
npm ci --prefix vendor/audiojs --ignore-scripts
```

Create `.config.local.json` next to `config.json` containing:

```json
{
  "profile": "portable"
}
```

If you already have that file, merge the field into it rather than replacing your existing paths. The profile automatically disables the proprietary effects and selects AudioJS. It does not download or activate plugins.

## 4. Download the models explicitly

After reviewing their terms, run:

```powershell
.\.venv\Scripts\python setup_models.py
```

This step uses the internet to download the configured weights. It verifies them against the pinned provenance described in [models](models.md). Ordinary cleanup does not download models or send audio to a cloud service. You can reuse existing weights through the [local path overrides](configuration.md).

## 5. Clean a first recording

With the Windows x64 archive, double-click the top-level VocalRestore.exe after completing the setup above. For a source checkout, build the desktop window once from the repository root:

```powershell
.\desktop\build.ps1
```

Double-click `dist\desktop\VocalRestore.exe`. It uses the installed Edge WebView2 Runtime, the existing Python environment and your configured models. Drop one recording anywhere in the window. Dropping another asks before switching. After cleanup, click Save WAV or Save MP3 for a file dialog, or drag the button into a folder or an audio editor. Dragged files remain under the job’s exports folder for editors that reference them. To use the browser interface separately, run `.\.venv\Scripts\python restore.py`.

1. Choose a short isolated vocal to begin with. Supported inputs are mono/stereo WAV, MP3, FLAC, M4A, OGG and AIFF, 16–96 kHz, 1 second–30 minutes, up to 512 MB.
2. Click **Clean vocal** and wait for the fixed stages to finish. Missing prerequisites are shown before processing; Restore does not silently fall back to another profile.
3. Compare **Before / Cleaned**, especially word endings and quiet consonants. Download the 24-bit WAV for further editing or the 320 kbps MP3 for convenient playback.

Jobs stay in `output/jobs` by default, including the original upload, intermediate stages and receipts. There is no automatic retention cleanup. Close the app and remove only completed job folders you no longer need. Do not commit or upload these folders.

## Troubleshooting

| Symptom | Check or action |
| --- | --- |
| Python package missing | Install with `.\.venv\Scripts\python -m pip ...`, then launch with that same Python. `RESTORE_PYTHON` can select a different environment. |
| FFmpeg or ffprobe missing | Both executables must resolve in the terminal that launches Restore. Reopen the terminal after updating PATH. |
| Models missing | Run `setup_models.py` with the same config/environment, or correct `model_dir` and `respiro_model`. Never bypass a checksum mismatch. |
| Studio plugin missing | Check the installed VST3 path, module and activation. Choose Portable explicitly if you want its different workflow. |
| Address already in use | Return to an already running Restore instance, or run `.\.venv\Scripts\python restore.py --port 8532` if another app owns the default port. Do not start two servers against the same active jobs directory. |
| A recording was interrupted | Reopen Restore and choose **Resume** in the saved job. Source, configuration and completed-stage hashes must match. |
| New JSON settings seem ignored | Restart the app and start a new job. A resumed job deliberately uses its original frozen configuration. |
| Cleanup is slow | Check [actual timings](validation.md), available RAM and background CPU load. Lower `cpu_threads` if needed for machine responsiveness; it does not guarantee faster processing. |
| A word ending sounds damaged | Keep the original and report the profile, stage and time range. Increasing suppression can remove intended sounds; see the [audio-quality issue form](https://github.com/ashutosh0sharma1/VocalRestore/issues/new/choose). |

For a report, include your OS, Python version, Restore version, profile and a redacted error. Never post credentials, activation data, private recordings or full job folders. See [Contributing](../CONTRIBUTING.md).
