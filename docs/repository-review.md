# Repository review — 4 November 2026

## Assessment

Restore has a credible foundation for a small public audio application: a working fixed workflow, source releases, CI, regression checks, separate licensing notes and documented limitations. It does not yet have the installation maturity, broad compatibility evidence or public listening examples of an established audio project. Presentation can be improved now; those remaining engineering and evidence gaps cannot be solved by stronger marketing.

This is a qualitative review of onboarding, transparency and maintainability. It is not a ranking by stars, a security audit or a claim that Restore beats other tools in sound quality.

## Reference points

Reviewed the public repository pages on 4 November 2026:

- [Spotify Pedalboard](https://github.com/spotify/pedalboard): concise purpose, installation guidance, a compatibility section, runnable examples and contribution routes. Its install and platform evidence are useful standards for library onboarding.
- [Ultimate Vocal Remover](https://github.com/Anjok07/ultimatevocalremovergui): prominent packaged downloads and platform-specific installation instructions. That makes the path from visitor to usable app clearer than a source-only release.
- [DawDreamer](https://github.com/DBraun/DawDreamer): explicit requirements, API documentation and a runnable synthetic example. It makes capabilities inspectable without needing a user's private recording.

These projects serve different purposes. They are reference points for repository usability, not direct restoration benchmarks or endorsements.

## Findings and response

| Area | Finding | Response |
| --- | --- | --- |
| First impression | An illustrated cover was present, but no actual application screenshot. | Show the real interface and a concise choose/clean/compare/download path. |
| Value of the release | Features were listed; the shared integration work and free offering were less explicit. | Explain the orchestration, guards, recovery, configuration and source freedoms. |
| Licensing and cost | Important restrictions were already disclosed, but a reader could still confuse free code with a free full Studio setup. | Add included/separate tables and direct Studio/Portable choices; retain the non-commercial model disclosure near the top. |
| Setup | A single short sequence mixed app setup and Studio dependencies. | Add a step-by-step Windows guide, profile-specific steps and symptom-based troubleshooting. |
| Workflow | Exact stages existed in deeper documentation. | Put a diagram and stage summary in the README, with deeper implementation details one click away. |
| Test visibility | Local native tests passed; the first public CI also skipped five FFmpeg-dependent cases. | Install and verify FFmpeg/ffprobe in CI, retaining only explicit native-installation skips. See the linked run in validation for the actual result. |
| Setup diagnostics | Preflight checked FFmpeg but omitted ffprobe, which decoding also needs. | Check both tools before processing and cover each missing-tool case. |
| Contributions | General guidance existed without structured reports. | Add setup/bug and audio-quality forms, a focused PR template and evidence-based priorities. |

## Still open

The release is not an all-in-one installer, Portable has not demonstrated equivalent quality, full commercial permission is not established, and macOS/Linux are unverified. Real recording benchmarks remain private. [Roadmap](roadmap.md) lists the evidence needed to improve those areas; [validation](validation.md) separates measured results from claims.

No audio algorithm or approved default was changed by this repository-presentation review.
