import { useState } from "react";
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

export function SourceAge({ market }: { market: Market }) {
  const time = market.last_modified && Date.parse(market.last_modified);
  if (!time || time > Date.now() + 300_000) return <>No reliable source timestamp</>;
  const minutes = Math.floor(Math.max(0, Date.now()-time) / 60_000);
  return <><LocalTime value={market.last_modified}/> · {minutes<1?"less than 1 minute ago":minutes<60?`${minutes} min ago`:minutes<1440?`${Math.floor(minutes/60)} hr ago`:`${Math.floor(minutes/1440)} days ago`}</>;
}

export function CollectionHistory({markets}:{markets:Market[]}) {
  const [market,setMarket]=useState(""),[status,setStatus]=useState("");
  const page=useRecordPage<Run>("collection",{...(market?{market_id:market}:{}),status},"checked_at");
  const health = markets.filter(row=>!market || row.id===Number(market));
  return <>
    <section className="panel padded" aria-label="Collection health">
      <div className="panel-heading"><h2>Collection health</h2><label>Collection market<select value={market} onChange={e=>{setMarket(e.target.value);page.reset();}}>
        <option value="">All configured markets</option>{markets.map(row=><option key={row.id} value={row.id}>{row.label}</option>)}
      </select></label></div>
      {health.length===0 && <p>No markets are configured. Add a market in Markets &amp; schedules.</p>}
      {health.map(row=><article key={row.id} className="admin-status-details">
        <h3>{row.label}</h3>
        <Status tone={!row.enabled?"neutral":row.failures||row.last_error?"error":row.freshness==="current"?"success":"warning"}>{
          !row.enabled ? "Collection disabled" : row.failures || row.last_error ? "Last check failed" : row.freshness==="current" ? "Collecting" : "Price freshness needs review"
        }</Status>
        <dl className="provider-summary">
          <div><dt>Source updated</dt><dd><SourceAge market={row}/></dd></div>
          <div><dt>Last checked successfully</dt><dd><LocalTime value={row.last_success}/></dd></div>
          <div><dt>Consecutive failures</dt><dd>{row.failures}</dd></div>
        </dl>
        {row.last_error && <p>{row.last_error} · Review recent failed runs below.</p>}
        {!row.last_error && row.enabled && row.freshness!=="current" && <p>Check the source update above and compare the latest runs below.</p>}
      </article>)}
      <p>Last new snapshot {page.query.isPlaceholderData||page.query.isPending?"· Checking…":page.query.error?"· Unavailable":<LocalTime value={page.query.data?.latest_snapshot_at}/>} · {market?"Selected market":"All markets"}</p>
      {page.query.dataUpdatedAt > 0 && <p className="muted">View refreshed <LocalTime value={new Date(page.query.dataUpdatedAt).toISOString()}/></p>}
    </section>
    <section className="panel padded"><h3>Collection checks</h3>
      <div className="admin-log-filters"><label>Collection outcome<select value={status} onChange={e=>{setStatus(e.target.value);page.reset();}}>
        <option value="">All outcomes</option><option value="failures">Failures only</option><option value="collected">Collected response</option><option value="unchanged">Unchanged</option>
      </select></label></div>
      <DataTable<Run> label="collection checks" data={page.query.data?.rows||[]} server={page.server} loading={page.query.isFetching} error={page.query.error?.message} getRowId={row=>String(row.id)} emptyMessage="No collection checks match these filters." columns={[
        {accessorKey:"market_id",header:"Market",enableHiding:false,cell:({row})=>markets.find(m=>m.id===row.original.market_id)?.label||`#${row.original.market_id}`},
        {accessorKey:"checked_at",header:"Checked",cell:({row})=><LocalTime value={row.original.checked_at}/>},
        {accessorKey:"status",header:"Result",cell:({row:{original:row}})=><Status tone={row.error||row.status==="failed"?"error":row.status==="collected"?"success":"neutral"}>{
          row.status==="collected"?"Response collected":row.status==="unchanged"?"Checked · prices unchanged":row.status.replaceAll("_"," ")
        }</Status>},
        {accessorKey:"http_status",header:"HTTP",cell:({row})=>row.original.http_status??"No response recorded"},
        {accessorKey:"duration_seconds",header:"Duration",meta:{numeric:true},cell:({row})=>row.original.duration_seconds==null?"Not measured":`${row.original.duration_seconds.toLocaleString()} s`},
        {accessorKey:"payload_bytes",header:"Payload",meta:{numeric:true},cell:({row})=>row.original.payload_bytes==null?"Not measured":`${(row.original.payload_bytes/1024).toLocaleString(undefined,{maximumFractionDigits:1})} KiB`},
      ]} renderDetails={row=><p>Run #{row.id} · {row.error||"No failure recorded"}</p>}/>
    </section>
  </>;
}
