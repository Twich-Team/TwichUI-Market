import { administrationGroups, administrationSection } from "./admin-navigation";
import { Loading } from "./loading";
import {parseRoute,useLocation,navigate,restoration} from "./navigation";
import { QueryClientProvider, useQuery } from "@tanstack/react-query";
import { queryClient, clearPrivateCache, setQueryIdentity } from "./query";
import { announceSessionChange, onSessionChange } from "./auth-channel";
import React, { lazy, Suspense, useEffect, useRef, useState } from "react";
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
const Companion = lazy(() => import("./companion").then(m=>({default:m.CompanionSetup})));
const CompanionApproval = lazy(() => import("./companion-approval").then(m=>({default:m.CompanionApproval})));
const ItemDetails=lazy(()=>import('./item-details').then(m=>({default:m.ItemDetails})));
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
        const query=new URLSearchParams(location.search);query.delete("invite");
        history.replaceState(null, "", location.pathname+(query.size?`?${query}`:''));
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
        {location.pathname==='/companion/authorize'&&<p className="notice">Sign in to review a Windows companion connection. Your approval request will remain open.</p>}
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
  if (loading) return <main className="login"><Loading label="Opening your ledger…" skeleton/></main>;
  if (!user) return <><Login onSession={result => { restore(result); announceSessionChange(); }} />{error && <p className="notice error" role="alert">{error}</p>}</>;
  if(location.pathname==='/companion/authorize')return <CompanionApproval key={user.id} user={user} logout={logout} authError={error}/>;
  return <PreferencesProvider key={`${user.id}:${user.role}`} userId={user.id}>
    <Workspace user={user} logout={logout} signedOut={signedOut} authError={error} />
  </PreferencesProvider>;
}

