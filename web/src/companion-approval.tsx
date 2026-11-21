import { Loading } from "./loading";
import { useEffect, useRef, useState } from "react";
import { api, User, when } from "./api";
import { companionCallback } from "./companion-callback";
interface RequestDetails {
  request_id: string;
  application: string;
  device_name: string;
  platform: string;
  app_version: string;
  expires_at: string;
  status: "pending" | "approved" | "consumed" | "denied" | "invalid";
  account: { id: number; username: string };
  consent_token: string | null;
}
export function CompanionApproval({
  user,
  logout,
  authError = "",
}: {
  user: User;
  logout: () => Promise<void>;
  authError?: string;
}) {
  const request = new URLSearchParams(location.search).get("request") || "";
  const [details, setDetails] = useState<RequestDetails | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const live = useRef(true);
  useEffect(() => {
    live.current = true;
    const abort = new AbortController();
    setDetails(null);
    setError("");
    if (!/^[A-Za-z0-9_-]{43}$/.test(request)) {
      setError(
        "This connection request is missing or invalid. Start again from the companion.",
      );
      return () => {
        live.current = false;
        abort.abort();
      };
    }
    api<RequestDetails>(
      `/companion/authorizations/${request}`,
      "GET",
      undefined,
      abort.signal,
    )
      .then((value) => {
        if (!live.current) return;
        if (
          value.request_id !== request ||
          value.application !== "TwichUI Market Companion" ||
          value.account.id !== user.id
        )
          throw new Error("Your sign-in changed. Reload this approval page.");
        setDetails(value);
      })
      .catch((error) => {
        if (!abort.signal.aborted && live.current) setError(error.message);
      });
    return () => {
      live.current = false;
      abort.abort();
    };
  }, [request, user.id]);
  async function decide(decision: "approve" | "deny") {
    if (!details?.consent_token || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ redirect_uri: string; status: string }>(
        `/companion/authorizations/${request}/decision`,
        "POST",
        { decision, consent_token: details.consent_token },
      );
      if (!live.current) return;
      const callback = companionCallback(result.redirect_uri);
      setDetails({
        ...details,
        status: decision === "approve" ? "approved" : "denied",
        consent_token: null,
      });
      location.replace(callback);
    } catch (error) {
      if (live.current) setError((error as Error).message);
    } finally {
      if (live.current) setBusy(false);
    }
  }
  return (
    <main className="companion-approval">
      <a className="brand" href="/companion">
        <span className="sigil">T</span>
        <span>
          TWICHUI<small>MARKET COMPANION</small>
        </span>
      </a>
      <section className="panel companion-consent">
        <div className="eyebrow">SECURE DEVICE CONNECTION</div>
        <h1>Connect your companion.</h1>
        <p className="intro">
          Approve this Windows device to keep your market prices close at hand.
        </p>
        <div className="consent-account">
          <span className="small muted">Signed in as</span>
          <strong>{user.username}</strong>
          <button className="text-button" disabled={busy} onClick={logout}>
            Use another account
          </button>
        </div>
        {!details && !error && (
          <Loading label="Checking your connection request…"/>
        )}
        {busy && <Loading label="Connecting your Companion…"/>}
        {details && (
          <>
            <div className="consent-device">
              <span className="device-glyph" aria-hidden="true">
                ▣
              </span>
              <div>
                <h2>{details.device_name}</h2>
                <p>
                  {details.platform} · Companion {details.app_version}
                </p>
              </div>
            </div>
            <p>
              The companion can read your account name and saved market choice,
              and download verified market prices. It cannot change collection
              settings or manage your account.
            </p>
            <p className="small muted">
              Your password stays on this website. Only approve if you started
              this request from TwichUI Market Companion.
            </p>
            {details.status === "pending" ? (
              <>
                <div className="consent-actions">
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={() => decide("approve")}
                  >
                    {busy ? "Connecting…" : "Approve this device"}
                  </button>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => decide("deny")}
                  >
                    Deny
                  </button>
                </div>
                <p className="small muted">
                  Keep the companion open. This request expires{" "}
                  {when(details.expires_at)}.
                </p>
              </>
            ) : (
              <div className="notice" role="status">
                <strong>
                  {details.status === "denied"
                    ? "Connection declined."
                    : details.status === "consumed"
                      ? "This device has connected."
                      : "This request has already been answered."}
                </strong>
                <p>
                  Return to the companion. If it did not connect, start a new
                  sign-in there.
                </p>
                <a href="/companion">View desktop setup</a>
              </div>
            )}
          </>
        )}
        {(error || authError) && (
          <div className="notice error" role="alert">
            <p>{error || authError}</p>
            <button
              className="secondary"
              disabled={busy}
              onClick={() => location.reload()}
            >
              Reload approval page
            </button>
            <p className="small">
              Expired or cancelled requests must be restarted in the companion.
            </p>
          </div>
        )}
      </section>
      <p className="small muted">
        You can rename or revoke this device later in{" "}
        <a href="/account">Account &amp; devices</a>.
      </p>
    </main>
  );
}
