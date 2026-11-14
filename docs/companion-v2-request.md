/goal Build, deploy, and verify TwichUI Market Companion v2: a polished, native-feeling Windows desktop utility with automatic background synchronization, system tray integration, secure browser-based account authentication, and a complete non-technical download and setup experience integrated into the production TwichUI Market website.

# Project context

Repository: Twich-Team/TwichUI-Market

Production website: https://market.twich.gg

The website is live and its visual design has been approved. Production release c8f03c2 was verified, with acceptance checkpoint 454ec14.

The platform collects genuine World of Warcraft: Forever Auction House data. US Normal — Horde (house 114, market 2) is the only active collector.

The existing desktop companion is built with Tauri, Rust, SQLite, Windows Credential Manager, and a simple WebView interface. It already supports authenticated synchronization, resumable downloads, offline caching, and versioned JSON export.

Preserve that working foundation.

The owner wants the desktop application to feel like a proper Windows utility rather than a website displayed inside a desktop window.

Target audience: ordinary World of Warcraft players, including friends with no technical knowledge.

The desired first-run experience is:

**Download → Install → Sign in through browser → Approve connection → Select market → Automatic synchronization.**

After setup, the application should quietly maintain market data with minimal user interaction.

# 1. Autonomous development requirements

Read AGENTS.md, all relevant desktop and authentication documentation, current implementation plans, API contracts, CI workflows, and deployment acceptance records.

Inspect the actual repository and installed production state before modifying anything.

Research current Tauri 2 capabilities, supported plugins, Windows platform behavior, and secure native-app authentication standards.

Create a detailed implementation plan with independently verifiable milestones, dependencies, and acceptance criteria.

Execute the complete plan autonomously.

Do not stop after planning, creating mockups, installing libraries, or completing one subtask.

Continue through all unblocked engineering work until the Goal is verified complete.

Maintain durable progress documentation so another Codex session can resume unfinished work.

At meaningful verified checkpoints:

- Inspect changes.
- Run relevant tests.
- Check for secrets and unrelated modifications.
- Commit coherent work.
- Push to the configured GitHub remote.
- Record commit hashes and verification evidence.

Never force-push or overwrite unrelated work.

# 2. Native-feeling Windows application

Keep Tauri unless research establishes a compelling reason to replace it.

Redesign the desktop experience around a compact, status-first utility.

Avoid reproducing the website's page layout, large headers, oversized cards, or lengthy explanations.

Maintain the restrained TwichUI Market palette:

- Dark espresso and walnut backgrounds.
- Muted aged-bronze highlights.
- Warm ivory text.
- Subtle borders and surface separation.
- Clear typography.
- Compact controls.
- Minimal decoration.

Use familiar Windows interaction patterns.

The primary window should prominently display:

- Connection status.
- Signed-in account.
- Selected market.
- Last successful synchronization.
- Last upstream Blizzard data update.
- Next scheduled synchronization.
- Local cache status.
- Current synchronization progress.
- Relevant warnings and errors.
- Sync Now action.
- Settings access.

Provide a compact, resizable window with sensible minimum dimensions, DPI scaling, accessible controls, and correct Windows taskbar behavior.

Use appropriate native integrations rather than trying to simulate all operating-system behavior with HTML.

The website is for market research. The desktop companion is for managing synchronization.

Do not add charts, auction tables, or unrelated website research features to the desktop companion unless genuinely necessary.

# 3. Windows system tray

Implement a real Windows notification-area icon.

Support:

- Minimize to tray.
- Close button hides to tray.
- Start directly in tray.
- Restore window from tray.
- Double-click tray icon to open.
- Clear, explicit Quit behavior.
- Accurate running/synchronizing/error indications.

Tray menu:

- Open TwichUI Market Companion.
- Sync Now.
- Pause / Resume automatic synchronization.
- Settings.
- Synchronization status.
- Quit.

Closing the window must not terminate background synchronization when close-to-tray is enabled.

Explicit Quit must terminate background activity and exit cleanly.

Avoid duplicate tray icons, hidden orphaned processes, and multiple competing sync workers.

Implement single-instance behavior. Starting the application again should focus the existing instance or otherwise behave predictably.

# 4. Persistent desktop settings

Provide a dedicated Settings interface with approachable sections:

General, Synchronization, Account & Connection, and Advanced.

Implement persistent preferences for:

