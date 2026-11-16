import { ProviderRateLimits, type RateStatus } from "./provider-rate-limits";
import { useState } from "react";
import { DataTable } from "./data-table";
import { LocalTime, ProviderEmblem, Status, useRecordPage } from "./admin-table";
import { MetadataAttempts } from "./metadata-attempts";
import { ProviderHealth, UnresolvedNames } from "./metadata-records";
import { useQuery } from "@tanstack/react-query";
import { api, when } from "./api";
import { Market } from "./types";
import { MarketSelect } from "./research";

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
interface Overview {
  observed: number; resolved_names: number; missing_names: number; name_percent: number | null;
  primary_names: number; supplemental_names: number; primary_pending: number; primary_missing_responses: number;
  icons_available: number; icons_missing: number; last_enrichment: string | null; pending_queue: number; active_jobs: number;
  provider_name_overlap: number; conflicting_names: number; provider_records: { provider: string; checked: number; names_available: number; name_only?: number; detailed_records?: number; fields_available?: Record<string, number>; builds?: {build: string | null; records: number}[] }[];
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

function useProviders() {
  return useQuery({ queryKey: ["private", "metadata-providers"], queryFn: ({ signal }) => api<Providers>("/admin/metadata-providers", "GET", undefined, signal), refetchInterval: 5000 });
}
function ErrorNotice({ error }: { error: string }) { return error ? <p className="notice error" role="alert">{error}</p> : null; }

export function DataSources({ readOnly = false }: { readOnly?: boolean }) {
  const data = useProviders();
  const [editing, setEditing] = useState<string | null>(null), [error, setError] = useState(""), [message, setMessage] = useState(""), [busy, setBusy] = useState(false);
  async function action(work: () => Promise<unknown>, message: string) {
    setBusy(true); setError(""); setMessage("");
    try { await work(); setMessage(message); await data.refetch(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <section aria-labelledby="data-sources-heading" className="metadata-admin">
    <div className="eyebrow">SERVER CONNECTIONS</div><h2 id="data-sources-heading">Data Sources</h2>
    <p className="muted">Provider keys stay on the server. Replacement keys are validated in the background before becoming active.</p>
    <ErrorNotice error={error || data.error?.message || ""} />
    {message && <p role="status" className="notice success">{message}</p>}
    {data.isPending && <p role="status">Loading data sources…</p>}
    {data.data && !data.data.credential_storage_ready && <p className="notice">API key storage needs an owner-managed encryption key file. Keyless recovery remains available.</p>}
    <ProviderHealth providers={data.data?.providers || []} />
    <h3>Provider settings and credentials</h3><div className="metadata-provider-grid">{data.data?.providers.map(provider => <section className="panel padded metadata-provider" key={provider.provider} aria-label={`${provider.name} connection`}>
      <div className="title-row"><h3>{provider.name}</h3><span className="tag">{provider.expiration_warning === "expired" ? "Key expired" : provider.validation_error || provider.recent_error ? "Needs attention" : provider.last_validated_at ? "Validated" : provider.configured ? "Key configured" : provider.key_required ? "Not configured" : "Keyless access"}</span></div>
      <p className="small muted">{provider.note}</p>
      {provider.website_verification && <p className="small muted">Website verification: unknown — confirm in your <a href="https://foreverdb.net/developers" target="_blank" rel="noopener noreferrer">ForeverDB account</a>. <a href={provider.website_verification.proof_url} target="_blank" rel="noopener noreferrer">Ownership proof</a> · {provider.website_verification.developer_id}. API connectivity does not confirm verification or website key scope.</p>}
      {provider.expiration_warning && <p className="notice" role="status">{metadataStatus(provider.expiration_warning)}. Replace this key before it expires.</p>}
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
      {provider.rate_limits && <ProviderRateLimits key={JSON.stringify(provider.rate_limits.configured)} provider={provider} disabled={busy || readOnly} save={config => action(() => api(`/admin/metadata-providers/${provider.provider}/rate-limits`, "PATCH", config), `${provider.name} rate limits saved. Usage and cooldowns are preserved.`)}/>}
      <a href={provider.url} target="_blank" rel="noopener noreferrer" className="small">Provider documentation &amp; attribution</a>
    </section>)}</div>
  </section>;
}

export function ItemMetadataAdmin({ markets, readOnly = false }: { markets: Market[]; readOnly?: boolean }) {
  const [market, setMarket] = useState(markets[0]?.id || 0), [mode, setMode] = useState("single"), [selected, setSelected] = useState(["blizzard", "everloot"]), [preview, setPreview] = useState<{ item_count: number; estimated_requests: number; request_budget: number; note: string } | null>(null);
  const [error, setError] = useState(""), [message, setMessage] = useState(""), [busy, setBusy] = useState(false), [jobId, setJobId] = useState<number | null>(null), [resultAfter, setResultAfter] = useState(0);
  const [input, setInput] = useState({ item_id: "", limit: 100, request_budget: 100 });
  const providers = useProviders();
  const stats = useQuery({ queryKey: ["private", "metadata-overview", market], enabled: !!market, queryFn: ({ signal }) => api<Overview>(`/admin/item-metadata?market_id=${market}`, "GET", undefined, signal), refetchInterval: 5000 });
  const [relatedResource,setRelatedResource] = useState("professions/alchemy"), [relatedPages,setRelatedPages] = useState(1);
  const [jobState, setJobState] = useState(""), [jobSearch,setJobSearch]=useState("");
  const jobPage = useRecordPage<Job>("jobs", { q:jobSearch, market_id: String(market), ...(jobState ? {state:jobState}: {}) }, "id");
  const jobs = jobPage.query;
  const detail = useQuery({ queryKey: ["private", "metadata-job", jobId, resultAfter], enabled: !!jobId, queryFn: ({ signal }) => api<Job>(`/admin/item-metadata/jobs/${jobId}?after=${resultAfter}`, "GET", undefined, signal), refetchInterval: 3000 });
  const body = { market_id: market, mode, providers: selected, limit: input.limit, request_budget: input.request_budget, item_id: mode === "single" ? Number(input.item_id) || null : null };
  function resetPreview() { setPreview(null); setMessage(""); }
  async function action(work: () => Promise<void>) { setBusy(true); setError(""); try { await work(); await jobs.refetch(); await stats.refetch(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); } }
  const state = stats.data;
  return <section aria-labelledby="metadata-heading" className="metadata-admin">
    <div className="title-row"><div><div className="eyebrow">LOCAL ITEM CATALOG</div><h2 id="metadata-heading">Item Metadata</h2></div><MarketSelect markets={markets} market={market} setMarket={value => { setMarket(value); jobPage.reset(); resetPreview(); }} /></div>
    <p className="muted">Recover observed item names and base attributes. Unavailable provider metadata never means an auction item does not exist.</p>
    <ErrorNotice error={error || stats.error?.message || jobs.error?.message || detail.error?.message || providers.error?.message || ""} />
    {message && <p className="notice success" role="status">{message}</p>}
    {stats.isPending && <p role="status">Loading catalog measurements…</p>}
    {state?.provider_records.some(record=>record.name_only !== undefined) && <details><summary>Provider metadata coverage</summary><p className="small muted">Retained fields for observed items in this market. A missing field is unknown, not proof that the provider does not offer it.</p>{state.provider_records.map(record=><div key={record.provider}><strong>{record.provider}</strong><p className="small">{record.name_only ?? "Unknown"} name only · {record.detailed_records ?? "Unknown"} with details</p><p className="small">{Object.entries(record.fields_available || {}).map(([field,count])=>`${field.replaceAll("_", " ")}: ${count} available / ${Math.max(0,state.observed-count)} missing`).join(" · ")}</p><p className="small">{record.builds?.map(build=>`${build.build || "Unknown build"}: ${build.records} records`).join(" · ")}</p></div>)}</details>}
    {state && <><div className="metadata-stats">
      {[["Observed item IDs", state.observed], ["Resolved names", state.resolved_names], ["Name coverage", state.name_percent === null ? "No observations" : `${state.name_percent}%`], ["Missing names", state.missing_names], ["Icons available", state.icons_available], ["Icons missing", state.icons_missing]].map(([label, value]) => <div className="panel padded" key={label}><span className="small muted">{label}</span><strong>{value}</strong></div>)}
    </div><p className="small muted">Latest recorded market snapshot · Blizzard names {state.primary_names} · supplemental names {state.supplemental_names} · Blizzard pending {state.primary_pending} · Blizzard 404 responses {state.primary_missing_responses}</p><p className="small muted">Multiple name sources: {state.provider_name_overlap} · conflicting names: {state.conflicting_names}{state.provider_records.map(p => ` · ${p.provider}: ${p.names_available} source names`).join("")}</p>
    <p className="small">Last successful enrichment: {when(state.last_enrichment)} · Pending queue: {state.pending_queue} · Active jobs: {state.active_jobs}</p></>}
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
    <section className="panel padded"><h3>Import ForeverDB relationships</h3><p className="small muted">Import a bounded profession page, vendor inventory or item set into related item details. Each page shares existing provider quotas. Trainer, vendor and Classic evidence stays labelled.</p><form onSubmit={event=>{event.preventDefault();action(async()=>{const job=await api<{job_id:number}>("/admin/item-metadata/related-jobs","POST",{market_id:market,resource:relatedResource,pages:relatedPages});setJobId(job.job_id);setResultAfter(0);setMessage(`Related metadata job #${job.job_id} queued.`);});}}><label>Documented resource<input value={relatedResource} maxLength={80} onChange={event=>setRelatedResource(event.target.value)} placeholder="professions/alchemy, vendors/54, itemsets/1" required/></label><label>Maximum requests (20 recipes per page)<input type="number" min="1" max="10" value={relatedPages} onChange={event=>setRelatedPages(Number(event.target.value))}/></label><button disabled={busy||readOnly||!market}>Queue bounded import</button></form></section>
    <section className="panel padded"><h3>Recovery jobs</h3>
      <div className="toolbar"><label>Search job reference<input type="search" value={jobSearch} maxLength={64} onChange={e=>{setJobSearch(e.target.value);jobPage.reset();}}/></label><label>Job status<select value={jobState} onChange={e=>{setJobState(e.target.value);jobPage.reset();}}><option value="">All statuses</option>{["queued","running","paused","completed","cancelled"].map(value=><option key={value}>{value}</option>)}</select></label></div>
      <DataTable<Job> label="recovery jobs" data={jobs.data?.rows || []} server={jobPage.server} loading={jobs.isPending} error={jobs.error?.message} getRowId={row=>String(row.id)} columns={[
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
    <section className="panel padded"><h3>Provider health</h3><ProviderHealth providers={providers.data?.providers || []}/></section>
    <MetadataAttempts key={`attempts-${market}`} market={market} readOnly={readOnly}/>
    <UnresolvedNames key={`unresolved-${market}`} market={market} chooseItem={id=>{setMode("single");setInput({...input,item_id:String(id)});resetPreview();document.querySelector<HTMLInputElement>('input[type="number"]')?.focus();}}/>
  </section>;
}

export function JobWaiting({job}:{job:Pick<Job,"waiting">}) { return <>{job.waiting?.map(wait => <p className="small" key={wait.provider}>Waiting for {wait.provider === "foreverdb" ? "ForeverDB" : wait.provider === "thewowdb" ? "TheWoWDB" : wait.provider === "everloot" ? "Everloot" : "Blizzard"} rate limit — resumes at <LocalTime value={wait.resumes_at}/></p>)}</>; }
