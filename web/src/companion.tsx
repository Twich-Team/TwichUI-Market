import { Loading } from "./loading";
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
  const connected = current[0];
  const synced = current.filter(device => device.last_sync_at)
    .sort((a,b) => Date.parse(b.last_sync_at!) - Date.parse(a.last_sync_at!))[0];
  const [editingSetup,setEditingSetup] = useState(false);
  const [channel,setChannel] = useState<"stable"|"beta">("stable");
  const [copied,setCopied] = useState(false);
  const selected = bootstrap.data?.markets.find(
    (market) => market.id === bootstrap.data?.suggested_market_id,
  );
  const url = companionDownloadUrl(release.data);
  const beta = privateBeta.data;
  const betaUrl = beta?.channel === "private-beta" && beta.signed === false && beta.updates === "signed" && beta.updater_signature_verified === true && beta.tray_actions_verified === false
    ? companionDownloadUrl(beta, "private-beta") : null;
  const showGuide = editingSetup || !synced;
  const betaSelected = Boolean(betaUrl && (channel === "beta" || !url));
  const installer = betaSelected ? beta : release.data;
  const installerUrl = betaSelected ? betaUrl : url;
  const pageLink = new URL("/companion", location.origin).href;
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
      <h1>Desktop Companion</h1>
      {devices.isPending ? <Loading label="Loading your devices…" skeleton/> : connected && (
        <section className="panel padded companion-recent" role="status">
          <div><h2>{(synced ?? connected).name}</h2>
          <p>Authorized for this account</p>
          <p>{synced ? <>Last sync delivered {when(synced.last_sync_at)}{synced.selected_market_name && ` · ${synced.selected_market_name}`}</> : "Waiting for first sync"}</p></div>
          <button className="secondary" onClick={() => {setEditingSetup(true); step(0, Date.now());}}>
            Set up another PC
          </button>
        </section>
      )}
      {devices.error && <p role="alert" className="notice error">Your devices could not be loaded. <button onClick={() => devices.refetch()}>Try again</button></p>}
      {showGuide && !devices.isPending && <div className="companion-setup-grid">
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
              <h2>Install on Windows</h2>
              <p>Keep a copy of market prices on your PC for offline use.</p>
              {url && betaUrl && <label>Release<select value={channel} onChange={e=>setChannel(e.target.value as "stable"|"beta")}>
                <option value="stable">Stable</option><option value="beta">Beta</option>
              </select></label>}
              {installerUrl && installer ? <div className="companion-installer">
                <p><strong>{betaSelected ? "Beta" : "Stable"}</strong> · {installer.version} · Windows x64 · {formatBytes(installer.bytes)}</p>
                <a className="primary companion-download" href={installerUrl} download onClick={()=>step(1)}>Download for Windows</a>
                <p className="small">Windows may show an unknown-publisher warning. Updates are signed and require your consent.</p>
                <details><summary>Download integrity and Windows warnings</summary>
                  <p>Compare the downloaded file’s SHA-256 with this value. If Windows blocks the installer, contact your administrator.</p>
                  <code className="release-hash">{installer.sha256}</code>
                  {betaSelected && <p>Windows tray actions still need verification on your PC.</p>}
                </details>
              </div> : privateBeta.isPending || release.isPending ? <Loading label="Checking downloads…"/> :
                <div className={privateBeta.error || release.error ? "notice error" : "notice"} role="status">
                  <p>{privateBeta.error || release.error ? "Download information could not be loaded." : "A verified Windows installer is not available yet."}</p>
                  <button className="secondary" onClick={()=>{void privateBeta.refetch();void release.refetch();}}>Check downloads again</button>
                </div>}
              <details className="windows-page-link"><summary>Open this page on your Windows PC</summary>
                <p>On Windows, open this address and sign in. For a private preview, connect the review tunnel on that PC first.</p>
                <input aria-label="Windows download page address" value={pageLink} readOnly onFocus={e=>e.target.select()}/>
                <button className="secondary" onClick={async()=>{try {await navigator.clipboard.writeText(pageLink);setCopied(true);} catch {document.querySelector<HTMLInputElement>(".windows-page-link input")?.select();}}}>
                  {copied ? "Link copied" : "Copy page link"}
                </button>
              </details>
              <button className="text-button" onClick={() => step(1)}>
                I already have the companion →
              </button>
              <p className="small muted">
                Workshop data updates need your permission and wait until WoW is
                closed. Your WoW SavedVariables stay untouched.
              </p>
            </div>
          )}
          {progress.step === 1 && (
            <div className="companion-step">
              <span className="eyebrow">02 / INSTALL &amp; OPEN</span>
              <h2>Open the installer</h2>
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
              <h2>Approve your PC</h2>
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
                  ? "Market prices delivered"
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
                  <span>Last sync delivered</span>
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
      </div>}
      <CompanionDevices userId={user.id} />
    </div>
  );
}
