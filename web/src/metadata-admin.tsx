import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, when } from "./api";
import { Market } from "./types";
import { MarketSelect } from "./research";

export interface MetadataProvider {
  provider: string; name: string; enabled: boolean; automatic: boolean; configured: boolean;
  key_required: boolean; credential_status: string; validation_pending: boolean; validation_error: string | null;
  last_validated_at: string | null; expires_at: string | null; expiration_warning: string | null;
  last_success: string | null; recent_error: string | null; cooldown_until: string | null;
  hourly_budget: number; daily_budget: number; hour_used: number; day_used: number; note: string; url: string;
}
interface Providers { credential_storage_ready: boolean; providers: MetadataProvider[] }
interface Result { provider: string; item_id?: number; status: string; recovered_fields?: string[]; imported_items?: number; source?: { provider?: string; build?: string; confidence?: string; attribution?: { text: string; url: string } } }
interface Job {
  id: number; mode: string; state: string; total: number; counts: Record<string, number>;
  requests_used: number; request_budget: number; providers: string[];
  results?: { id: number; item_id: number; provider: string; state: string; available_at: string; result: Result | null }[];
  next_after?: number | null;
}
interface Overview {
  observed: number; resolved_names: number; missing_names: number; name_percent: number | null;
  primary_names: number; supplemental_names: number; primary_pending: number; primary_missing_responses: number;
  icons_available: number; icons_missing: number; last_enrichment: string | null; pending_queue: number; active_jobs: number;
  provider_name_overlap: number; conflicting_names: number; provider_records: { provider: string; checked: number; names_available: number }[];
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
    <div className="metadata-provider-grid">{data.data?.providers.map(provider => <section className="panel padded metadata-provider" key={provider.provider} aria-label={`${provider.name} connection`}>
      <div className="title-row"><h3>{provider.name}</h3><span className="tag">{provider.configured ? "Connected" : provider.key_required ? "Not configured" : "Keyless access"}</span></div>
      <p className="small muted">{provider.note}</p>
      <dl className="metadata-facts"><div><dt>Credential</dt><dd>{metadataStatus(provider.credential_status)}{provider.validation_pending ? " · validation queued" : ""}</dd></div>
        <div><dt>Last validation</dt><dd>{when(provider.last_validated_at)}</dd></div><div><dt>Expiration</dt><dd>{when(provider.expires_at)}</dd></div>
        <div><dt>Recent error</dt><dd>{metadataStatus(provider.validation_error || provider.recent_error)}</dd></div>
        <div><dt>Cooldown until</dt><dd>{when(provider.cooldown_until)}</dd></div><div><dt>Requests this hour / day</dt><dd>{provider.hour_used} / {provider.day_used}</dd></div></dl>
      {provider.expiration_warning && <p className="notice" role="status">{metadataStatus(provider.expiration_warning)}. Replace this key before it expires.</p>}
      <form className="metadata-config" key={`${provider.provider}-${provider.enabled}-${provider.automatic}-${provider.hourly_budget}-${provider.daily_budget}`} onSubmit={event => {
        event.preventDefault(); const form = new FormData(event.currentTarget);
        action(() => api(`/admin/metadata-providers/${provider.provider}`, "PATCH", { enabled: form.has("enabled"), automatic: form.has("automatic"), hourly_budget: Number(form.get("hourly")), daily_budget: Number(form.get("daily")) }), `${provider.name} settings saved.`);
      }}>
        <label className="check"><input name="enabled" type="checkbox" defaultChecked={provider.enabled} disabled={busy || readOnly} />Enabled</label>
        <label className="check"><input name="automatic" type="checkbox" defaultChecked={provider.automatic} disabled={busy || readOnly} />Automatic recovery</label>
        <div className="metadata-form-row"><label>Hourly budget<input name="hourly" type="number" min="1" max="240" defaultValue={provider.hourly_budget} required /></label><label>Daily budget<input name="daily" type="number" min="1" max="2000" defaultValue={provider.daily_budget} required /></label></div>
        <button disabled={busy || readOnly}>Save settings</button>
      </form>
      {["everloot", "foreverdb"].includes(provider.provider) && <div className="metadata-actions"><button disabled={busy || readOnly} onClick={() => action(() => api(`/admin/metadata-providers/${provider.provider}/test`, "POST"), "Connection test queued. Provider limits still apply.")}>Test Connection</button>
        <button disabled={busy || readOnly || !data.data?.credential_storage_ready} onClick={() => { setEditing(editing === provider.provider ? null : provider.provider); setError(""); }}>{provider.configured ? "Replace API Key" : "Add API Key"}</button></div>}
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
  const jobs = useQuery({ queryKey: ["private", "metadata-jobs"], queryFn: ({ signal }) => api<{ jobs: Job[] }>("/admin/item-metadata/jobs", "GET", undefined, signal), refetchInterval: 3000 });
  const detail = useQuery({ queryKey: ["private", "metadata-job", jobId, resultAfter], enabled: !!jobId, queryFn: ({ signal }) => api<Job>(`/admin/item-metadata/jobs/${jobId}?after=${resultAfter}`, "GET", undefined, signal), refetchInterval: 3000 });
  const body = { market_id: market, mode, providers: selected, limit: input.limit, request_budget: input.request_budget, item_id: mode === "single" ? Number(input.item_id) || null : null };
  function resetPreview() { setPreview(null); setMessage(""); }
  async function action(work: () => Promise<void>) { setBusy(true); setError(""); try { await work(); await jobs.refetch(); await stats.refetch(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); } }
  const state = stats.data;
  return <section aria-labelledby="metadata-heading" className="metadata-admin">
    <div className="title-row"><div><div className="eyebrow">LOCAL ITEM CATALOG</div><h2 id="metadata-heading">Item Metadata</h2></div><MarketSelect markets={markets} market={market} setMarket={value => { setMarket(value); resetPreview(); }} /></div>
    <p className="muted">Recover observed item names and base attributes. Unavailable provider metadata never means an auction item does not exist.</p>
    <ErrorNotice error={error || stats.error?.message || jobs.error?.message || detail.error?.message || providers.error?.message || ""} />
    {message && <p className="notice success" role="status">{message}</p>}
    {stats.isPending && <p role="status">Loading catalog measurements…</p>}
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
    <section className="panel padded"><h3>Recovery jobs</h3>{!jobs.data?.jobs.length && <p className="muted">No recovery jobs yet.</p>}
      <div className="metadata-job-list">{jobs.data?.jobs.map(job => <div key={job.id} className="metadata-job-row"><button className="text-button" onClick={() => { setJobId(job.id); setResultAfter(0); }}>Job #{job.id} · {job.mode}</button>
        <span>{job.state} · {Object.entries(job.counts).map(([key, value]) => `${value} ${key}`).join(", ")} / {job.total}</span><span className="small muted">{job.requests_used}/{job.request_budget} requests</span>
        <div className="metadata-actions">{["queued", "running"].includes(job.state) && <button disabled={busy || readOnly} onClick={() => action(async () => { await api(`/admin/item-metadata/jobs/${job.id}/pause`, "POST"); })}>Pause</button>}{job.state === "paused" && <button disabled={busy || readOnly} onClick={() => action(async () => { await api(`/admin/item-metadata/jobs/${job.id}/resume`, "POST"); })}>Resume</button>}{["queued", "running", "paused"].includes(job.state) && <button disabled={busy || readOnly} onClick={() => action(async () => { await api(`/admin/item-metadata/jobs/${job.id}/cancel`, "POST"); })}>Cancel</button>}</div>
      </div>)}</div>
      {detail.data && <div className="metadata-job-detail"><h4>Job #{detail.data.id} results</h4><progress aria-label="Recovery progress" max={Math.max(1, detail.data.total)} value={["completed", "failed", "skipped", "cancelled"].reduce((n, key) => n + (detail.data!.counts[key] || 0), 0)} />
        {detail.data.results?.map(result => <div className="metadata-result" key={result.id}><strong>Item #{result.item_id} · {result.provider}</strong><span>{metadataStatus(result.result?.status || result.state)}</span><span className="small muted">{result.result?.recovered_fields?.join(", ") || "No recovered fields"}{result.state === "queued" ? ` · eligible ${when(result.available_at)}` : ""}</span>{result.result?.source && <span className="small muted">{result.result.source.build} · {metadataStatus(result.result.source.confidence)} {result.result.source.attribution && <a href={result.result.source.attribution.url} target="_blank" rel="noopener noreferrer">{result.result.source.attribution.text}</a>}</span>}</div>)}
        <div className="metadata-actions">{resultAfter > 0 && <button onClick={() => setResultAfter(0)}>First results</button>}{detail.data.next_after && <button onClick={() => setResultAfter(detail.data!.next_after!)}>Next results</button>}</div></div>}
    </section>
    <section className="panel padded"><h3>Provider health</h3>{providers.data?.providers.map(provider => <p key={provider.provider}><strong>{provider.name}</strong> · {provider.enabled ? "enabled" : "disabled"} · {metadataStatus(provider.recent_error)}{provider.cooldown_until ? ` · cooldown ${when(provider.cooldown_until)}` : ""}</p>)}</section>
    <section className="panel padded"><h3>Recent provider results</h3>{!state?.recent_results.length && <p className="muted">No completed provider attempts yet.</p>}{state?.recent_results.map((r, i) => <p key={i}>Item #{r.item_id} · {r.provider} · {metadataStatus(r.result.status)} · {when(r.at)}</p>)}</section>
  </section>;
}