function Workspace({user,logout:signOut,signedOut,authError}:{user:User;logout:()=>Promise<void>;signedOut:()=>void;authError:string}) {
  const [menuOpen,setMenuOpen]=useState(false);
  const menuButton=useRef<HTMLButtonElement>(null);
  const shellNav=useRef<HTMLElement>(null);
  useEffect(()=>{
    if(!menuOpen)return;
    const close=(event:KeyboardEvent)=>{if(event.key==='Escape'){setMenuOpen(false);menuButton.current?.focus();}};
    const outside=(event:PointerEvent)=>{if(!shellNav.current?.contains(event.target as Node))setMenuOpen(false);};
    document.addEventListener('keydown',close);document.addEventListener('pointerdown',outside);
    return()=>{document.removeEventListener('keydown',close);document.removeEventListener('pointerdown',outside);};
  },[menuOpen]);
  const url=useLocation();
  useEffect(()=>setMenuOpen(false),[url]);
  const route=parseRoute(location.pathname,location.search);const page=route.kind;
  const setPage=(page:string)=>navigate(({explorer:'/',deals:'/deals',admin:'/administration',account:'/account',companion:'/companion'} as Record<string,string>)[page]||'/');
  useEffect(()=>{
    if(restoration()?.focus)return;
    const focus=()=>{const h=document.querySelector<HTMLElement>('main h1');if(!h)return false;h.tabIndex=-1;h.focus({preventScroll:true});return true;};
    if(focus())return;
    const observer=new MutationObserver(()=>{if(focus())observer.disconnect();});observer.observe(document.body,{childList:true,subtree:true});return()=>observer.disconnect();
  },[location.pathname]);
  const marketList = useQuery({
    queryKey:["private","workspace-markets",user.id],
    queryFn:({signal})=>api<{markets:Market[]}>("/markets","GET",undefined,signal),
    refetchInterval:60_000,
  });
  const environment = useQuery({
    queryKey:["private","environment"],
    queryFn:({signal})=>api<{read_only:boolean;review_fixtures?:boolean}>("/environment","GET",undefined,signal),
  });
  const markets = marketList.data?.markets ?? [];
  const marketsReady = Boolean(marketList.data);
  const environmentReady = Boolean(environment.data);
  const readOnly = environment.data?.read_only ?? true;
  const fixtureReview = environment.data?.review_fixtures;
  const preferences=usePreferences();
  const market=preferredMarket(markets,preferences.values.market_id);
  const setMarket=(id:number)=>preferences.update({market_id:id});
  const loadMarkets=async()=>{await marketList.refetch({throwOnError:true});};
  async function logout() { await preferences.flush(); await signOut(); }
  const names: Record<string, string> = {
    explorer: "Market Explorer",
    deals: "Deal Finder",
    admin: "Administration",
    account: "Account & devices",
    companion: "Desktop Companion",
    item:"Item Details",missing:"Page not found",
  };
  return (
    <>
      <aside className={`app-navigation ${menuOpen ? "navigation-open" : ""}`} ref={shellNav}>
        <a
          href="#explorer"
          className="brand"
          onClick={event => {event.preventDefault();setMenuOpen(false);setPage("explorer");}}
        >
          <span className="sigil">T</span>
          <span>
            TWICHUI<small>{fixtureReview ? "REVIEW · SYNTHETIC DATA" : "MARKET INTELLIGENCE"}</small>
          </span>
        </a>
        <button ref={menuButton} className="mobile-menu-button secondary" aria-expanded={menuOpen} aria-controls="app-menu" onClick={()=>setMenuOpen(open=>!open)}>{menuOpen ? "Close" : "Menu"}</button>

        <div id="app-menu" className="app-menu">
        <nav aria-label="Main navigation">
          {[
            "explorer",
            "deals",
            ...(user.role === "admin" ? ["admin"] : []),
            "account",
            "companion",
          ].map((key) => (
            <button
              key={key}
              className={page === key || (page === "item" && key === "explorer") ? "active" : ""}
              aria-current={page === key || (page === "item" && key === "explorer") ? "page" : undefined}
              onClick={() => {setMenuOpen(false);if(page===key)menuButton.current?.focus();setPage(key);}}
            >
              {names[key]}
            </button>
          ))}
        </nav>
        {page === "admin" && user.role === "admin" && <nav className="admin-sidebar-sections" aria-label="Administration sections">
          {administrationGroups.map(group => <div key={group.label}><h2>{group.label}</h2>
            {group.sections.map(({id,label}) => <a key={id} href={id==="overview" ? "/administration" : `/administration?admin_tab=${id}`}
              aria-current={administrationSection(url)===id ? "page" : undefined}
              onClick={event=>{if(event.button===0&&!event.ctrlKey&&!event.metaKey&&!event.shiftKey&&!event.altKey){event.preventDefault();navigate(event.currentTarget.getAttribute("href")!);}}}>{label}</a>)}
          </div>)}
        </nav>}
        <div className="account-info">
          <strong>{user.username}</strong>
          <small>{user.role === "admin" ? "Administrator" : "Member"}</small>
          <button className="text-button" onClick={logout}>
            Sign out
          </button>
        </div>
        </div>
      </aside>
      <div className="workspace">
        <header>
          <span>
            THE AUCTIONEER’S LEDGER <i>/</i> {names[page]}
          </span>
          <span className="badge">{fixtureReview ? "Review · synthetic data" : "Private"}</span>
        </header>
        <main>
          {environmentReady && readOnly && <p className="notice" role="status">Interactive preview · Your preferences save automatically. Collection and account administration are read-only.</p>}
          <PreferenceStatus />
          {page!=="item" && preferences.values.market_id !== null && !markets.some(m => m.id === preferences.values.market_id) && markets.length > 0 && <p className="notice">Your preferred market is unavailable. Your saved choice is retained.</p>}
          {authError && <p className="notice error" role="alert">{authError}</p>}
          {marketList.error && <p className="notice error" role="alert">The list of markets could not be refreshed. <button onClick={()=>marketList.refetch()}>Retry markets</button></p>}
          {environment.error && <p className="notice error" role="alert">The website could not check which actions are available. <button onClick={()=>environment.refetch()}>Retry access check</button></p>}
          <Suspense fallback={<Loading label="Opening page…" skeleton/>}>
          {page === "explorer" && (marketsReady || !marketList.error) && (
            <Explorer
              marketsReady={marketsReady}
              markets={markets}
              market={market}
              setMarket={setMarket}
              searchParams={new URL(url,location.origin).search}
            />
          )}{" "}
          {page === "deals" && (marketsReady || !marketList.error) && (
            <Deals
              marketsReady={marketsReady}
              markets={markets}
              market={market}
              setMarket={setMarket}
              searchParams={new URL(url,location.origin).search}
            />
          )}{" "}
          {page === "admin" && user.role === "admin" && (!environmentReady || !marketsReady) && !environment.error && !marketList.error && <Loading label="Loading administration…" skeleton/>}
          {page === "admin" && user.role === "admin" && environmentReady && marketsReady && (
            <Administration
              user={user}
              markets={markets}
              readOnly={readOnly}
              refreshMarkets={loadMarkets}
            />
          )}{" "}
          {page === "account" && !environmentReady && !environment.error && <Loading label="Loading account settings…" skeleton/>}
          {page === "account" && environmentReady && (
            <Account readOnly={readOnly} userId={user.id} openCompanion={()=>navigate('/companion?setup=1')}
              signedOut={signedOut}
            />
          )}
          {page === 'companion' && <Companion user={user} fixtureReview={fixtureReview}/>}
          {route.kind==='item'&&<ItemDetails route={route} markets={markets} marketsReady={marketsReady}/>}
          {(page==='missing'||(page==='admin'&&user.role!=='admin'))&&<section className="empty panel"><h1>{page==='admin'?'Administrator access required':'Page not found'}</h1><p>{route.kind==='missing'?route.error:'This account does not have administration access.'}</p><a href="/" onClick={e=>{e.preventDefault();navigate('/');}}>Back to Explorer</a></section>}
          </Suspense>
        </main>
        <footer>
          TWICHUI MARKET
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
          <Loading label="Loading market tools…" />
        }
      >
        <App />
      </Suspense>
    </QueryClientProvider>
  </React.StrictMode>,
);
