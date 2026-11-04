# Model and plugin terms

The app's GPL-3.0 license covers its code. It does not replace the separate licenses of external models, plugin software or recordings. No model weights or VST binaries are distributed in this repository or source release.

**Commercial-use limitation:** the configured Sucial aspiration model is labelled **CC BY-NC-SA 4.0**, including the strong checkpoint used by both profiles. This release does not establish permission to use it for paid services or monetized recordings. Obtain appropriate permission from the rights holder or validate an appropriately licensed replacement before that use. SingAlign research weights are not used or shipped.

| Component | Configured model / use | Provenance and terms |
| --- | --- | --- |
| Noise | `denoise_mel_band_roformer_aufr33_sdr_27.9959` / `dry` | aufr33 model, acquired through the pinned [PyMSS](https://github.com/pymss-project/pymss) catalog. Checkpoint-specific commercial permission was not independently established in this release. A catalog mirror is not a license grant. |
| Echo | `dereverb_mel_band_roformer_less_aggressive_anvuew_sdr_18.8050` / `noreverb` | [anvuew model card](https://huggingface.co/anvuew/dereverb_mel_band_roformer), labelled GPL-3.0. The less aggressive checkpoint is retained for the existing workflow. |
| Aspiration | `aspiration_mel_band_roformer_sdr_18.9845` / `other` plus complementary aspiration | [Sucial model card](https://huggingface.co/Sucial/Aspiration_Mel_Band_Roformer), labelled CC BY-NC-SA 4.0. Non-commercial restriction applies. |
| Breath detector | Respiro-en ONNX | [pbTechLab conversion](https://huggingface.co/pbTechLab/respiro-en-onnx), MIT; original [ydqmkkx/Respiro-en](https://github.com/ydqmkkx/Respiro-en). Trained on English speech; singing/generalization is not guaranteed. |
| Studio VSTs | Nectar 4 Breath Control, Nectar 4 Auto-Level Tame Noises, Waves X-Click, soothe2 | Proprietary; install and license separately from their vendors. No activation bypass, binary redistribution or automatic purchase. |

`setup_models.py` explicitly downloads the three PyMSS entries with available catalog verification. Respiro is pinned to revision `c6901b7500c78b8274a140d59a0ecbecc205959b` and checked against SHA-256 `3ccc55d4130b2465f8a7975178a30317d45babb7de5e7b3533fae1810c9b7138`. Its README and license are saved alongside the model.

[`model-manifest.json`](model-manifest.json) records the three separator hashes and sizes from the tested installation. Downloaded pickle-based weights are executable inputs: obtain them only from trusted upstream distribution and do not substitute untrusted checkpoints. Model setup is a separate, explicit operation; ordinary cleanup performs no downloads.

Terms reviewed 4 November 2026. Verify upstream terms for your intended use. Software/model quality and licensing are separate questions.
