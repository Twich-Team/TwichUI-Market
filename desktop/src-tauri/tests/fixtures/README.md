These are synthetic, non-executable updater verification fixtures. The public key
and version-bound signature authenticate only the 1 KiB text test payload. They
are never embedded as a production update trust key. No private key is committed.

Generated with the repository-pinned Tauri CLI using an ephemeral local test key
and `signer sign --app-version 2.0.0`. Windows unit acceptance invokes the actual
supported updater to verify the payload, reject altered bytes, reject inflated
version metadata and preserve its ordinary newer-version comparison. The mock
runtime supplies application metadata only; no installation/network is attempted.
This does not establish owner signing, Authenticode or a signed production release.
