import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient, clearPrivateCache, setQueryIdentity } from "./query";
import { announceSessionChange, onSessionChange } from "./auth-channel";
import React, { lazy, Suspense, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, ApiError, BrowserSession, setCsrf, User } from "./api";
const Explorer = lazy(() =>
  import("./research").then((m) => ({ default: m.Explorer })),
);
const Deals = lazy(() => import("./deals").then((m) => ({ default: m.Deals })));
const Administration = lazy(() =>
  import("./settings").then((m) => ({ default: m.Administration })),
);
const Account = lazy(() =>
  import("./settings").then((m) => ({ default: m.Account })),
);
import { Market } from "./types";
import { PreferencesProvider, PreferenceStatus, usePreferences } from "./preferences";
import { preferredMarket } from "./preferences-store";
import "./style.css";

function Login({
  onSession,
}: {
  onSession: (session: BrowserSession) => void;
}) {
  const [register, setRegister] = useState(
      Boolean(new URLSearchParams(location.search).get("invite")),
    ),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      const body = {
        username: String(form.get("username")),
        password: String(form.get("password")),
      };
      if (register) {
        await api("/auth/register", "POST", {
          ...body,
          invitation: String(form.get("invitation")),
        });
        setRegister(false);
        history.replaceState(null, "", location.pathname);
        setNotice("Account created. Sign in with your new credentials.");
      } else onSession(await api<BrowserSession>("/auth/login", "POST", body));
    } catch (error) {
      setError(String((error as Error).message));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login">
      <div className="brand">
        <span className="sigil">T</span>
        <div>
          TWICHUI<small>MARKET INTELLIGENCE</small>
        </div>
      </div>
      <section className="panel">
        <div className="eyebrow">PRIVATE GUILD RESEARCH</div>
        <h1>{register ? "Join the ledger" : "Welcome back"}</h1>
        <p>
          {register
            ? "An invitation from an administrator is required."
            : "Sign in to your private market research."}
        </p>
        <form onSubmit={submit}>
          <label>
            Username
            <input
              name="username"
              autoComplete="username"
              minLength={3}
              maxLength={64}
              required
              pattern="[a-zA-Z0-9_]+"
            />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              minLength={12}
              maxLength={128}
              autoComplete={register ? "new-password" : "current-password"}
              required
            />
          </label>
          {register && (
            <label>
              Invitation token
              <input
                name="invitation"
                defaultValue={
                  new URLSearchParams(location.search).get("invite") || ""
                }
                minLength={20}
                maxLength={128}
                required
                autoComplete="off"
              />
            </label>
          )}
          <button className="primary" disabled={busy}>
            {busy ? "Please wait…" : register ? "Create account" : "Sign in"}
          </button>
        </form>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {notice && (
          <p role="status" className="success">
            {notice}
          </p>
        )}
        <button
          className="text-button"
          onClick={() => {
            setRegister(!register);
            setError("");
            setNotice("");
          }}
        >
          {register ? "Back to sign in" : "Have an invitation? Join here"}
        </button>
      </section>
      <p className="small">
        Invitation-only access · Asking prices, never inferred sales
      </p>
    </main>
  );
}

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let current = true;
    const expired = () => { current = false; clearPrivateCache(); setCsrf(""); setUser(null); setLoading(false); };
    const stop = onSessionChange(expired);
    window.addEventListener("market-auth-expired", expired);
    api<BrowserSession>("/auth/session").then(result => { if (current) restore(result); })
      .catch(error => { if (current && !(error instanceof ApiError && error.status === 401)) setError(error.message); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; stop(); window.removeEventListener("market-auth-expired", expired); };
  }, []);
  function restore(result: BrowserSession) {
    setQueryIdentity(`${result.user.id}:${result.user.role}`);
    setCsrf(result.csrf_token); setUser(result.user); setError("");
  }
  function signedOut() { clearPrivateCache(); setCsrf(""); setUser(null); announceSessionChange(); }
  async function logout() {
    try { await api("/auth/logout", "POST"); signedOut(); }
    catch(error) { setError((error as Error).message); }
  }
  if (loading) return <main className="login" role="status">Opening your ledger…</main>;
  if (!user) return <><Login onSession={result => { restore(result); announceSessionChange(); }} />{error && <p className="notice error" role="alert">{error}</p>}</>;
  return <PreferencesProvider key={`${user.id}:${user.role}`} userId={user.id}>
    <Workspace user={user} logout={logout} signedOut={signedOut} authError={error} />
  </PreferencesProvider>;
}

