import { formatBytes } from "./size";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError, User, when } from "./api";
import { companionDownloadUrl } from "./companion-downloads";
import { usePreferences } from "./preferences";
import { CompanionDevices, useCompanionDevices } from "./companion-devices";
interface Release {
  contract_version: number;
  ready: boolean;
  version: string | null;
  platform: string;
  download_url: string | null;
  bytes: number | null;
  sha256: string | null;
  message: string;
  published_at: string | null;
}
interface SetupProgress {
  schema_version: 1;
  step: number;
  since: number;
}
function restore(key: string): SetupProgress {
  try {
    const raw = localStorage.getItem(key) || "null";
    if (raw.length > 4096) return { schema_version: 1, step: 0, since: 0 };
    const value = JSON.parse(raw);
    if (
      value?.schema_version === 1 &&
      Number.isInteger(value.step) &&
      value.step >= 0 &&
      value.step <= 3 &&
      Number.isSafeInteger(value.since) &&
      value.since >= 0 &&
      value.since <= Date.now() + 300000
    )
      return value;
  } catch {}
  return { schema_version: 1, step: 0, since: 0 };
}
interface PrivateBeta extends Release {
  channel: "private-beta";
  signed: false;
  updates: "signed";
  updater_signature_verified: true;
  tray_actions_verified: false;
}
export function CompanionSetup({ user }: { user: User }) {
  const key = `market-companion-setup-v1:${user.id}`;
  const [progress, setProgress] = useState(() => restore(key)),
    [storageError, setStorageError] = useState(""),
    [pollUntil, setPollUntil] = useState(() =>
      restore(key).step >= 2 ? Date.now() + 5 * 60_000 : 0,
    );
  const preferences = usePreferences();
  const release = useQuery({
    queryKey: ["companion", "release"],
    queryFn: ({ signal }) =>
      api<Release>("/companion/releases/current", "GET", undefined, signal),
    staleTime: 60_000,
  });
  const privateBeta = useQuery({
    queryKey: ["private", "companion", "private-beta", user.id],
    enabled: release.isSuccess && !release.data.ready,
    queryFn: async ({ signal }) => {
      try { return await api<PrivateBeta>("/companion/private-beta/current", "GET", undefined, signal); }
      catch (error) { if (error instanceof ApiError && error.status === 404) return null; throw error; }
    },
    retry: false,
    staleTime: 60_000,
  });
  const bootstrap = useQuery({
    queryKey: [
      "private",
      "companion",
      "bootstrap",
      user.id,
      preferences.values.market_id,
    ],
    queryFn: ({ signal }) =>
      api<{
        account: { id: number };
        suggested_market_id: number | null;
        preferred_market_id: number | null;
        preference_fallback: boolean;
        markets: { id: number; label: string; available_for_sync: boolean }[];
      }>("/companion/bootstrap", "GET", undefined, signal),
  });
  const devices = useCompanionDevices(
    user.id,
    false,
    Date.now() < pollUntil && document.visibilityState === "visible",
  );
  const current = (devices.data?.devices || []).filter(
    (device) =>
      !device.revoked &&
      new Date(device.expires_at).getTime() > Date.now() &&
      (!device.renewal_expires_at ||
        new Date(device.renewal_expires_at).getTime() > Date.now()) &&
      new Date(device.authorized_at).getTime() >= progress.since,
  );
  const connected = current[0],
    synced = current.find((device) => device.last_sync_at);
  const selected = bootstrap.data?.markets.find(
    (market) => market.id === bootstrap.data?.suggested_market_id,
  );
  const url = companionDownloadUrl(release.data);
  const beta = privateBeta.data;
  const betaUrl = beta?.channel === "private-beta" && beta.signed === false && beta.updates === "signed" && beta.updater_signature_verified === true && beta.tray_actions_verified === false
    ? companionDownloadUrl(beta, "private-beta") : null;
  function step(value: number, since = progress.since) {
    const next: SetupProgress = { schema_version: 1, step: value, since };
    setProgress(next);
    setStorageError("");
    try {
      localStorage.setItem(key, JSON.stringify(next));
    } catch {
      setStorageError(
        "This browser could not save your place. Connection status still comes from the server.",
      );
    }
    if (value >= 2) setPollUntil(Date.now() + 5 * 60_000);
  }
  const labels = ["Download", "Install & open", "Approve device", "First sync"];
  return (
    <div className="companion-page">
      <div className="eyebrow">GET DESKTOP COMPANION</div>
      <h1>Your market, ready on your PC.</h1>
      <p className="intro">
        A small Windows companion that keeps prices up to date and available
        offline. Your market research stays here on the website.
      </p>
      {synced && (
        <section className="notice success" role="status">
          <strong>{synced.name} is connected.</strong>
          <p>
            First sync delivered {when(synced.last_sync_at)}
            {synced.selected_market_name && ` · ${synced.selected_market_name}`}
            .
          </p>
          <button className="text-button" onClick={() => step(0, Date.now())}>
            Set up another PC
          </button>
        </section>
      )}
      <div className="companion-setup-grid">
        <section className="panel padded companion-guide">
          <nav className="companion-steps" aria-label="Desktop setup steps">
            {labels.map((label, index) => (
              <button
                key={label}
                className={progress.step === index ? "active" : ""}
                aria-current={progress.step === index ? "step" : undefined}
                onClick={() => step(index)}
              >
                <span>{index + 1}</span>
                {label}
              </button>
            ))}
          </nav>
          {progress.step === 0 && (
            <div className="companion-step">
              <span className="eyebrow">01 / DOWNLOAD</span>
              <h2>Keep it close. Keep it simple.</h2>
              <p>
                Get the Windows installer directly from TwichUI Market.
                No GitHub account is needed.
              </p>
              {release.isPending ? (
                <p role="status">Checking the current release…</p>
              ) : release.error ? (
                <div className="notice error" role="alert">
                  <p>Download information is unavailable. Please try again.</p>
                  <button
                    className="secondary"
                    onClick={() => release.refetch()}
                  >
                    Check downloads again
                  </button>
                </div>
              ) : url ? (
                <>
                  <a
                    className="primary companion-download"
                    href={url}
                    download
                    onClick={() => step(1)}
                  >
                    Download for Windows <span aria-hidden="true">↓</span>
                  </a>
                  <p className="small muted">
                    Version {release.data?.version} · Windows 10/11, 64-bit ·{" "}
                    {formatBytes(release.data?.bytes)}
                  </p>
                  <p className="small muted">
                    Published {when(release.data?.published_at)}. The installer
                    has cryptographically signed updates. This release passed its Windows checks; Windows may show an unknown-publisher warning.
                  </p>
                  <details>
                    <summary>Release integrity details</summary>
                    <p className="small">SHA-256</p>
                    <code className="release-hash">{release.data?.sha256}</code>
                  </details>
                </>
              ) : betaUrl ? (
                <div className="notice" role="status">
                  <strong>Private Windows beta</strong>
                  <p>This test version is shared with your account. The installer is unsigned, so Windows may show a warning or block it.</p>
                  <p>Updates are checked automatically and verified before installation. You choose when to install. Tray actions still need checking on your PC.</p>
                  <a className="primary companion-download" href={betaUrl} download onClick={() => step(1)}>
                    Download private beta <span aria-hidden="true">↓</span>
                  </a>
                  <p className="small muted">Version {beta?.version} · Windows 10/11, 64-bit · {formatBytes(beta?.bytes)}</p>
                  <details>
                    <summary>Download integrity and Windows warnings</summary>
                    <p>Download only from market.twich.gg and compare the SHA-256 below. If SmartScreen offers More info, review the app and choose Run anyway only when you trust this exact download. If Windows blocks it without that option, stop and report the message. Keep Windows security protections enabled.</p>
                    <p className="small">SHA-256</p>
                    <code className="release-hash">{beta?.sha256}</code>
                  </details>
                </div>
              ) : privateBeta.error ? (
                <div className="notice error" role="alert">
                  <p>Private download information is unavailable. Please try again.</p>
                  <button className="secondary" onClick={() => privateBeta.refetch()}>Check private download again</button>
                </div>
              ) : (
                <div className="notice" role="status">
                  <strong>Release verification is in progress.</strong>
                  <p>
                    {release.data?.message ||
                      "The Windows download will appear here after release verification is complete."}
                  </p>
                  <button
                    className="secondary"
                    onClick={() => release.refetch()}
                  >
                    Check release status
                  </button>
                </div>
              )}
              <button className="text-button" onClick={() => step(1)}>
                I already have the companion →
              </button>
              <p className="small muted">
                The companion never changes game files or writes into WoW
                SavedVariables.
              </p>
            </div>
          )}
          {progress.step === 1 && (
            <div className="companion-step">
              <span className="eyebrow">02 / INSTALL &amp; OPEN</span>
              <h2>A small place in your tray.</h2>
              <ol>
                <li>
                  Open the downloaded installer and follow the Windows prompts.
                </li>
                <li>
                  Launch <strong>TwichUI Market Companion</strong>.
                </li>
                <li>
                  Choose whether to start it with Windows. This stays off until
                  you enable it.
                </li>
              </ol>
              <p>
                Closing the window can keep the companion running in the tray.
                Use its tray menu to reopen it or quit completely.
              </p>
              <p className="small muted">
                Downloading alone does not confirm installation. The next steps
                check for an authorized companion connection.
              </p>
              <button className="primary" onClick={() => step(2)}>
                Continue to device approval
              </button>
            </div>
          )}
          {progress.step === 2 && (
            <div className="companion-step">
              <span className="eyebrow">03 / APPROVE DEVICE</span>
              <h2>Sign in where you already belong.</h2>
              <ol>
                <li>
                  In the companion, choose{" "}
                  <strong>Sign in with your browser</strong>.
                </li>
                <li>
                  Sign in with your existing Market account. Use your invitation
                  if you are new.
                </li>
                <li>
                  Check the Windows device name, then choose{" "}
                  <strong>Approve this device</strong>.
                </li>
              </ol>
              <p>
                Your password stays on the website. You do not need to copy a
                token or sign in to Blizzard.
              </p>
              <div className="notice" role="status">
                {connected ? (
                  <>
                    <strong>{connected.name} is authorized.</strong>
                    <p>
                      Return to the companion to check its market and first
                      sync.
                    </p>
                  </>
                ) : (
                  <>
                    <strong>Waiting for a companion connection.</strong>
                    <p>Keep the companion open while approving the request.</p>
                  </>
                )}
              </div>
              <div className="toolbar">
                <button
                  className="primary"
                  onClick={() => {
                    void devices.refetch();
                    setPollUntil(Date.now() + 5 * 60_000);
                  }}
                >
                  Check for connection
                </button>
                <button className="secondary" onClick={() => step(3)}>
                  View first sync
                </button>
              </div>
              <p className="small muted">
                While this page is visible, connection checks stop automatically
                after five minutes. Use Check for connection to resume.
              </p>
            </div>
          )}
          {progress.step === 3 && (
            <div className="companion-step">
              <span className="eyebrow">04 / FIRST SYNC</span>
              <h2>
                {synced
                  ? "You’re connected."
                  : "Your first prices are on their way."}
              </h2>
              <p>
                {synced
                  ? "The server delivered a complete market sync. The companion shows when its local cache is ready."
                  : "In the companion, choose an available market and select Sync now. This page confirms when the server has delivered the complete download."}
              </p>
              <div className="companion-status-grid">
                <div>
                  <span>Device authorization</span>
                  <strong>{connected ? "Confirmed" : "Waiting"}</strong>
                </div>
                <div>
                  <span>First sync delivered</span>
                  <strong>
                    {synced ? when(synced.last_sync_at) : "Not yet"}
                  </strong>
                </div>
                <div>
                  <span>Website market choice</span>
                  <strong>
                    {selected?.label ||
                      "Choose an available market in the companion"}
                  </strong>
                </div>
              </div>
              {bootstrap.data?.preference_fallback && (
                <p className="notice">
                  Your saved website market is unavailable. The companion can
                  use an available market without changing your saved
                  preference.
                </p>
              )}
              <p>
                The default check interval is 30 minutes. Change it or pause
                updates in companion Settings. An unchanged collection check
                does not mean new upstream market data.
              </p>
              <button
                className="secondary"
                onClick={() => {
                  void devices.refetch();
                  setPollUntil(Date.now() + 5 * 60_000);
                }}
              >
                Check sync status
              </button>
            </div>
          )}
          {(devices.error || bootstrap.error) && (
            <p className="notice error" role="alert">
              Connection details could not be loaded. Your setup progress is
              kept. Try Check for connection again.
            </p>
          )}
          {storageError && (
            <p className="notice" role="status">
              {storageError}
            </p>
          )}
        </section>
        <aside className="companion-help panel padded">
          <span className="eyebrow">A QUIETER COMPANION</span>
          <h2>Made for the background.</h2>
          <ul>
            <li>One compact status window</li>
            <li>Real Windows tray controls</li>
            <li>Automatic, pausable updates</li>
            <li>Prices available offline</li>
            <li>Revocable device access</li>
          </ul>
          <h3>Need a hand?</h3>
          <p>
            Expired request? Start a new sign-in in the companion. Network
            interrupted? Your completed cache and download progress are
            preserved.
          </p>
          <p className="small muted">
            No charts or research tables in the companion. Market Explorer and
            Deal Finder stay on this website.
          </p>
        </aside>
      </div>
      <CompanionDevices userId={user.id} />
    </div>
  );
}
