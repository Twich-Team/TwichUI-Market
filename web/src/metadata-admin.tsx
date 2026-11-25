import { RecoveryTracker } from "./recovery-tracker";
import { Loading } from "./loading";
import { MetadataSummary, ProviderCoverage } from "./metadata-coverage";
import { ProviderRateLimits, SourceUsage, applicationLimitReached, type RateStatus } from "./provider-rate-limits";
import { useEffect, useState } from "react";
import { DataTable } from "./data-table";
import { LocalTime, ProviderEmblem, Status, useRecordPage } from "./admin-table";
import { MetadataAttempts } from "./metadata-attempts";
import { ProviderHealth, UnresolvedNames } from "./metadata-records";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { Market } from "./types";
import { MarketSelect } from "./research";
import { navigate, supportedId, useLocation } from "./navigation";

export interface MetadataProvider {
  rate_limits?: RateStatus;
  website_verification?: {status: string; proof_url: string; developer_id: string};
  key_scope?: string;
  provider: string; name: string; enabled: boolean; automatic: boolean; configured: boolean;
  key_required: boolean; credential_status: string; validation_pending: boolean; validation_error: string | null;
  last_validated_at: string | null; expires_at: string | null; expiration_warning: string | null;
  last_success: string | null; recent_error: string | null; cooldown_until: string | null;
  hourly_budget: number; daily_budget: number; hour_used: number; day_used: number; note: string; url: string;
}
interface Providers { credential_storage_ready: boolean; providers: MetadataProvider[] }
interface Result { provider: string; item_id?: number; status: string; recovered_fields?: string[]; imported_items?: number; source?: { provider?: string; build?: string; confidence?: string; attribution?: { text: string; url: string } } }
interface Job {
  recovered: number; failed: number; created_at: string; updated_at: string; id: number; mode: string; state: string; total: number; counts: Record<string, number>;
  requests_used: number; request_budget: number; providers: string[]; waiting?: {provider:string;resumes_at:string}[]; retry_allowance_needed?: boolean;
  results?: { id: number; item_id: number; provider: string; state: string; available_at: string; result: Result | null }[];
  next_after?: number | null;
}
export interface MetadataOverview {
  measured_at:string;
  attributes_available:number; scoped_pending_items:number; unknown_not_tried:number; tried_unavailable:number; failed_or_blocked:number; checked_unresolved:number; coverage_identity:string; attributes_definition:string; recovery_notice:string;
  observed: number; resolved_names: number; missing_names: number; name_percent: number | null;
  primary_names: number; supplemental_names: number; primary_pending: number; primary_missing_responses: number;
  icons_available: number; icons_missing: number; last_enrichment: string | null; pending_queue: number; active_jobs: number;
  provider_name_overlap: number; conflicting_names: number; provider_records: { provider: string; checked: number; names_available: number; name_only?: number; detailed_records?: number; fields_available?: Record<string, number>; overlapping_names?:number; conflicting_names?:number; builds?: {build: string | null; records: number}[] }[];
  recent_results: { item_id: number; provider: string; at: string; result: Result }[];
}
const labels: Record<string, string> = {
  authorization: "Authorization failed", forbidden: "Access forbidden", rate_limited: "Provider rate limit",
  metadata_unavailable: "Metadata unavailable from this provider", transport_or_schema: "Connection or response validation failed",
  credential_unavailable: "Credential unavailable", secret_unavailable: "Credential storage unavailable", cached: "Refresh window has not expired",
  provider_disabled: "Provider disabled", job_budget: "Job request budget reached", available: "Metadata stored locally",
  not_modified: "Existing metadata confirmed", subscription_required: "Provider subscription required",
};
export const metadataStatus = (value: string | null | undefined) => value ? labels[value] || value.replaceAll("_", " ") : "None";

