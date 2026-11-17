import { ItemName } from "./item-name";
import { useState } from "react";
import { api } from "./api";
import { DataTable } from "./data-table";
import { LocalTime, ProviderEmblem, providerNames, Status, useRecordPage } from "./admin-table";
export interface Attempt {
  id: number; job_id: number; item_id: number; item_name: string | null; quality?:string|null; region: string; provider: string; state: string;
  record_scope?: "item"|"catalog"; at: string; attempts: number; http_status: number | null; outcome: string; fields_returned: string[]; fields_recovered: string[]; fields_updated?:string[];
  error_category: string | null; source: { edition: string; build: string | null; confidence: string | null };
  delta_recorded?: boolean;
  next_retry: string | null; retry_allowed: boolean; retry_reason: string | null;
}
export const outcomeLabels: Record<string, string> = {
  attributes_returned:"Attributes returned only", observations_returned:"Observations returned · no names imported", name_returned:"Name returned · not imported",
  metadata_updated:"Verified known fields updated", name_recovered: "Recovered name", attributes_recovered: "Recovered attributes only", already_known: "Data already known",
  metadata_returned: "Data returned · historical gain unrecorded", no_usable_data: "No usable metadata returned", missing: "Item not found by provider",
  wrong_identity: "Wrong edition or item", invalid_response: "Invalid response", credentials_invalid: "Credentials invalid",
  access_blocked: "Access denied", rate_limited: "Rate limited", unavailable: "Temporarily unavailable", pending: "Pending", skipped: "Skipped",
};
export function AttemptStatus({ attempt }: { attempt: Attempt }) {
  const tone = ["name_recovered","metadata_updated"].includes(attempt.outcome) ? "success" : ["attributes_recovered", "already_known", "metadata_returned", "attributes_returned", "name_returned", "observations_returned"].includes(attempt.outcome) ? "warning" : ["pending", "skipped"].includes(attempt.outcome) ? "neutral" : "error";
  const fields = attempt.fields_recovered.map(field => field.replaceAll("_", " "));
  const label = attempt.outcome === "name_recovered" && fields.length ? `Recovered ${fields.join(" and ")}` : outcomeLabels[attempt.outcome] || "Outcome unavailable";
  return <Status tone={tone}>{label}</Status>;
}
function recentLocalStart(){const date=new Date(Date.now()-7*86400000);return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);}
export function MetadataAttempts({ market, readOnly }: { market: number; readOnly: boolean }) {
  const [provider, setProvider] = useState(""), [outcome, setOutcome] = useState(""), [item, setItem] = useState(""), [since, setSince] = useState(recentLocalStart), [until, setUntil] = useState("");
  const [scope,setScope]=useState("all");
  const [message, setMessage] = useState(""), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const filters: Record<string, string> = {};
  if(scope==="current")filters.market_id=String(market);
  if (provider) filters.provider = provider;
  if (outcome) filters.outcome = outcome;
  if (item) filters.q = item;
  if (since) filters.since = new Date(since).toISOString();
  if (until) filters.until = new Date(until).toISOString();
  const page = useRecordPage<Attempt>("metadata-attempts", filters, "at");
  function change(set: (value: string) => void, value: string) { set(value); page.reset(); }
  async function retry(row: Attempt) {
    setBusy(true); setError("");
    try { const job = await api<{job_id:number}>(`/admin/records/metadata-attempts/${row.id}/retry`, "POST"); setMessage(`Recovery job #${job.job_id} queued. Provider limits still apply.`); await page.query.refetch(); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <section className="panel padded"><h3>Recent provider results</h3>
    <p className="small muted">A successful request may return no usable name. Times use your local timezone ({Intl.DateTimeFormat().resolvedOptions().timeZone}).</p>
    {message && <p role="status">{message}</p>}{error && <p role="alert" className="notice error">{error}</p>}
    <div className="toolbar record-filters">
      <label>Attempt scope<select value={scope} onChange={e=>change(setScope,e.target.value)}><option value="all">All markets</option><option value="current">Selected market</option></select></label>
      <label>Provider<select value={provider} onChange={e => change(setProvider, e.target.value)}><option value="">All providers</option>{Object.entries(providerNames).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
      <label>Outcome<select value={outcome} onChange={e => change(setOutcome, e.target.value)}><option value="">All outcomes</option>{Object.entries(outcomeLabels).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      <label>Item name or ID<input type="search" value={item} maxLength={64} onChange={e=>change(setItem,e.target.value)} /></label>
      <label>From (local time)<input type="datetime-local" value={since} onChange={e => change(setSince,e.target.value)} /></label>
      <label>Until (local time)<input type="datetime-local" value={until} onChange={e => change(setUntil,e.target.value)} /></label>
    </div>
    <p className="small muted">Showing all markets by default; clear From to include older attempts. Historical field changes may be unrecorded.</p>
    {page.query.data?.summary && <div className="attempt-summary" role="status">{[["Names recovered","name_recovered"],["Attributes recovered","attributes_recovered"],["Already known","already_known"],["Access blocked","access_blocked"]].map(([label,key]) => <span key={key}><strong>{(page.query.data!.summary![key] || 0).toLocaleString()}</strong> {label}</span>)}<span><strong>{["no_usable_data","missing","wrong_identity","invalid_response","credentials_invalid","access_blocked","rate_limited","unavailable"].reduce((n,key)=>n+(page.query.data!.summary![key]||0),0).toLocaleString()}</strong> Failed</span></div>}
    <DataTable<Attempt> label="provider attempts" data={page.query.data?.rows || []} server={page.server} loading={page.query.isFetching} error={page.query.error?.message} getRowId={row => String(row.id)}
      columns={[
        {accessorKey:"provider",header:"Provider",cell:({row})=><ProviderEmblem provider={row.original.provider}/>},
        {accessorKey:"item_id",header:"Item",enableHiding:false,cell:({row})=><><strong><ItemName name={row.original.record_scope==="catalog" ? "Catalog page" : row.original.item_name || `Item #${row.original.item_id}`} quality={row.original.item_name ? row.original.quality : null}/></strong>{row.original.record_scope!=="catalog" && row.original.item_name && <div className="small muted">#{row.original.item_id}</div>}</>},
        {accessorKey:"outcome",header:"What happened",cell:({row})=><AttemptStatus attempt={row.original}/>},
        {id:"fields",header:"Recovered fields",enableSorting:false,cell:({row})=>row.original.fields_recovered.map(field=>field.replaceAll("_"," ")).join(", ") || (row.original.delta_recorded===false ? "Historical changes unrecorded" : "None recorded")},
        {accessorKey:"at",header:"Last attempt",cell:({row})=><LocalTime value={row.original.at}/>},
        {id:"retry",header:"Retry",enableSorting:false,cell:({row})=>row.original.retry_allowed && !readOnly ? <button disabled={busy} onClick={()=>retry(row.original)}>Retry item #{row.original.item_id}</button> : <span className="small muted">{readOnly ? "Read-only access" : row.original.retry_reason || "Unavailable"}</span>},
      ]}
      renderDetails={row=><dl className="record-details"><dt>Request</dt><dd>{row.http_status == null ? "No HTTP response recorded" : `HTTP ${row.http_status}`} · {row.attempts} attempt(s) · job #{row.job_id}</dd><dt>Returned fields</dt><dd>{row.fields_returned.join(", ") || "None"}</dd><dt>Newly recovered fields</dt><dd>{row.fields_recovered.join(", ") || "None recorded"}</dd><dt>Updated known fields</dt><dd>{row.fields_updated?.join(", ")||"None recorded"}</dd><dt>Source / build</dt><dd>{providerNames[row.provider]} · {row.source.edition} · {row.source.build || "Build not recorded"} · {row.source.confidence || "Confidence not recorded"}</dd><dt>Rejection category</dt><dd>{row.error_category?.replaceAll("_"," ") || "None recorded"}</dd><dt>Next eligible retry</dt><dd><LocalTime value={row.next_retry}/>{row.retry_reason && ` · ${row.retry_reason}`}</dd></dl>}
    />
  </section>;
}