- Launch when signing into Windows.
- Start minimized to system tray.
- Minimize to system tray.
- Close button hides to tray.
- Automatic synchronization enabled.
- Synchronization interval.
- Synchronize on application startup.
- Notifications for significant errors.
- Selected market.
- Window size and position where appropriate.

Synchronization interval choices:

- 15 minutes.
- 30 minutes (recommended default).
- 60 minutes.
- 2 hours.
- 4 hours.

The server's Blizzard collection and the desktop's synchronization interval are separate concepts.

Do not let changing a desktop preference modify server collection schedules.

Windows autostart must be opt-in and reversible.

First-time users should always see onboarding rather than having the application silently disappear into the tray.

Use the supported Tauri autostart, tray, window-state, and single-instance mechanisms where appropriate.

Use versioned local settings and safe migrations.

Store non-sensitive preferences locally.

Never store passwords, device tokens, or refresh credentials in plaintext settings.

Continue using Windows Credential Manager for secure credentials.

# 5. Native background synchronization

Move automatic synchronization scheduling into the Rust application layer.

It must not depend on whether the WebView is open, visible, minimized, or hidden.

Reuse the existing tested Rust sync engine, SQLite cache, and incremental cursor protocol.

Implement:

- Automatic scheduled synchronization.
- Manual Sync Now.
- Pause and Resume.
- Safe cancellation.
- Single-flight synchronization.
- Bounded retries and backoff.
- Offline detection.
- Recovery when connectivity returns.
- Windows sleep/wake handling.
- Correct startup behavior.
- Accurate timestamps.
- Progress events for the UI.
- Tray status updates.
- Graceful shutdown.
- Preservation of the last completed offline cache.

Do not start competing downloads for the same market.

Avoid unnecessary downloads when the server has not published a newer generation.

Do not confuse a successful HTTP check with new Blizzard market data.

Distinguish:

- Last desktop sync.
- Last server collection check.
- Last actual upstream market update.
- Current cache freshness.

Use incremental sync whenever possible.

The application should consume minimal CPU, RAM, network bandwidth, and disk activity when idle.

Use a controllable clock for deterministic scheduling tests.

# 6. Replace manual device-token login

The current desktop application requires users to paste a server URL and device token.

Replace that normal experience with secure browser-based authentication using the user's existing TwichUI Market website account.

The desired flow:

1. User clicks "Sign in with TwichUI Market" in the desktop app.
2. The app opens https://market.twich.gg in the system's default browser.
3. User signs in with their normal Market credentials, or reuses an authenticated browser session.
4. The website displays an authorization screen identifying the requesting desktop application and device.
5. User approves or denies the connection.
6. The desktop securely receives the authorization result.
7. The application stores its device credentials in Windows Credential Manager.
8. The app retrieves the user's market preferences and available markets.
9. Initial synchronization begins.
10. Future launches reconnect silently while authorization remains valid.

Use OAuth 2.0 Authorization Code with PKCE S256 or a comparably well-established native-app authorization pattern.

Prefer a temporary loopback callback bound to 127.0.0.1 and an OS-assigned port, with exact callback validation.

Use the system browser, not an embedded authentication WebView.

Security requirements:

- Cryptographically random state.
- PKCE S256.
- Short-lived, single-use authorization codes.
- Strict redirect validation.
- Server-side approval tied to the authenticated account.
- Explicit device identification.
- Bounded attempts and rate limiting.
- Replay protection.
- Least-privilege device permissions.
- Revocable credentials.
- Appropriate expiration and renewal.
- Secure credential storage.
- Protection against cross-user authorization.
- No credentials in browser URLs, logs, installer files, or plaintext configuration.

Existing website account passwords remain entirely outside the desktop companion.

Do not introduce Blizzard OAuth login for desktop users.

Do not replace the existing invitation-only Market authentication system.

Preserve existing authorized desktop clients or provide a safe, non-destructive migration path.

After setup, users should never need to manually copy API tokens for normal operation.

An advanced development-token option may remain hidden in troubleshooting settings if justified.

# 7. User-level preferences integration

The website now has a persistent PostgreSQL-backed per-user preference system.

Integrate it into desktop onboarding.

When a user connects:

- Retrieve available verified markets.
- Prefer their saved market selection.
- Display friendly market names.
- Allow changing the desktop's selected market.
- Respect unavailable or disabled markets.
- Avoid exposing internal market IDs.

Default to US Normal — Horde when it is both available and appropriate for the signed-in user.