function useProviders(enabled = true, refetchInterval = 5_000) {
  return useQuery({
    enabled,
    queryKey: ["private", "metadata-providers"],
    queryFn: ({ signal }) => api<Providers>("/admin/metadata-providers", "GET", undefined, signal),
    refetchInterval,
  });
}
function ErrorNotice({ error }: { error: string }) { return error ? <p className="notice error" role="alert">{error}</p> : null; }

function sourceRecovery(provider: MetadataProvider) {
  if (!provider.enabled) return { group: 'Disabled', label: 'Source disabled', tone: 'neutral' } as const;
  if (provider.key_required && !provider.configured && provider.validation_pending)
    return { group: 'Waiting', label: 'Waiting for key check', tone: 'warning' } as const;
  if ((provider.key_required && !provider.configured) || provider.expiration_warning === 'expired')
    return { group: 'To review', label: 'Recovery blocked', tone: 'warning' } as const;
  if (provider.rate_limits?.cooling_down)
    return { group: 'Waiting', label: 'Recovery cooling down', tone: 'warning' } as const;
  if (applicationLimitReached(provider.rate_limits))
    return { group: 'Waiting', label: 'Waiting for quota', tone: 'warning' } as const;
  if (provider.validation_error || provider.recent_error)
    return { group: 'To review', label: 'Review connection', tone: 'warning' } as const;
  return provider.automatic
    ? { group: 'Automatic on', label: 'Automatic recovery on', tone: 'success' } as const
    : { group: 'Automatic off', label: 'Automatic recovery off', tone: 'neutral' } as const;
}

export type MetadataSourceSummary = ReturnType<typeof sourceRecovery> & {
  id: string;
  name: string;
  enabled: boolean;
  automatic: boolean;
  lastSuccess: string | null;
};

export function useMetadataSourceSummary(enabled: boolean) {
  const query = useProviders(enabled, 60_000);
  const sources: MetadataSourceSummary[] | undefined = query.data?.providers.map(provider => ({
    id: provider.provider,
    name: provider.name,
    enabled: provider.enabled,
    automatic: provider.automatic,
    lastSuccess: provider.last_success,
    ...sourceRecovery(provider),
  }));
  return { sources, isPending: query.isPending, isError: query.isError };
}

export function defaultMetadataMarket(markets: Market[]): Market | undefined {
  return markets.find(market => market.enabled) ?? markets[0];
}

export function useMetadataCoverage(market: number, enabled = true, refetchInterval = 60_000) {
  return useQuery({
    enabled: enabled && !!market,
    queryKey: ["private", "metadata-overview", market],
    queryFn: ({ signal }) => api<MetadataOverview>(`/admin/item-metadata?market_id=${market}`, "GET", undefined, signal),
    refetchInterval,
  });
}

