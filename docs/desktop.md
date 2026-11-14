# Windows companion

Status: Linux core/HTTP tests and Windows CI core/native credential/HTTP/NSIS build pass. Windows workflow 43530807214 uploaded the installer artifact. Installer execution and native UI interactions on a Windows desktop remain unverified. No main addon repository changes or live SavedVariables writes.

The Windows UI accepts a server origin and a browser-created device token. Rust validates the token with the authenticated /auth/me endpoint before storing it in Windows Credential Manager. Tokens never enter configuration files, SQLite or exported data. Other operating systems fail closed for credential persistence; there is no plaintext fallback. HTTPS is mandatory except loopback development. Redirects, credential-bearing server URLs and embedded paths/query/fragments are rejected. Native HTTP responses are bounded to 2 MiB; sync contract versions, algorithms, fields, money, IDs, variants, counts and timestamps are validated before cache mutation.

Each page and cursor are committed in one SQLite transaction. A staging generation preserves the previous completed cache until the entire new generation is downloaded; restarting resumes at the saved page. Invalid responses or stale retries cannot advance the cursor. The cache has a conservative 128 MiB page budget. Network/authentication errors preserve offline data. A server cursor reset clears only pending download state; the completed generation remains available until replacement completes.

If the server returns 409 because detailed history was compacted or cursors were invalidated, the client automatically resets pending state and begins a complete refresh. The completed offline generation remains intact. A real HTTP regression verifies this recovery path. Core regression count is now seven on Linux (plus the native credential test on Windows).

Exports are atomic, versioned JSON data in the companion's application-data exports directory. They contain compact values, provenance flags and observation times, never code, tokens or cursor material. Even the core export API rejects a canonical directory with a SavedVariables component. The UI exposes no arbitrary file-write command or shell execution. Workshop's actual addon ingestion is S6 and remains excluded. Provisional algorithm compatibility and live upstream verification are explicitly disclosed.

## Reproducible checks

- `cargo test --manifest-path desktop/Cargo.toml --workspace --locked`: six core regression tests on Linux; Windows adds a real Credential Manager save/load/delete round trip.
- `cargo build --manifest-path desktop/Cargo.toml --example http_smoke --locked`, then with backend Python dependencies installed: `python scripts/verify-companion-http.py`. This starts a disposable real FastAPI server on a loopback port and checks Rust authentication, initial sync, incremental no-op, cache preservation on rejected authentication and JSON export. Verified on Linux against synthetic data, without Blizzard calls.
- `npm ci --prefix desktop` and `npm --prefix desktop run tauri build -- --ci`: Windows NSIS installer. Locked npm and Cargo dependencies are tracked. Windows Actions passed core/native credential tests, actual HTTP integration and installer build, then uploaded an artifact (run 43530807214).

The interface uses a market ID explicitly until website market selection and metadata are complete. It supports synchronize/pause/resume/reset/export and offline status. User interface and native installer behavior still require review on Windows; signing/distribution are not configured.

Chromium UI verification passes connection/token-input clearing, two-page synchronization, completed-cache display, export status and disconnect with explicitly mocked Tauri IPC. No browser errors or horizontal overflow at 880 px. This verifies frontend behavior only; native credential storage and installer execution remain Windows CI checks. Screenshot: ignored artifacts/companion-desktop.png. Reproduce with scripts/verify-companion-ui.cjs and Playwright 1.56.1.
