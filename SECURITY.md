# Security

Restore is a single-user local application. It binds to `127.0.0.1` only. Do not expose it through a public tunnel, reverse proxy, port-forward or shared-host deployment. Authentication and isolation for remote users are not implemented.

Keep FFmpeg, Python and native plugins up to date through their official sources. Model checkpoints can be executable inputs: use trusted distributions and verify model hashes. No credentials are required for ordinary local processing.

For security problems, use GitHub's private vulnerability reporting when available. Avoid putting a vulnerability exploit, private recording, local filesystem path, log containing private data, or a credential in a public issue. General bug reports can use synthetic fixtures.
