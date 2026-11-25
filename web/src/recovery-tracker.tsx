import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { PaginationState, SortingState } from "@tanstack/react-table";
import { api } from "./api";
import { DataTable } from "./data-table";
import { LocalTime, ProviderEmblem, Status, providerNames } from "./admin-table";
import { Loading } from "./loading";
import { DeferredChart } from "./deferred-chart";

const providers = ["blizzard", "foreverdb", "everloot", "thewowdb"];
const labels: Record<string,string> = {
  never_attempted:"Never attempted", name_recovered:"Name recovered", attributes_recovered:"Attributes recovered", icon_recovered:"Icon recovered",
  metadata_updated:"Verified fields updated", already_known:"Already known", missing:"Missing from provider", rate_limited:"Rate limited", waiting_for_refresh:"Waiting for refresh",
  recently_unproductive:"Recent check added no fields", temporarily_unavailable:"Temporarily unavailable", access_blocked:"Access blocked",
  provider_disabled:"Provider disabled", automatic_disabled:"Automatic recovery off", credential_unavailable:"Credentials unavailable",
  provider_cooldown:"Provider cooldown", no_eligible_provider:"No eligible provider", historical_incomplete:"Historical evidence incomplete",
  eligible:"Eligible", waiting:"Waiting", complete:"Applicable profile complete", reservation_unknown:"Request dispatch unknown",
};
export interface ProviderState {status:string; checked_at:string|null; next_at:string|null; waiting:string|null}
export interface RecoveryItem {
  region:string; item_id:number; name:string|null; icon:string|null; missing:string[]; providers:Record<string,ProviderState>;
  last_useful_at:string|null; next_provider:string|null; next_at:string|null; status:string; explanation:string;
}
interface TrackerPage {rows:RecoveryItem[];total:number;summary:Record<string,number>;measured_at:string;definition:string}
interface Efficiency {queued_quota_deferrals?:number;days:number;providers:{provider:string;external_requests:number;useful_requests:number;names:number;icons:number;attributes:number;already_known:number;missing_no_data:number;errors:number;rate_limits:number;unknown_reservations:number;metadata_requests?:number}[];metadata_requests:number;useful_requests:number;useful_rate:number|null;historical_task_records:number;notice:string}
interface Journey extends RecoveryItem {last_scheduler_decision?:{at:string;status:string;next_at:string|null;decision:{explanation:string}}|null;known_fields:Record<string,unknown>;provenance:Record<string,{provider?:string;build?:string;confidence?:string;retrieved_at?:string}>;attempts:{id:number;provider:string;at:string;http_status:number|null;outcome:string;kind:string;returned_fields:string[];new_fields:string[];updated_fields?:string[];decision:{explanation?:string}|null}[];next_before:number|null;historical:{provider:string;at:string;attempts:number;outcome:string;evidence:string}[]}
export function RecoveryProviderStatus({value}:{value:ProviderState}) {
  const successful=["name_recovered","attributes_recovered","icon_recovered"].includes(value.status);
  const failed=["missing","access_blocked","temporarily_unavailable"].includes(value.status);
  return <span title={`${labels[value.status]||value.status}${value.waiting?` · ${labels[value.waiting]||value.waiting}`:""}`}><Status tone={successful?"success":failed?"error":value.waiting?"warning":"neutral"}>{labels[value.status]||value.status}</Status>{value.waiting&&value.waiting!==value.status&&<small className="muted">{labels[value.waiting]||value.waiting}</small>}</span>;
}
function Identity({item,onSelect}:{item:RecoveryItem;onSelect:()=>void}) {
  return <button className="recovery-item-button" data-recovery-item={item.item_id} onClick={onSelect}>{item.icon?<img src={item.icon} alt="" width="32" height="32" loading="lazy"/>:<span aria-hidden="true" className="recovery-icon-placeholder">?</span>}<span>{item.name||`Item #${item.item_id}`}<small className="muted">#{item.item_id}</small></span></button>;
}
export function RecoveryEfficiency({days,setDays,data,error,loading}:{days:number;setDays:(value:number)=>void;data?:Efficiency;error?:string;loading:boolean}) {
  const series=[['Names','names'],['Icons','icons'],['Attributes','attributes'],['Already known','already_known'],['Missing / no data','missing_no_data'],['Errors','errors'],['Rate limited','rate_limits']] as const;
  return <section className="panel padded" aria-labelledby="recovery-efficiency-title"><div className="title-row"><h3 id="recovery-efficiency-title">Recovery Efficiency</h3><label>Measurement period<select value={days} onChange={e=>setDays(Number(e.target.value))}><option value={1}>24 hours</option><option value={7}>7 days</option><option value={30}>30 days</option></select></label></div>
    {loading&&<Loading label="Loading recovery efficiency…"/>}{error&&<p role="alert">{error}</p>}
    {data&&<><p><strong>{data.useful_rate===null?"No measured requests":`${(data.useful_rate*100).toFixed(1)}% useful recovery rate`}</strong> · {data.useful_requests} requests committed a new useful field / {data.metadata_requests} actual metadata requests.</p><p className="small muted">{data.notice}</p><p className="small">{data.queued_quota_deferrals||0} tasks currently deferred by shared quota/cooldown; queued tasks are excluded from external request counts.</p>
      {data.providers.length?<><DeferredChart label="Recovery efficiency by provider" option={{color:['#c29b67','#83aca1','#b694c3','#9a8565','#b67f6d','#be6864','#a79871'],tooltip:{trigger:'axis'},legend:{type:'scroll',top:0,left:0,right:0,pageIconColor:'#c29b67',pageTextStyle:{color:'#c1b296'},textStyle:{color:'#c1b296'}},grid:{left:45,right:15,bottom:45,top:65},xAxis:{type:'category',data:data.providers.map(p=>providerNames[p.provider]),axisLabel:{color:'#c1b296',interval:0}},yAxis:{type:'value',minInterval:1,axisLabel:{color:'#c1b296'}},series:series.map(([name,key])=>({name,type:'bar',data:data.providers.map(p=>p[key])}))}}/>
      <details><summary>Exact counts and chart alternative</summary><DataTable compact label="Recovery efficiency evidence" data={data.providers} getRowId={provider=>provider.provider} columns={[
        {accessorKey:'provider',header:'Provider',cell:({row})=>providerNames[row.original.provider]},
        {accessorKey:'external_requests',header:'All external requests',meta:{numeric:true}},
        {id:'useful',header:'Useful / metadata requests',enableSorting:false,meta:{numeric:true},cell:({row})=>`${row.original.useful_requests} / ${row.original.metadata_requests??"Unrecorded"}`},
        ...series.map(([name,key])=>({accessorKey:key,header:name,meta:{numeric:true}})),
        {accessorKey:'unknown_reservations',header:'Unknown dispatch',meta:{numeric:true}},
      ]}/></details></>:<p className="muted">No forward request evidence exists for this period.</p>}
      <p className="small muted">{data.historical_task_records} historical task records have incomplete evidence. Names, icons and attributes can overlap; the useful-rate numerator counts each request once.</p></>}
  </section>;
}
export function RecoveryJourney({market,item,onClose,readOnly}:{market:number;item:number;onClose:()=>void;readOnly:boolean}) {
  const panel=useRef<HTMLElement>(null);useEffect(()=>{panel.current?.focus();},[]);
  const [before,setBefore]=useState<number|null>(null),[message,setMessage]=useState(""),[busy,setBusy]=useState(false),[force,setForce]=useState(false),[manualProvider,setManualProvider]=useState("blizzard");
  const query=useQuery({queryKey:["private","recovery-journey",market,item,before],queryFn:({signal})=>api<Journey>(`/admin/item-metadata/tracker/${item}?market_id=${market}${before?`&before=${before}`:""}`,"GET",undefined,signal)});
  const data=query.data;
  async function recover(){if(!data || (!force&&!data.next_provider))return;setBusy(true);try{const result=await api<{job_id:number}>("/admin/item-metadata/jobs","POST",{market_id:market,mode:"single",item_id:item,providers:[force?manualProvider:data.next_provider],limit:1,request_budget:1,force_refresh:force});setMessage(`Recovery job #${result.job_id} queued. Shared quotas and negative caches still apply.`);await query.refetch();}catch(e){setMessage((e as Error).message);}finally{setBusy(false);}}
  return <section ref={panel} tabIndex={-1} onKeyDown={e=>{if(e.key==="Escape")onClose();}} className="panel padded recovery-journey" aria-label="Item recovery journey"><div className="title-row"><h3>Item recovery journey · #{item}</h3><button onClick={onClose}>Close journey</button></div>
    {query.isPending&&<Loading label="Loading item recovery journey…"/>}{query.error&&<p role="alert">{query.error.message}<button onClick={()=>query.refetch()}>Retry journey</button></p>}
    {data&&<><h4>{data.name||`Item #${item}`}</h4><p>Still needed: {data.missing.join(", ")||"No applicable gaps"}.</p><p className="notice">{data.explanation}</p><p>Next known attempt: <LocalTime value={data.next_at}/></p>
      <div className="recovery-provider-list">{providers.map(p=><div key={p}><ProviderEmblem provider={p}/>{data.providers[p]&&<RecoveryProviderStatus value={data.providers[p]}/>}<LocalTime value={data.providers[p]?.next_at}/></div>)}</div>
      <label className="check"><input type="checkbox" checked={force} onChange={e=>setForce(e.target.checked)}/>Deliberate refresh of known fields (quotas and failure caches still apply)</label><label>Manual recovery provider<select disabled={!force} value={force?manualProvider:data.next_provider||"blizzard"} onChange={e=>setManualProvider(e.target.value)}>{providers.map(p=><option key={p} value={p} disabled={["provider_disabled","access_blocked","credential_unavailable"].includes(data.providers[p]?.status)}>{providerNames[p]}</option>)}</select></label><button disabled={readOnly||busy||(!force&&!data.next_provider)||force&&["provider_disabled","access_blocked","credential_unavailable"].includes(data.providers[manualProvider]?.status)} onClick={recover}>{force?"Queue deliberate refresh":"Queue eligible recovery"}</button><p className="small muted">Disabled providers and providers without access remain unavailable. Viewing this panel makes no external requests.</p>{message&&<p role="status">{message}</p>}
      <details><summary>Known fields and provenance</summary><dl className="record-details">{Object.entries(data.known_fields).map(([field,value])=><div key={field}><dt>{field.replaceAll("_"," ")}</dt><dd><span className="recovery-field-value">{typeof value==='object'?JSON.stringify(value):String(value)}</span><small className="muted">{data.provenance[field]?.provider||"Historical source unrecorded"} · {data.provenance[field]?.build||"Build unknown"} · {data.provenance[field]?.confidence||"Confidence unrecorded"}</small></dd></div>)}</dl></details>
      <details><summary>Latest recorded scheduler decision</summary>{data.last_scheduler_decision?<><LocalTime value={data.last_scheduler_decision.at}/><p>{data.last_scheduler_decision.decision.explanation}</p></>:<p>No historical scheduler choice was recorded. The next-action explanation evaluates the current local state using the shared worker policy.</p>}</details><h4>Provider attempts</h4>{!data.attempts.length&&<p className="muted">No detailed forward request records yet.</p>}<ol className="recovery-timeline">{data.attempts.map(a=><li key={a.id}><ProviderEmblem provider={a.provider}/><strong>{labels[a.outcome]||a.outcome.replaceAll("_"," ")}</strong> · <LocalTime value={a.at}/><p>Returned: {a.returned_fields.join(", ")||"None recorded"}. Newly filled: {a.new_fields.join(", ")||"None"}. Changed values: {a.updated_fields?.join(", ")||"None"}.</p><details><summary>Request evidence</summary><p>{a.http_status===null?"No HTTP response recorded":`HTTP ${a.http_status}`} · {a.kind}</p><p>{a.decision?.explanation||"Selection evidence not recorded"}</p></details></li>)}</ol>
      {data.next_before&&<button onClick={()=>setBefore(data.next_before)}>Older attempts</button>}{before&&<button onClick={()=>setBefore(null)}>Latest attempts</button>}
      {!!data.historical.length&&<details><summary>Historical records with incomplete evidence ({data.historical.length}, bounded to 50)</summary>{data.historical.map((a,i)=><p key={i}><ProviderEmblem provider={a.provider}/> · <LocalTime value={a.at}/> · {labels[a.outcome]||a.outcome} · {a.evidence}</p>)}</details>}
    </>}
  </section>;
}
export function RecoveryTracker({market,readOnly=false}:{market:number;readOnly?:boolean}) {
  const [q,setQ]=useState(""),[missing,setMissing]=useState("all"),[provider,setProvider]=useState(""),[eligibility,setEligibility]=useState("all"),[outcome,setOutcome]=useState(""),[days,setDays]=useState(7),[item,setItem]=useState<number|null>(null);
  const [pagination,setPagination]=useState<PaginationState>({pageIndex:0,pageSize:25}),[sorting,setSorting]=useState<SortingState>([{id:"item_id",desc:false}]);
  const params=new URLSearchParams({market_id:String(market),q,missing,eligibility,outcome,offset:String(pagination.pageIndex*pagination.pageSize),limit:String(pagination.pageSize),sort:sorting[0]?.id||"item_id",desc:String(sorting[0]?.desc||false)});if(provider)params.set("provider",provider);
  const query=useQuery({queryKey:["private","recovery-tracker",params.toString()],enabled:!!market,queryFn:({signal})=>api<TrackerPage>(`/admin/item-metadata/tracker?${params}`,"GET",undefined,signal),refetchInterval:60000});
  const efficiency=useQuery({queryKey:["private","recovery-efficiency",days],queryFn:({signal})=>api<Efficiency>(`/admin/item-metadata/tracker/efficiency?days=${days}`,"GET",undefined,signal),refetchInterval:60000});
  function filter(set:(value:string)=>void,value:string){set(value);setPagination(p=>({...p,pageIndex:0}));}
  const rows=query.data?.rows||[];
  return <section className="recovery-tracker" aria-labelledby="recovery-tracker-heading"><div className="title-row"><div><h3 id="recovery-tracker-heading">Recovery Tracker</h3></div><button onClick={()=>{query.refetch();efficiency.refetch();}}>Refresh local evidence</button></div>
    {query.data&&<p className="muted">{(query.data.summary.eligible??0).toLocaleString()} ready · {(query.data.summary.waiting_cooldowns??0).toLocaleString()} waiting for a provider · {(query.data.summary.no_eligible??0).toLocaleString()} without an eligible provider</p>}
    <div className="admin-log-filters"><label>Search recovery items<input type="search" maxLength={64} value={q} onChange={e=>filter(setQ,e.target.value)}/></label><label>Missing metadata<select value={missing} onChange={e=>filter(setMissing,e.target.value)}><option value="all">All items</option><option value="name">Names</option><option value="icon">Icons</option><option value="attributes">Essential attributes</option></select></label><label>Recovery provider<select value={provider} onChange={e=>filter(setProvider,e.target.value)}><option value="">All providers</option>{providers.map(p=><option key={p} value={p}>{providerNames[p]}</option>)}</select></label><label>Recovery eligibility<select value={eligibility} onChange={e=>filter(setEligibility,e.target.value)}><option value="all">All states</option><option value="eligible">Eligible</option><option value="waiting">Provider cooldown</option><option value="unavailable">No eligible provider</option></select></label><label>Recovery outcome<select value={outcome} onChange={e=>filter(setOutcome,e.target.value)}><option value="">All outcomes</option>{['name_recovered','attributes_recovered','already_known','missing','rate_limited','invalid_response'].map(o=><option key={o} value={o}>{labels[o]||o.replaceAll('_',' ')}</option>)}</select></label></div>
    <DataTable<RecoveryItem> label="Metadata recovery tracker" emptyMessage={q||provider||outcome||missing!=="all"||eligibility!=="all"?"No recovery items match these filters.": "No items are recorded for this market."} data={rows} loading={query.isFetching} error={query.error?.message} getRowId={r=>`${r.region}-${r.item_id}`} server={{rowCount:query.data?.total||0,pagination,sorting,onPaginationChange:setPagination,onSortingChange:value=>{setSorting(value);setPagination(p=>({...p,pageIndex:0}));}}} columns={[
      {id:"item_id",header:"Item",enableHiding:false,accessorFn:r=>r.item_id,cell:({row})=><Identity item={row.original} onSelect={()=>setItem(row.original.item_id)}/>},
      {id:"name",header:"Name",accessorFn:r=>r.name||`Item #${r.item_id}`},
      {id:"missing",header:"Missing metadata",enableSorting:false,cell:({row})=>row.original.missing.join(", ")||"No applicable gaps"},
      {id:"status",header:"Status",enableSorting:false,cell:({row})=><Status tone={row.original.status==="waiting"?"warning":"neutral"}>{labels[row.original.status]||row.original.status}</Status>},
      {id:"next",header:"Next attempt",enableSorting:false,cell:({row})=><>{row.original.next_provider ? providerNames[row.original.next_provider] : "No eligible provider"}{row.original.next_at && <><br/><LocalTime value={row.original.next_at}/></>}</>},
    ]} renderDetails={row=><div className="admin-status-details">
      <p>{row.explanation}</p>
      <div className="recovery-provider-list">{providers.map(provider=><div key={provider}>
        <ProviderEmblem provider={provider}/>{row.providers[provider]&&<RecoveryProviderStatus value={row.providers[provider]}/>}
      </div>)}</div>
      <p>Last useful recovery <LocalTime value={row.last_useful_at}/></p>
    </div>}/>
    {item&&<RecoveryJourney key={`${market}-${item}`} market={market} item={item} onClose={()=>{const selected=item;setItem(null);requestAnimationFrame(()=>{const trigger=Array.from(document.querySelectorAll<HTMLButtonElement>(`[data-recovery-item="${selected}"]`)).find(el=>el.getClientRects().length);trigger?.focus();});}} readOnly={readOnly}/>}
    <details className="panel padded"><summary>Recovery efficiency and measurement scope</summary>
      {query.data && <p className="muted">Measured <LocalTime value={query.data.measured_at}/> · {query.data.definition}</p>}
      <RecoveryEfficiency days={days} setDays={setDays} data={efficiency.data} error={efficiency.error?.message} loading={efficiency.isPending}/>
    </details>
  </section>;
}
