# Pinned Windows upgrade baseline

`legacy-0.1.0-unsigned-setup.exe` is the exact already-verified0.1.0 engineering installer from sourceab1c886/run43542957765/artifact14092971157. Its immutable bytes, SHA256 and source are in `legacy-0.1.0.json`; the Windows upgrade driver additionally pins that digest before execution.

The3.68MB baseline is retained here so future compatibility tests survive expiry of the original private CI artifact. It is used only on disposable Windows CI with an isolated synthetic profile. It is unsigned, not a stable/user release, never a setup-guide download, and never included in the packaged companion assets. No signing trust, owner approval or current-version readiness is implied. Do not regenerate or replace it under this name; a different baseline requires its own provenance and digest.