export function DataSources({ readOnly = false }: { readOnly?: boolean }) {
  const data = useProviders();
  const [editing, setEditing] = useState<string | null>(null), [error, setError] = useState(""), [message, setMessage] = useState(""), [busy, setBusy] = useState(false);
  async function action(work: () => Promise<unknown>, message: string) {
    setBusy(true); setError(""); setMessage("");
    try { await work(); setMessage(message); await data.refetch(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  if (data.isPending) return <><h1>Data Sources</h1><Loading label="Loading data sources…"/></>;
  const sources = (data.data?.providers || []).map(provider => ({provider, recovery: sourceRecovery(provider)}));
  const groups = new Map<string, number>();
  for (const { recovery } of sources) groups.set(recovery.group, (groups.get(recovery.group) ?? 0) + 1);
  return <section aria-labelledby="data-sources-heading" className="metadata-admin">
    <h1 id="data-sources-heading">Data Sources</h1>
    {data.error && <button onClick={()=>void data.refetch()}>Retry data sources</button>}
    <ErrorNotice error={error || data.error?.message || ""} />
    {busy && <Loading label="Submitting metadata operation…"/>}
    {message && <p role="status" className="notice success">{message}</p>}
    {sources.length > 0 && <section className="source-recovery-summary" aria-labelledby="source-recovery-summary-heading">
      <h2 id="source-recovery-summary-heading">Recovery across {sources.length} sources</h2>
      <ul>{['Automatic on','To review','Waiting','Automatic off','Disabled'].filter(group=>groups.has(group)).map(group=>
        <li key={group}><strong>{groups.get(group)}</strong> {group.toLowerCase()}</li>)}</ul>
    </section>}
    {data.error && data.data && <p role="status">Showing the last available readings.</p>}
    <div className="metadata-provider-grid source-provider-grid">{sources.map(({provider, recovery}) => {
      const needsKey = provider.key_required && !provider.configured;
      const expired = provider.expiration_warning === "expired";
      const coolingDown = provider.rate_limits?.cooling_down;
      const auth = provider.validation_pending ? "Validation queued"
        : expired ? "Key expired"
        : provider.validation_error ? "Last validation failed"
        : needsKey ? "Key needed"
        : provider.last_validated_at ? "Validated"
        : provider.configured ? "Key configured" : "Keyless access";
      return <section className="panel padded metadata-provider source-provider" key={provider.provider} aria-label={`${provider.name} connection`}>
      <div className="source-provider-heading"><h2>{provider.name}</h2><Status tone={recovery.tone}>{recovery.label}</Status></div>
      <p className="source-authentication">Authentication · {auth}</p>
      {provider.enabled && (needsKey || expired) && <p className="source-action-note">
        {provider.validation_pending ? "A key check is queued."
          : provider.provider === "blizzard" ? "Ask the host administrator to configure Blizzard credentials."
          : !data.data?.credential_storage_ready ? "Ask the host administrator to enable credential storage."
          : needsKey ? "Add an API key in Edit settings to enable recovery." : "Replace the expired key in Edit settings."}
      </p>}
      {provider.enabled && !needsKey && !expired && !coolingDown && (provider.validation_error || provider.recent_error) &&
        <p className="source-action-note">{metadataStatus(provider.validation_error || provider.recent_error)}. Review the connection in Edit settings.</p>}
      <SourceUsage name={provider.name} status={provider.rate_limits} availableForRecovery={provider.enabled&&!needsKey&&!expired}/>
      <details className="provider-edit"><summary>Edit settings</summary>
      {provider.expiration_warning && <p className="notice" role="status">{metadataStatus(provider.expiration_warning)}. Replace this key to keep access.</p>}
      <form className="metadata-config" key={`${provider.provider}-${provider.enabled}-${provider.automatic}-${provider.hourly_budget}-${provider.daily_budget}`} onSubmit={event => {
        event.preventDefault(); const form = new FormData(event.currentTarget);
        action(() => api(`/admin/metadata-providers/${provider.provider}`, "PATCH", { enabled: form.has("enabled"), automatic: form.has("automatic") }), `${provider.name} settings saved.`);
      }}>
        <label className="check"><input name="enabled" type="checkbox" defaultChecked={provider.enabled} disabled={busy || readOnly} />Enabled</label>
        <label className="check"><input name="automatic" type="checkbox" defaultChecked={provider.automatic} disabled={busy || readOnly} />Automatic recovery</label>
        <button disabled={busy || readOnly}>Save settings</button>
      </form>
      <div className="metadata-actions"><button disabled={busy || readOnly} onClick={() => action(() => api(`/admin/metadata-providers/${provider.provider}/test`, "POST"), "Connection test queued. Provider limits still apply.")}>Test Connection</button>
        {["everloot", "foreverdb"].includes(provider.provider) && <button disabled={busy || readOnly || !data.data?.credential_storage_ready} onClick={() => { setEditing(editing === provider.provider ? null : provider.provider); setError(""); }}>{provider.configured ? "Replace API Key" : "Add API Key"}</button>}</div>
      {editing === provider.provider && <form className="metadata-key-form" autoComplete="off" onSubmit={event => {
        event.preventDefault(); const formElement = event.currentTarget; const form = new FormData(formElement);
        const key = String(form.get("key")); const date = String(form.get("expires"));
        formElement.reset(); setEditing(null);
        action(() => api(`/admin/metadata-providers/${provider.provider}/credentials`, "POST", { key, expires_at: date ? new Date(`${date}T23:59:59Z`).toISOString() : null }), "Replacement queued for validation. The previous key remains active until validation succeeds.");
      }}>
        <h4>{provider.name} API key</h4><label>New API key<input name="key" type="password" autoComplete="new-password" minLength={12} maxLength={2048} required /></label>
        <label>Expiration date (optional)<input name="expires" type="date" /></label>
        <p className="small muted">The key is encrypted at rest and cannot be retrieved through this website.</p>
        <div className="metadata-actions"><button className="primary" disabled={busy || readOnly}>Validate &amp; replace</button><button type="button" onClick={() => setEditing(null)}>Cancel</button></div>
      </form>}
      <details className="provider-edit"><summary>Rate limits and usage</summary>{provider.rate_limits && <ProviderRateLimits key={JSON.stringify(provider.rate_limits.configured)} provider={provider} disabled={busy || readOnly} save={config => action(() => api(`/admin/metadata-providers/${provider.provider}/rate-limits`, "PATCH", config), `${provider.name} rate limits saved. Usage and cooldowns are preserved.`)}/>}</details>
      </details>
      <details className="provider-edit"><summary>Source details</summary>
      <p className="muted">{provider.note}</p>
      {provider.website_verification && <p className="muted">Website verification: unknown. Check your <a href="https://foreverdb.net/developers" target="_blank" rel="noopener noreferrer">ForeverDB account</a> and <a href={provider.website_verification.proof_url} target="_blank" rel="noopener noreferrer">ownership proof</a>.</p>}
      <a href={provider.url} target="_blank" rel="noopener noreferrer" className="small">Provider documentation &amp; attribution</a>
      </details>
    </section>;
    })}</div>
    {data.data && !data.data.credential_storage_ready && <p className="source-configuration-note">API key storage requires a host-managed encryption key. Keyless access remains available.</p>}
    {!!data.data?.providers.length && <details className="panel padded"><summary>Provider evidence</summary><ProviderHealth providers={data.data.providers}/></details>}
  </section>;
}

export function ItemMetadataAdmin({ markets, readOnly = false }: { markets: Market[]; readOnly?: boolean }) {
  const location = useLocation();
  const params = new URLSearchParams(location.split("?")[1]);
  const view = params.get("metadata_view") || "overview";
  const views = [["overview","Coverage"],["missing","Missing metadata"],["jobs","Recovery jobs"],["tracker","Recovery Tracker"],["evidence","Provider evidence"]];
  function setView(next: string) {
    params.set("admin_tab","metadata");
    if (next==="overview") params.delete("metadata_view"); else params.set("metadata_view",next);
    navigate("/administration?"+params);
  }
  const requestedMarket = supportedId(params.get("market_id"));
  const [market, setMarket] = useState(() => markets.find(row => row.id === requestedMarket)?.id ?? defaultMetadataMarket(markets)?.id ?? 0);
  const [mode, setMode] = useState("single"), [selected, setSelected] = useState(["blizzard", "everloot"]), [preview, setPreview] = useState<{ item_count: number; estimated_requests: number; request_budget: number; note: string } | null>(null);
  const [error, setError] = useState(""), [message, setMessage] = useState(""), [busy, setBusy] = useState(false), [jobId, setJobId] = useState<number | null>(null), [resultAfter, setResultAfter] = useState(0);
  useEffect(() => {
    if (!market && markets.length) setMarket(defaultMetadataMarket(markets)?.id ?? 0);
  }, [market, markets]);
  const [input, setInput] = useState({ item_id: "", limit: 100, request_budget: 100 });
  const providers = useProviders(view === "jobs");
  const stats = useMetadataCoverage(market);
  const [relatedResource,setRelatedResource] = useState("professions/alchemy"), [relatedPages,setRelatedPages] = useState(1);
  const [jobState, setJobState] = useState(""), [jobSearch,setJobSearch]=useState("");
  const jobPage = useRecordPage<Job>("jobs", { q:jobSearch, market_id: String(market), ...(jobState ? {state:jobState}: {}) }, "id", true, view === "jobs" && !!market);
  const jobs = jobPage.query;
  const detail = useQuery({ queryKey: ["private", "metadata-job", jobId, resultAfter], enabled: view === "jobs" && !!jobId, queryFn: ({ signal }) => api<Job>(`/admin/item-metadata/jobs/${jobId}?after=${resultAfter}`, "GET", undefined, signal), refetchInterval: 3000 });
  const body = { market_id: market, mode, providers: selected, limit: input.limit, request_budget: input.request_budget, item_id: mode === "single" ? Number(input.item_id) || null : null };
  function resetPreview() { setPreview(null); setMessage(""); }
  function selectMarket(value: number) {
    setMarket(value);
    jobPage.reset();
    setJobId(null);
    resetPreview();
  }
  async function action(work: () => Promise<void>) { setBusy(true); setError(""); try { await work(); await jobs.refetch(); await stats.refetch(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); } }
  const state = stats.data;
  return <section aria-labelledby="metadata-heading" className="metadata-admin">
    <div className="title-row"><h1 id="metadata-heading">Item Metadata</h1><MarketSelect markets={markets} market={market} setMarket={selectMarket} /></div>
    <nav className="admin-view-switch" aria-label="Item metadata views">
      {views.map(([id,label])=><button key={id} aria-current={view===id?"page":undefined} aria-pressed={view===id} onClick={()=>setView(id)}>{label}</button>)}
    </nav>
    <ErrorNotice error={error || (view==="overview"?stats.error?.message:view==="jobs"?jobs.error?.message||detail.error?.message:undefined) || ""} />
    {message && <p className="notice success" role="status">{message}</p>}
    {!market && <p>Choose a configured market to see its item metadata.</p>}
    {view==="overview" && !!market && <>{stats.isPending && <Loading label="Loading catalog measurements…" />}{state && <MetadataSummary state={state} openRecovery={()=>setView("tracker")}/>}</>}
    {view==="tracker" && !!market && <RecoveryTracker key={market} market={market} readOnly={readOnly}/>}
    {view==="missing" && !!market && <UnresolvedNames key={market} market={market} chooseItem={id=>{setMode("single");setInput({...input,item_id:String(id)});resetPreview();setView("jobs");}}/>}
    {view==="evidence" && !!market && <>
      <MetadataAttempts key={market} market={market} readOnly={readOnly}/>
      {stats.isPending && <Loading label="Loading provider coverage…" />}
      {stats.error && <p role="alert">Provider coverage could not be loaded. <button onClick={()=>void stats.refetch()}>Retry</button></p>}
      {state && <ProviderCoverage state={state}/>}
    </>}
    {view==="jobs" && !!market && <>
    <section className="panel padded"><h3>Recover item metadata</h3>
      <form onSubmit={event => { event.preventDefault(); action(async () => setPreview(await api("/admin/item-metadata/preview", "POST", body))); }} onChange={resetPreview}>
        <div className="metadata-form-row"><label>Recovery action<select value={mode} onChange={e => { setMode(e.target.value); if (e.target.value === "bulk") setSelected(["everloot"]); }}>
          <option value="single">Recover one item</option><option value="missing">Recover missing items</option><option value="stale">Refresh stale metadata</option><option value="bulk">Import Everloot client attributes</option>
        </select></label>
        {mode === "single" ? <label>Numeric item ID<input type="number" min="1" max="2147483647" required value={input.item_id} onChange={e => setInput({ ...input, item_id: e.target.value })} /></label> : <label>Maximum items<input type="number" min="1" max="1000" required value={input.limit} onChange={e => setInput({ ...input, limit: Number(e.target.value) })} /></label>}
        <label>Request budget<input type="number" min="1" max="1000" required value={input.request_budget} onChange={e => setInput({ ...input, request_budget: Number(e.target.value) })} /></label></div>
        <fieldset className="metadata-provider-options"><legend>Providers</legend>{providers.data?.providers.map(provider => <label className="check" key={provider.provider}><input type="checkbox" checked={selected.includes(provider.provider)} disabled={mode === "bulk" && provider.provider !== "everloot"} onChange={e => setSelected(e.target.checked ? [...selected, provider.provider] : selected.filter(p => p !== provider.provider))} />{provider.name}{!provider.enabled ? " · disabled" : ""}</label>)}</fieldset>
        <button disabled={busy || !market || !selected.length}>Preview recovery</button>
      </form>
      {preview && <div className="metadata-preview" role="status"><h4>Recovery preview</h4><p>{preview.item_count} item{preview.item_count === 1 ? "" : "s"} · up to {preview.estimated_requests} requests · budget {preview.request_budget}</p><p className="small muted">{preview.note}</p>
        <button className="primary" disabled={busy || readOnly || !preview.item_count} onClick={() => action(async () => { const job = await api<{ job_id: number }>("/admin/item-metadata/jobs", "POST", body); setJobId(job.job_id); setResultAfter(0); setPreview(null); setMessage(`Recovery job #${job.job_id} queued. You can leave this page while it runs.`); })}>Start recovery</button></div>}
    </section>
    <details className="panel padded"><summary>Advanced · Import ForeverDB relationships</summary><p className="small muted">Import a bounded profession page, vendor inventory or item set into related item details. Each page shares existing provider quotas. Trainer, vendor and Classic evidence stays labelled.</p><form onSubmit={event=>{event.preventDefault();action(async()=>{const job=await api<{job_id:number}>("/admin/item-metadata/related-jobs","POST",{market_id:market,resource:relatedResource,pages:relatedPages});setJobId(job.job_id);setResultAfter(0);setMessage(`Related metadata job #${job.job_id} queued.`);});}}><label>Documented resource<input value={relatedResource} maxLength={80} onChange={event=>setRelatedResource(event.target.value)} placeholder="professions/alchemy, vendors/54, itemsets/1" required/></label><label>Maximum requests (20 recipes per page)<input type="number" min="1" max="10" value={relatedPages} onChange={event=>setRelatedPages(Number(event.target.value))}/></label><button disabled={busy||readOnly||!market}>Queue relationship import</button></form></details>
    <section className="panel padded"><h3>Recovery jobs</h3>
      <div className="toolbar"><label>Search job reference<input type="search" value={jobSearch} maxLength={64} onChange={e=>{setJobSearch(e.target.value);jobPage.reset();}}/></label><label>Job status<select value={jobState} onChange={e=>{setJobState(e.target.value);jobPage.reset();}}><option value="">All statuses</option>{["queued","running","paused","completed","cancelled"].map(value=><option key={value}>{value}</option>)}</select></label></div>
      <DataTable<Job> emptyMessage="No recovery jobs match these filters. Preview a recovery to start a new job." label="recovery jobs" data={jobs.data?.rows || []} server={jobPage.server} loading={jobs.isPending} error={jobs.error?.message} getRowId={row=>String(row.id)} columns={[
        {accessorKey:"id",header:"Job",enableHiding:false,cell:({row})=><button className="text-button" onClick={()=>{setJobId(row.original.id);setResultAfter(0);}}>Job #{row.original.id} · {row.original.mode}</button>},
        {accessorKey:"mode",header:"Recovery type"},
        {id:"providers",header:"Providers",enableSorting:false,cell:({row})=>row.original.providers.map(provider=><ProviderEmblem key={provider} provider={provider}/>)},
        {accessorKey:"state",header:"Status",cell:({row})=><><Status>{row.original.state}</Status><JobWaiting job={row.original}/></>},
        {id:"progress",header:"Progress",enableSorting:false,cell:({row})=>`${["completed","failed","skipped","cancelled"].reduce((n,key)=>n+(row.original.counts[key]||0),0)} / ${row.original.total}`},
        {id:"recovered",header:"Recovered / failed / skipped",enableSorting:false,cell:({row})=>`${row.original.recovered||0} / ${row.original.failed||0} / ${row.original.counts.skipped||0}`},
        {accessorKey:"created_at",header:"Started",cell:({row})=><LocalTime value={row.original.created_at}/>},
        {accessorKey:"updated_at",header:"Updated",cell:({row})=><LocalTime value={row.original.updated_at}/>},
        {id:"actions",header:"Actions",enableSorting:false,cell:({row})=><div className="metadata-actions">{row.original.retry_allowance_needed && <button disabled={busy||readOnly} onClick={()=>action(async()=>{await api(`/admin/item-metadata/jobs/${row.original.id}/retry-allowance`,"POST",{additional_requests:1});})}>Allow one retry</button>}{["queued","running","paused"].includes(row.original.state) && <><button disabled={busy||readOnly} onClick={()=>action(async()=>{await api(`/admin/item-metadata/jobs/${row.original.id}/${row.original.state==="paused"?"resume":"pause"}`,"POST");})}>{row.original.state==="paused"?"Resume":"Pause"}</button><button disabled={busy||readOnly} onClick={()=>action(async()=>{await api(`/admin/item-metadata/jobs/${row.original.id}/cancel`,"POST");})}>Cancel</button></>}</div>},
      ]} renderDetails={row=><p>Job #{row.id} · {row.requests_used}/{row.request_budget} requests. Completed tasks include missing or empty responses; see provider results for actual recovery.{row.retry_allowance_needed && " Rate-limited work is preserved. The campaign request budget is spent; allow another retry to continue."}</p>}/>
      {detail.data && <div className="metadata-job-detail"><h4>Job #{detail.data.id} results</h4><JobWaiting job={detail.data}/><progress aria-label="Recovery progress" max={Math.max(1, detail.data.total)} value={["completed", "failed", "skipped", "cancelled"].reduce((n, key) => n + (detail.data!.counts[key] || 0), 0)} />
        <p className="small muted">Search and sorting apply to this bounded result batch. Use Next results for the next batch.</p>
        <DataTable label="job results" data={detail.data.results || []} getRowId={row=>String(row.id)} columns={[
          {accessorKey:"item_id",header:"Item ID",cell:({row})=>`Item #${row.original.item_id}`},
          {accessorKey:"provider",header:"Provider",cell:({row})=><ProviderEmblem provider={row.original.provider}/>},
          {id:"status",header:"Result",accessorFn:row=>metadataStatus(row.result?.status||row.state)},
          {id:"fields",header:"Returned fields",accessorFn:row=>row.result?.recovered_fields?.join(", ")||"None"},
          {accessorKey:"available_at",header:"Eligible",cell:({row})=><LocalTime value={row.original.available_at}/>},
        ]}/>
        <div className="metadata-actions">{resultAfter > 0 && <button onClick={() => setResultAfter(0)}>First results</button>}{detail.data.next_after && <button onClick={() => setResultAfter(detail.data!.next_after!)}>Next results</button>}</div></div>}
    </section>
    </>}
  </section>;
}

export function JobWaiting({job}:{job:Pick<Job,"waiting">}) { return <>{job.waiting?.map(wait => <p className="small" key={wait.provider}>Waiting for {wait.provider === "foreverdb" ? "ForeverDB" : wait.provider === "thewowdb" ? "TheWoWDB" : wait.provider === "everloot" ? "Everloot" : "Blizzard"} rate limit — resumes at <LocalTime value={wait.resumes_at}/></p>)}</>; }
