import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { formatBytes } from "./size";
import { CollectionActivity, type ActivitySummary } from "./collection-activity";
import "./collection.css";
import { DataTable } from "./data-table";
import { LocalTime, Status, useRecordPage } from "./admin-table";
import type { Market } from "./types";

interface SecurityRecord { id:number; actor_id:number|null; account:string|null; action:string; at:string; detail:string }

const securityOutcome = (action: string) => {
  if (/\.(failed|rejected|denied|refused)$/.test(action)) return "Rejected";
  if (/\.(succeeded|completed|validated|approved)$/.test(action)) return "Completed";
  return "Recorded";
};
function eventActor(record: SecurityRecord) {
  if (record.account) return record.account;
  if (record.actor_id) return `Account #${record.actor_id}`;
  if (record.action === "login.failed") return "Unauthenticated sign-in";
  if (/^metadata\.credential\.(used|validated|rejected)$/.test(record.action)) return "Automated service";
  return "Actor unrecorded";
}

export function SecurityHistory() {
  const [search,setSearch]=useState(""),[category,setCategory]=useState(""),[range,setRange]=useState(""),[outcome,setOutcome]=useState("");
  const since = range ? new Date(Date.now() - Number(range) * 86_400_000).toISOString().slice(0,10)+"T00:00:00Z" : "";
  const page=useRecordPage<SecurityRecord>("security",{q:search,category,outcome,...(since?{since}:{})},"created_at");
  function change(set:(value:string)=>void,value:string) { set(value);page.reset(); }
  return <section className="panel padded" aria-label="Security event history">
    <div className="admin-view-switch">
      <button aria-pressed={!category} onClick={()=>change(setCategory,"")}>All events</button>
      <button aria-pressed={category==="login"} onClick={()=>change(setCategory,"login")}>Sign-ins</button>
      <button aria-pressed={category==="access"} onClick={()=>change(setCategory,"access")}>Access changes</button>
    </div>
    <div className="admin-log-filters">
      <label>Search account or event<input type="search" value={search} maxLength={64} onChange={e=>change(setSearch,e.target.value)}/></label>
      <label>Event category<select value={category} onChange={e=>change(setCategory,e.target.value)}>
        <option value="">All categories</option><option value="login">Sign-ins</option><option value="access">Access changes</option>
        {["user","device","companion","metadata","retention","market","invitation","backup"].map(value=><option key={value} value={value}>{value[0].toUpperCase()+value.slice(1)}</option>)}
      </select></label>
      <label>Time period (UTC)<select value={range} onChange={e=>change(setRange,e.target.value)}>
        <option value="">All recorded time</option><option value="0">Today</option><option value="6">Last 7 days</option><option value="29">Last 30 days</option>
      </select></label>
      <label>Outcome<select value={outcome} onChange={e=>change(setOutcome,e.target.value)}>
        <option value="">All outcomes</option><option value="completed">Completed</option><option value="rejected">Rejected</option><option value="recorded">Other recorded events</option>
      </select></label>
    </div>
    <DataTable<SecurityRecord> label="security events" data={page.query.data?.rows||[]} server={page.server} loading={page.query.isFetching} error={page.query.error?.message} getRowId={row=>String(row.id)} emptyMessage="No security events match these filters." columns={[
      {id:"created_at",accessorKey:"at",header:"Timestamp",enableHiding:false,cell:({row})=><LocalTime value={row.original.at}/>},
      {accessorKey:"action",header:"Event",cell:({row})=>row.original.action.replaceAll("."," ").replaceAll("_"," ")},
      {accessorKey:"actor_id",header:"Actor",cell:({row})=>eventActor(row.original)},
      {id:"outcome",header:"Outcome",enableSorting:false,cell:({row})=><Status tone={securityOutcome(row.original.action)==="Rejected"?"error":"neutral"}>{securityOutcome(row.original.action)}</Status>},
    ]} renderDetails={row=><dl className="record-details"><dt>Audit reference</dt><dd>#{row.id}</dd><dt>Event details</dt><dd>{row.detail||"Not recorded"}</dd><dt>Full timestamp</dt><dd><LocalTime value={row.at}/></dd></dl>}/>
  </section>;
}

interface Run { id:number; market_id:number; checked_at:string; status:string; http_status:number|null; duration_seconds:number|null; payload_bytes:number|null; error:string|null }

function age(value: string | null | undefined) {
  const time = Date.parse(value ?? "");
  if (!Number.isFinite(time) || time > Date.now() + 300_000) return "Not recorded";
  const minutes = Math.floor(Math.max(0,Date.now()-time) / 60_000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 1440) return `${Math.floor(minutes/60)} hr ago`;
  return `${Math.floor(minutes/1440)} days ago`;
}

export function SourceAge({ market }: { market: Market }) {
  const elapsed = age(market.last_modified);
  if (elapsed === "Not recorded") return <>No reliable source timestamp</>;
  return <><LocalTime value={market.last_modified}/> · {elapsed === "Just now" ? "less than 1 minute ago" : elapsed}</>;
}

function marketHealth(market: Market): {label: string; tone: "neutral" | "success" | "warning" | "error"} {
  if (!market.verified) return {label:"Unverified",tone:"neutral"};
  if (!market.enabled) return {label:"Paused",tone:"neutral"};
  if (market.coverage_status === "partial") return {label:"Partial coverage",tone:"error"};
  if (market.failures || market.last_error) return {label:"Check failed",tone:"error"};
  if (!market.last_success) return {label:"Waiting for first check",tone:"warning"};
  if (Date.now() - Date.parse(market.last_success) > Math.max(600, market.interval_seconds * 2) * 1000)
    return {label:"Checks delayed",tone:"warning"};
  if (market.freshness === "unknown") return {label:"Source time unavailable",tone:"warning"};
  if (market.freshness === "stale") return {label:"Prices may be stale",tone:"warning"};
  return {label:"Collecting",tone:"success"};
}

function MetricTime({ value }: {value:string}) {
  const date = new Date(value);
  if (date.toDateString() !== new Date().toDateString()) return <LocalTime value={value}/>;
  return <time dateTime={value} title={date.toLocaleString(undefined,{dateStyle:"full",timeStyle:"long"})}>
    {date.toLocaleTimeString(undefined,{timeStyle:"short"})}
  </time>;
}

function HealthCard({ title, value, tone, children }: {
  title:string; value:ReactNode; tone?:"warning"|"success"|"neutral"; children:ReactNode;
}) {
  return <article className="collection-health-card" data-tone={tone}>
    <h3>{title}</h3><strong>{value}</strong><p>{children}</p>
  </article>;
}

export function CollectionHistory({markets}:{markets:Market[]}) {
  const [market,setMarket] = useState("");
  const [status,setStatus] = useState("");
  const [period,setPeriod] = useState(14);
  const params = new URLSearchParams({days:String(period),...(market?{market_id:market}:{})});
  const activity = useQuery({
    queryKey:["private","collection-activity",market,period],
    queryFn:({signal})=>api<ActivitySummary>(`/admin/records/collection-activity?${params}`,"GET",undefined,signal),
    refetchInterval:30_000,
  });
  const page = useRecordPage<Run>("collection",{...(market?{market_id:market}:{}),status},"checked_at");
  const scoped = market ? markets.filter(row=>row.id===Number(market)) : markets;
  const active = scoped.filter(row=>row.enabled&&row.verified);
  const showing = active.length ? active : scoped;
  const successful = showing.map(row=>row.last_success).filter((value):value is string=>Boolean(value))
    .sort((a,b)=>Date.parse(b)-Date.parse(a))[0];
  const withSource = showing.filter(row=>age(row.last_modified)!=="Not recorded")
    .sort((a,b)=>Date.parse(a.last_modified!)-Date.parse(b.last_modified!));
  const source = withSource.length === showing.length ? withSource[0] : undefined;
  const statuses = scoped.map(market=>({market,...marketHealth(market)}));
  const attention = statuses.filter(({tone})=>tone==="error"||tone==="warning");
  const snapshot = activity.data?.latest_snapshot_at;
  const hasFailures = attention.some(({market,tone})=>tone==="error" && (market.failures || market.last_error));
  function reviewChecks() {
    if (hasFailures) {
      setStatus("failures");
      page.reset();
    }
    document.getElementById(hasFailures?"collection-check-heading":"collection-activity-heading")?.focus();
  }
  return <div className="collection-page">
    <section aria-label="Collection health">
      <label className="collection-scope">Market
        <select aria-label="Collection market" value={market} onChange={event=>{setMarket(event.target.value);page.reset();}}>
          <option value="">All configured markets</option>{markets.map(row=><option key={row.id} value={row.id}>{row.label}</option>)}
        </select>
      </label>
      <div className="collection-health-cards">
        <HealthCard title="Current status" value={attention.length ? "Needs attention" : active.length ? "Collecting" : "No active collection"}
          tone={attention.length ? "warning" : active.length ? "success" : "neutral"}>
          {active.length.toLocaleString()} of {scoped.length.toLocaleString()} {scoped.length===1?"market scheduled":"markets scheduled"}
        </HealthCard>
        <HealthCard title={showing.length>1 ? "Oldest source update" : "Source updated"} value={age(source?.last_modified)}>
          {source?.last_modified ? <><MetricTime value={source.last_modified}/>{active.length && scoped.length>active.length ? " · active only" : ""}</> : "A source timestamp is missing"}
        </HealthCard>
        <HealthCard title="Last successful check" value={age(successful)}>
          {successful ? <><MetricTime value={successful}/>{active.length && scoped.length>active.length ? " · active only" : ""}</> : "No successful check in scope"}
        </HealthCard>
        <HealthCard title="Last new snapshot" value={activity.data ? age(snapshot) : activity.isPending ? "Loading…" : "Unavailable"}>
          {snapshot ? <MetricTime value={snapshot}/> : activity.data ? "No saved snapshot in scope" :
            activity.isError ? "Retry history below" : "Checking retained records"}
        </HealthCard>
      </div>
      {!!attention.length && <section className="collection-attention" aria-label="Collection needs attention">
        <div>
          <div className="collection-alert-summary"><Status tone={attention[0].tone}>{attention[0].label}</Status>
            <strong>{attention[0].market.label}</strong>{attention.length > 1 && <span>+{attention.length-1} more</span>}
          </div>
          {attention[0].market.last_error && <p>{attention[0].market.last_error}</p>}
        </div>
        <button onClick={reviewChecks}>{hasFailures ? "Review failed checks" : "Review collection activity"}</button>
      </section>}
      {!active.length && <div className="collection-paused">
        <span>{markets.length ? "Collection requires an enabled, verified market." : "No markets are configured."}</span>
        <a href="/administration?admin_tab=markets">Markets &amp; schedules</a>
      </div>}
    </section>

    <CollectionActivity
      key={market}
      days={activity.data?.days} period={period} onPeriod={setPeriod}
      loading={activity.isFetching} failed={activity.isError} retry={()=>{void activity.refetch();}}
    />

    {!!scoped.length && <details className="panel collection-market-details">
      <summary>Market status details</summary>
      {statuses.map(({market,label,tone})=><article key={market.id}>
        <div><h3>{market.label}</h3><Status tone={tone}>{label}</Status></div>
        <dl>
          <div><dt>Source updated</dt><dd><SourceAge market={market}/></dd></div>
          <div><dt>Last successful check</dt><dd><LocalTime value={market.last_success}/></dd></div>
          <div><dt>Consecutive failures</dt><dd>{market.failures}</dd></div>
        </dl>
        {market.last_error && <p>{market.last_error}</p>}
      </article>)}
    </details>}

    <section className="panel padded collection-check-log">
      <div className="collection-section-header">
        <div><h2 id="collection-check-heading" tabIndex={-1}>Collection checks</h2>
          {!!page.query.dataUpdatedAt && !page.query.isPlaceholderData && <p>All retained dates · View refreshed <LocalTime value={new Date(page.query.dataUpdatedAt).toISOString()}/></p>}
        </div>
        <label>Collection outcome<select value={status} onChange={event=>{setStatus(event.target.value);page.reset();}}>
          <option value="">All outcomes</option><option value="failures">Failures only</option><option value="collected">Collected response</option><option value="unchanged">Unchanged</option><option value="partial">Partial</option>
        </select></label>
      </div>
      <DataTable<Run> label="collection checks" data={page.query.isPlaceholderData ? [] : page.query.data?.rows ?? []}
        server={{...page.server,rowCount:page.query.isPlaceholderData?0:page.server.rowCount}} loading={page.query.isFetching}
        error={page.query.error && <>Collection checks could not be loaded. <button onClick={()=>page.query.refetch()}>Retry checks</button></>}
        getRowId={row=>String(row.id)} emptyMessage="No collection checks match these filters." columns={[
        {accessorKey:"market_id",header:"Market",enableHiding:false,cell:({row})=>markets.find(m=>m.id===row.original.market_id)?.label||`#${row.original.market_id}`},
        {accessorKey:"checked_at",header:"Checked",cell:({row})=><LocalTime value={row.original.checked_at}/>},
        {accessorKey:"status",header:"Result",cell:({row:{original:row}})=><Status tone={row.status==="partial"?"warning":row.error||row.status==="failed"?"error":row.status==="collected"?"success":"neutral"}>{
          row.status==="partial"?"Partial coverage":row.error||row.status==="failed"?"Failed":row.status==="collected"?"Response collected":row.status==="unchanged"?"Checked · prices unchanged":row.status.replaceAll("_"," ")
        }</Status>},
        {accessorKey:"http_status",header:"HTTP",cell:({row})=>row.original.http_status??"No response recorded"},
        {accessorKey:"duration_seconds",header:"Duration",meta:{numeric:true},cell:({row})=>row.original.duration_seconds==null?"Not measured":`${row.original.duration_seconds.toLocaleString()} s`},
        {accessorKey:"payload_bytes",header:"Payload",meta:{numeric:true},cell:({row})=>row.original.payload_bytes==null?"Not measured":formatBytes(row.original.payload_bytes)},
      ]} renderDetails={row=><p>Run #{row.id} · {row.error||"No failure recorded"}</p>}/>
    </section>
  </div>;
}