The desktop preference may be different from the website's selected market if the user explicitly chooses that behavior.

Do not modify administrator collection settings when saving an individual user's selection.

# 8. Website download and setup wizard

Add a prominent **Get Desktop Companion** action to the production website.

Preferred placement:

- Account & Devices.
- A clearly discoverable secondary navigation/header entry.

Create a polished guided installation experience.

The wizard should cover:

1. Download the Windows installer.
2. Install the application.
3. Open the application.
4. Sign in through the browser.
5. Approve the device.
6. Choose a market.
7. Complete the first synchronization.

Use concise, friendly language.

Do not expose implementation terms such as OAuth, PKCE, bearer tokens, callback URLs, market IDs, or GitHub Actions artifacts to ordinary users.

The wizard should:

- Show clear progress.
- Explain each step.
- Provide troubleshooting help.
- Support resuming setup.
- Handle canceled or failed pairing.
- Show the actual released application version.
- Provide a reliable installer download.
- Work on desktop and mobile browsers.
- Follow the existing approved clean visual style.

Do not make the wizard dependent on an untrusted client-side claim that installation succeeded.

Use server-confirmed pairing and synchronization status where possible.

Keep the existing website fast. Lazy-load wizard components if appropriate.

# 9. Installer distribution and updates

The current Windows installer is produced by GitHub Actions.

Replace the developer-oriented workflow artifact experience with a proper versioned release process.

Requirements:

- Build on Windows CI.
- Run automated tests.
- Produce a reproducible installer.
- Validate installed application behavior.
- Publish approved release artifacts.
- Display the correct installer version.
- Provide an authenticated or otherwise appropriately controlled download link from the website.
- Do not require ordinary users to log into GitHub.
- Do not depend on expiring GitHub Actions artifacts.

Research Tauri's signed updater system and implement secure update checking where feasible.

Never install unsigned or unverified update payloads silently.

If code signing requires owner-managed credentials or external expenditure, leave that as an explicit owner decision and complete all independent release infrastructure.

Do not publish an unverified prerelease as stable.

Never commit signing keys, update private keys, secrets, or release credentials.

# 10. Device management

Improve Account & Devices to display useful information about connected desktop clients.

Where reliably available, show:

- Device name.
- Platform.
- Application version.
- Authorization date.
- Last connection.
- Last successful synchronization.
- Selected market.
- Credential expiration.
- Revocation status.

Allow the account owner to rename and revoke their own devices.

Administrators may inspect or revoke devices according to existing role permissions.

Revoked devices must lose access even if the desktop application retains an offline cache.

Local offline data should remain available unless the user explicitly clears it; server revocation must not be misrepresented as deleting offline copies.

Use the existing API security patterns and audit events.

Do not expose device secrets through the website.

# 11. First-run and failure experiences

The companion should have clear, approachable states for:

- Not connected.
- Waiting for browser authorization.
- Authorization approved.
- Authorization denied.
- Authorization expired.
- No markets available.
- Initial synchronization.
- Up to date.
- New data available.
- Offline.
- Server unavailable.
- Credentials revoked.
- Synchronization paused.
- Recoverable sync error.
- Update available.

Avoid technical stack traces and raw API errors in ordinary UI.

Provide a separate diagnostic area with useful technical details and redacted logs.

Do not send repeated notifications for expected offline conditions.

The application should remain useful without a network connection.

# 12. Preserve the addon boundary

TwichUI Workshop integration remains deferred.

Do not modify:

- Twich-Team/TwichUI
- The Workshop addon.
- Actual game SavedVariables.
- Game installation directories.

The desktop companion may continue generating the existing validated data-only JSON export.

Do not claim that data is automatically imported into the addon.

Do not download arbitrary Lua code or write executable addon updates.

Preserve versioned sync/export contracts for the future Workshop integration milestone.

# 13. Production and infrastructure safety

The server is hosted on a Linux VM that also runs CubeCoders AMP.

Use only the approved marketdev/rootless Docker environment.

Never interfere with:

- AMP.
- Game-server processes.
- Unrelated containers.
- Host networking.
- Firewall configuration.
- Traefik.
- Komodo.
- Other user files or services.

Preserve the production website at https://market.twich.gg.

Preserve the live collector for US Normal — Horde, house 114.

Preserve all current historical records, accounts, preferences, sessions, and backups.

Make database migrations additive and safe.

Use isolated databases for destructive tests.

