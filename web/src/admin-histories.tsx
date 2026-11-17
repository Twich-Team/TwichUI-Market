import { useState } from "react";
import { DataTable } from "./data-table";
import { LocalTime, Status, useRecordPage } from "./admin-table";
import { Market } from "./types";
interface SecurityRecord { id:number; actor_id:number|null; account:string|null; action:string; at:string; detail:string }
export function SecurityHistory() {
  const [search,setSearch]=useState(""),[category,setCategory]=useState("");
  const page=useRecordPage<SecurityRecord>("security",{q:search,category},"created_at");
  return <section className="panel padded"><h3>Security events</h3><p className="small muted">Server-filtered audit history. Reference details remain redacted.</p>
    <div className="toolbar"><label>Search account or event<input type="search" value={search} maxLength={64} onChange={e=>{setSearch(e.target.value);page.reset();}}/></label><label>Event category<select value={category} onChange={e=>{setCategory(e.target.value);page.reset();}}><option value="">All categories</option>{["auth","user","device","companion","metadata","retention","market","invitation"].map(value=><option key={value} value={value}>{value}</option>)}</select></label></div>
    <DataTable<SecurityRecord> label="security events" data={page.query.data?.rows||[]} server={page.server} loading={page.query.isFetching} error={page.query.error?.message} getRowId={row=>String(row.id)} columns={[
      {id:"created_at",accessorKey:"at",header:"Timestamp",enableHiding:false,cell:({row})=><LocalTime value={row.original.at}/>},
      {accessorKey:"action",header:"Event category",cell:({row})=>row.original.action.replaceAll("."," ").replaceAll("_"," ")},
      {accessorKey:"actor_id",header:"Account",cell:({row})=>row.original.account||"System / unauthenticated"},
      {id:"outcome",header:"Outcome",enableSorting:false,cell:({row})=><Status tone={/fail|reject|denied/.test(row.original.action)?"error":"neutral"}>{/fail|reject|denied/.test(row.original.action)?"Rejected":/success|completed|validated/.test(row.original.action)?"Completed":"Recorded"}</Status>},
    ]} renderDetails={row=><dl className="record-details"><dt>Audit reference</dt><dd>#{row.id}</dd><dt>Device / source reference</dt><dd>{row.detail||"Not recorded"}</dd><dt>Full timestamp</dt><dd><LocalTime value={row.at}/></dd></dl>}/>
  </section>;
}
interface Run { id:number; market_id:number; checked_at:string; status:string; http_status:number|null; duration_seconds:number; payload_bytes:number; error:string|null }
export function CollectionHistory({markets}:{markets:Market[]}) {
  const [market,setMarket]=useState(""),[status,setStatus]=useState("");
  const page=useRecordPage<Run>("collection",{...(market?{market_id:market}:{}),status},"checked_at");
  return <section className="panel padded"><h3>Collection checks</h3><div className="toolbar"><label>Collection market<select value={market} onChange={e=>{setMarket(e.target.value);page.reset();}}><option value="">All markets</option>{markets.map(row=><option key={row.id} value={row.id}>{row.label}</option>)}</select></label><label>Collection outcome<select value={status} onChange={e=>{setStatus(e.target.value);page.reset();}}><option value="">All outcomes</option><option value="failures">Failures only</option><option value="collected">Collected new snapshot</option><option value="unchanged">Unchanged</option></select></label></div>
    <DataTable<Run> label="collection checks" data={page.query.data?.rows||[]} server={page.server} loading={page.query.isFetching} error={page.query.error?.message} getRowId={row=>String(row.id)} columns={[
      {accessorKey:"market_id",header:"Market",enableHiding:false,cell:({row})=>markets.find(m=>m.id===row.original.market_id)?.label||`#${row.original.market_id}`},
      {accessorKey:"checked_at",header:"Checked",cell:({row})=><LocalTime value={row.original.checked_at}/>},
      {accessorKey:"status",header:"Result",cell:({row})=><Status tone={row.original.error||row.original.status==="failed"?"error":"neutral"}>{row.original.status.replaceAll("_"," ")}</Status>},
      {accessorKey:"http_status",header:"HTTP"},
      {accessorKey:"duration_seconds",header:"Duration",meta:{numeric:true},cell:({row})=>`${row.original.duration_seconds.toLocaleString()} s`},
      {accessorKey:"payload_bytes",header:"Payload",meta:{numeric:true},cell:({row})=>`${(row.original.payload_bytes/1024).toLocaleString(undefined,{maximumFractionDigits:1})} KiB`},
    ]} renderDetails={row=><p>Run #{row.id} · {row.error||"No failure recorded"}</p>}/>
  </section>;
}
