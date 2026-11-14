import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient, clearPrivateCache, setQueryIdentity } from "./query";
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
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(true),
    [page, setPage] = useState("explorer"),
    [markets, setMarkets] = useState<Market[]>([]),
    [market, setMarket] = useState(0),
    [error, setError] = useState("");
  const [focus, setFocus] = useState<{
    item_id: number;
    variant_key: string;
  } | null>(null);
  useEffect(() => {
    const expired = () => {
      clearPrivateCache();
      setCsrf("");
      setUser(null);
      setMarkets([]);
      setMarket(0);
      setFocus(null);
    };
    window.addEventListener("market-auth-expired", expired);
    return () => window.removeEventListener("market-auth-expired", expired);
  }, []);
  const loadMarkets = async () => {
    const result = await api<{ markets: Market[] }>("/markets");
    setMarkets(result.markets);
    setMarket((previous) =>
      result.markets.some((row) => row.id === previous)
        ? previous
        : result.markets[0]?.id || 0,
    );
  };
  useEffect(() => {
    api<BrowserSession>("/auth/session")
      .then((session) => {
        setQueryIdentity(`${session.user.id}:${session.user.role}`);
        setCsrf(session.csrf_token);
        setUser(session.user);
      })
      .catch((error) => {
        if (!(error instanceof ApiError && error.status === 401))
          setError(error.message);
      })
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    if (user) loadMarkets().catch((error) => setError(error.message));
  }, [user?.id]);
  function session(result: BrowserSession) {
    setPage("explorer");
    setFocus(null);
    setQueryIdentity(`${result.user.id}:${result.user.role}`);
    setCsrf(result.csrf_token);
    setUser(result.user);
    setError("");
  }
  async function logout() {
    try {
      await api("/auth/logout", "POST");
      clearPrivateCache();
      setCsrf("");
      setUser(null);
      setMarkets([]);
    } catch (error) {
      setError((error as Error).message);
    }
  }
  if (loading)
    return (
      <main className="login" role="status">
        Opening your ledger…
      </main>
    );
  if (!user)
    return (
      <>
        <Login onSession={session} />
        {error && (
          <div className="notice error" role="alert">
            {error}
          </div>
        )}
      </>
    );
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
          <div className="notice review">
            Design review in progress · The three major page designs await owner
            approval.
          </div>
          {error && (
            <div className="notice error" role="alert">
              {error}
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
              refreshMarkets={loadMarkets}
            />
          )}{" "}
          {page === "account" && (
            <Account
              signedOut={() => {
                clearPrivateCache();
                setCsrf("");
                setUser(null);
              }}
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
