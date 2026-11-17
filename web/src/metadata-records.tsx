import { useState } from "react";
import { DataTable } from "./data-table";
import { LocalTime, ProviderEmblem, Status, useRecordPage } from "./admin-table";
import { MetadataProvider, metadataStatus } from "./metadata-admin";

export function ProviderHealth({ providers }: { providers: MetadataProvider[] }) {
  return <DataTable<MetadataProvider> label="provider health" data={providers} getRowId={row=>row.provider} columns={[
    {accessorKey:"provider",header:"Source",enableHiding:false,cell:({row})=><ProviderEmblem provider={row.original.provider}/>},
    {id:"enabled",accessorFn:row=>row.enabled ? "Enabled":"Disabled",header:"Recovery",cell:({row})=><Status tone={row.original.enabled?"success":"neutral"}>{row.original.enabled?"Enabled":"Disabled"}</Status>},
    {accessorKey:"credential_status",header:"Connection",cell:({row})=><>{metadataStatus(row.original.credential_status)}{row.original.validation_pending && " · validation queued"}</>},
    {accessorKey:"last_success",header:"Last accepted response",cell:({row})=><LocalTime value={row.original.last_success}/>},
    {accessorKey:"recent_error",header:"Recent issue",cell:({row})=>metadataStatus(row.original.validation_error||row.original.recent_error)},
    {accessorKey:"cooldown_until",header:"Cooldown until",cell:({row})=><LocalTime value={row.original.cooldown_until}/>},
    {accessorKey:"hour_used",header:"Requests · hour / day",cell:({row})=>`${row.original.rate_limits?.windows.hour?.used ?? row.original.hour_used} / ${row.original.rate_limits?.windows.day?.used ?? row.original.day_used}`},
  ]} renderDetails={row=><dl className="record-details"><dt>Provider note</dt><dd>{row.note}</dd><dt>Last validation</dt><dd><LocalTime value={row.last_validated_at}/></dd><dt>Credential expiry</dt><dd><LocalTime value={row.expires_at}/></dd><dt>Configured budgets</dt><dd>{row.hourly_budget} / hour · {row.daily_budget} / day</dd><dt>Automatic recovery</dt><dd>{row.automatic?"Enabled":"Disabled"}</dd></dl>}/>;
}
interface Unresolved { id:string; item_id:number; region:string; market_presence:string; blizzard_status:string; supplemental_status:string; checked_at:string|null; retry_after:string|null; icon_available:boolean; icon_url:string|null }
export function UnresolvedNames({ market, chooseItem }: { market:number; chooseItem:(id:number)=>void }) {
  const [item,setItem]=useState(""),[primary,setPrimary]=useState("");
  const filters:Record<string,string>={market_id:String(market)};
  if(item)filters.item_id=item;
  if(primary)filters.primary=primary;
  const page=useRecordPage<Unresolved>("unresolved",filters,"item_id",false);
  return <section className="panel padded"><h3>Unresolved names</h3><p className="small muted">Current market snapshot. A provider’s missing response does not mean the auction item does not exist.</p>
    <div className="toolbar"><label>Search unresolved item ID<input type="search" inputMode="numeric" value={item} maxLength={10} onChange={e=>{if(/^\d*$/.test(e.target.value)&&Number(e.target.value)<=2147483647){setItem(e.target.value);page.reset();}}}/></label><label>Blizzard lookup<select value={primary} onChange={e=>{setPrimary(e.target.value);page.reset();}}><option value="">All</option><option value="missing">Provider reports missing</option><option value="pending">Pending or unavailable</option></select></label></div>
    <DataTable<Unresolved> label="unresolved names" data={page.query.data?.rows||[]} server={page.server} loading={page.query.isFetching} error={page.query.error?.message} getRowId={row=>row.id} columns={[
      {accessorKey:"item_id",header:"Item ID",enableHiding:false,cell:({row})=>`Item #${row.original.item_id}`},
      {accessorKey:"market_presence",header:"Market presence",enableSorting:false},
      {accessorKey:"blizzard_status",header:"Blizzard lookup",enableSorting:false},
      {accessorKey:"supplemental_status",header:"Supplemental lookup",enableSorting:false},
      {accessorKey:"checked_at",header:"Last attempt",cell:({row})=><LocalTime value={row.original.checked_at}/>},
      {accessorKey:"retry_after",header:"Next source retry",cell:({row})=><LocalTime value={row.original.retry_after}/>},
      {accessorKey:"icon_available",header:"Icon",enableSorting:false,cell:({row})=>row.original.icon_url?<img src={row.original.icon_url} width={28} height={28} alt={`Icon for item #${row.original.item_id}`} loading="lazy"/>:"Unknown"},
      {id:"action",header:"Recovery",enableSorting:false,cell:({row})=><button onClick={()=>chooseItem(row.original.item_id)}>Review recovery #{row.original.item_id}</button>},
    ]}/>
  </section>;
}
