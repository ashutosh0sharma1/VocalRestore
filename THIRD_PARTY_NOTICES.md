# Third-party notices

Restore application code is GPL-3.0-only (see LICENSE). Dependency licenses and model terms remain separate. Dependencies are installed from their own distributions; none of their binaries or model weights are bundled in this source release.

| Project | Role | Upstream license / source |
| --- | --- | --- |
| [PyMSS](https://github.com/pymss-project/pymss) 2.1.3 | Model inference/catalog | MIT (installed distribution metadata); individual models have separate terms |
| [DawDreamer](https://github.com/DBraun/DawDreamer) 0.9.0 | Nectar / soothe2 VST3 host | GPL-3.0 |
| [Pedalboard](https://github.com/spotify/pedalboard) 0.9.24 | Isolated Waves host and compressor | GPL-3.0 |
| [AudioJS denoise](https://github.com/audiojs/denoise/tree/main/packages/denoise-declick) | Optional `@audio/denoise-declick` 0.4.0 / `@audio/lpc` 1.2.0 | MIT; Dmitry Iv. / AudioJS. Versions and registry integrity are in vendor/audiojs/package-lock.json |
| [Respiro-en](https://github.com/ydqmkkx/Respiro-en) / [ONNX export](https://huggingface.co/pbTechLab/respiro-en-onnx) | Breath probability evidence | MIT; original DongYANG / ydqmkkx; conversion by pbTechLab |
| [PyTorch](https://github.com/pytorch/pytorch) | CPU tensor inference | BSD-style |
| [NumPy](https://numpy.org), [SciPy](https://scipy.org) | Array / signal processing | BSD-3-Clause |
| [librosa](https://librosa.org) | Resampling / features | ISC |
| [SoundFile](https://github.com/bastibe/python-soundfile) | Audio I/O | BSD-3-Clause; libsndfile separate LGPL terms |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | Detector runtime | MIT |
| [psutil](https://github.com/giampaolo/psutil) | Owned process / resource monitoring | BSD-3-Clause |
| [FFmpeg](https://ffmpeg.org/legal.html) | Decoding, loudness measurement and export | External installation; LGPL/GPL depends on your build |

**Proprietary plugins:** iZotope Nectar 4, Waves X-Click and oeksound soothe2 must be separately installed and licensed. They are not redistributed here. Their names describe compatibility, not endorsement.

**Model weights:** see [docs/models.md](docs/models.md), especially the non-commercial Sucial aspiration model used in both profiles. The application's source license does not grant rights to any recordings or external weight files.