function Workspace({user,logout:signOut,signedOut,authError}:{user:User;logout:()=>Promise<void>;signedOut:()=>void;authError:string}) {
  const [page,setPage]=useState("explorer");
  const [markets,setMarkets]=useState<Market[]>([]);
  const [error,setError]=useState("");
  const [readOnly,setReadOnly]=useState(true);
  const [focus,setFocus]=useState<{item_id:number;variant_key:string}|null>(null);
  const preferences=usePreferences();
  const market=preferredMarket(markets,preferences.values.market_id);
  const setMarket=(id:number)=>preferences.update({market_id:id});
  const loadMarkets=async()=>{
    const result=await api<{markets:Market[]}>("/markets");
    setMarkets(result.markets);
  };
  useEffect(()=>{
    loadMarkets().catch(error=>setError(error.message));
    api<{read_only:boolean}>("/environment").then(result=>{
      queryClient.setQueryData(["private","environment"],result);setReadOnly(result.read_only);
    }).catch(error=>setError(error.message));
  },[]);
  async function logout() { await preferences.flush(); await signOut(); }
  const names: Record<string, string> = {
    explorer: "Market Explorer",
    deals: "Deal Finder",
    admin: "Administration",
    account: "Account & devices",
  };
  return (
    <>
      <aside>
        <a
          href="#explorer"
          className="brand"
          onClick={() => setPage("explorer")}
        >
          <span className="sigil">T</span>
          <span>
            TWICHUI<small>MARKET INTELLIGENCE</small>
          </span>
        </a>
        <div className="eyebrow private">PRIVATE GUILD RESEARCH</div>
        <nav>
          {[
            "explorer",
            "deals",
            ...(user.role === "admin" ? ["admin"] : []),
            "account",
          ].map((key) => (
            <button
              key={key}
              className={page === key ? "active" : ""}
              onClick={() => setPage(key)}
            >
              {names[key]}
            </button>
          ))}
        </nav>
        <div className="account-info">
          <strong>{user.username}</strong>
          <small>{user.role === "admin" ? "Administrator" : "Member"}</small>
          <button className="text-button" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header>
          <span>
            THE AUCTIONEER’S LEDGER <i>/</i> {names[page]}
          </span>
          <span className="badge">PRIVATE</span>
        </header>
        <main>
          {readOnly && <p className="notice" role="status">Interactive preview · Your preferences save automatically. Collection and account administration are read-only.</p>}
          <PreferenceStatus />
          {preferences.values.market_id !== null && !markets.some(m => m.id === preferences.values.market_id) && markets.length > 0 && <p className="notice">Your preferred market is unavailable. Showing an available market; your saved choice is retained.</p>}
          {(error || authError) && (
            <div className="notice error" role="alert">
              {error || authError}
            </div>
          )}
          {page === "explorer" && (
            <Explorer
              markets={markets}
              market={market}
              setMarket={setMarket}
              focus={focus}
            />
          )}{" "}
          {page === "deals" && (
            <Deals
              markets={markets}
              market={market}
              setMarket={setMarket}
              inspect={(deal) => {
                setFocus({
                  item_id: deal.item_id,
                  variant_key: deal.variant_key,
                });
                setPage("explorer");
              }}
            />
          )}{" "}
          {page === "admin" && user.role === "admin" && (
            <Administration
              user={user}
              markets={markets}
              readOnly={readOnly}
              refreshMarkets={loadMarkets}
            />
          )}{" "}
          {page === "account" && (
            <Account readOnly={readOnly}
              signedOut={signedOut}
            />
          )}
        </main>
        <footer>
          TWICHUI MARKET <span>Private knowledge. Better decisions.</span>
          <span>All prices are asking prices, not completed sales.</span>
        </footer>
      </div>
    </>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <Suspense
        fallback={
          <p role="status" className="empty">
            Loading market tools…
          </p>
        }
      >
        <App />
      </Suspense>
    </QueryClientProvider>
  </React.StrictMode>,
);