Take and verify backups before production migrations.

Keep deployment rollback available.

Do not activate historical pruning as part of this milestone.

Keep unapproved major website and desktop design changes in reviewable candidates until owner approval.

Do not disrupt live market collection simply to deploy new frontend or desktop features.

# 14. Testing and verification

Implement automated coverage for the complete experience.

## Rust tests

Verify:

- Background scheduler.
- Time intervals and persistence.
- Manual and automatic sync.
- Single-flight behavior.
- Pause and cancellation.
- Offline recovery.
- Sleep/resume.
- Cache preservation.
- Authentication expiration and renewal.
- Windows credential handling.
- Settings migrations.
- Single-instance behavior.

## Windows integration tests

Verify the actual installed executable, not only mocked WebView commands.

Test:

- First launch.
- Browser-based sign-in.
- Device approval.
- Credential persistence.
- App restart.
- System tray.
- Autostart registration.
- Hidden startup.
- Minimize/close behavior.
- Tray restoration.
- Explicit Quit.
- Automatic synchronization.
- Manual synchronization.
- Credential revocation.
- Uninstall.
- Upgrade compatibility.

Use isolated Windows CI environments.

Do not enable unsafe debugging features in production releases.

## Backend tests

Verify:

- Authorization-code flow.
- PKCE and state validation.
- Expiration and replay prevention.
- Redirect restrictions.
- Rate limiting.
- Account and device ownership.
- Revocation.
- Credential renewal.
- Existing session compatibility.
- Device activity reporting.

## Website tests

Use Playwright to verify:

- Download flow.
- Setup wizard.
- Browser authorization.
- Device approval and denial.
- Connected-device status.
- Device revocation.
- Error recovery.
- Accessibility.
- Responsive layouts.

Test the actual browser-to-desktop flow where practical.

## Deployment verification

Verify:

- Existing production authentication.
- Existing frontend features.
- Current market data.
- Background collector health.
- Historical record preservation.
- Database migration.
- Backup restoration.
- New desktop API endpoints.
- Installer distribution.
- HTTPS certificate validation.
- No regression to existing desktop clients.

Record actual verification evidence, not assumptions.

# 15. Performance and quality

The companion should feel responsive and use very little system resources while idle.

Measure:

- Cold startup time.
- Memory usage.
- Idle CPU usage.
- Background network activity.
- Initial sync time.
- Incremental sync time.
- Window restore time.
- Installer size.
- Frontend bundle size.

Optimize measured bottlenecks.

Do not add a heavy frontend framework or unnecessary background services without justification.

Reuse established Tauri plugins and the tested Rust core.

Preserve accessibility and keyboard navigation.

# 16. Visual review

Produce actual screenshots of:

1. Welcome / Sign in.
2. Connected dashboard.
3. Synchronization progress.
4. Settings.
5. Tray menu.
6. Website download wizard.
7. Website authorization approval screen.
8. Website connected devices.

Inspect these for readability, spacing, layout, consistency, and Windows usability.

Use the existing TwichUI Market palette and simple visual direction.

Present significant design changes for owner approval before final production promotion.

Functional testing does not imply visual approval.

# 17. Completion criteria

This Goal is complete when:

- The companion feels like a purpose-built Windows utility.
- Tray functionality works reliably.
- Windows startup settings work.
- Background synchronization operates without the visible UI.
- Synchronization intervals are configurable.
- Preferences persist correctly.
- Browser-based sign-in and device approval work securely.
- Existing account credentials are reused without manual token copying.
- The user's preferred market is available during setup.
- The website provides a straightforward installer download and setup wizard.
- Users can manage and revoke connected devices.
- Release distribution no longer depends on temporary CI artifacts.
- Windows and browser end-to-end tests pass.
- Existing market collection and history are preserved.
- Production security remains intact.
- Approved changes can be deployed with a verified rollback path.
- Documentation and acceptance evidence are complete.
- Verified changes are committed and pushed.

Do not claim complete production readiness if code signing, owner visual approval, external deployment actions, or other required dependencies remain unresolved.

## Execute now

Begin by inspecting the latest implementation and creating the detailed milestone plan.

Prioritize the native background scheduler and secure browser authentication foundations before building the surrounding onboarding experience.

Continue through the full implementation autonomously, completing all independent engineering work and preserving verified Git checkpoints.

Stop only for genuine external blockers or required owner approvals. Do not repeatedly ask for routine development decisions.