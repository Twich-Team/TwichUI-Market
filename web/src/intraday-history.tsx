import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from './api';
import { Currency } from './currency';
import { Loading } from './loading';
import { DeferredChart } from './deferred-chart';
import { DataTable } from './data-table';
import { LocalTime } from './admin-table';
import { withMissingHours,intradayLabel,intradayTooltip,type IntradayPoint,type IntradayResponse } from './intraday-data';
export function IntradayHistory({market,item,variant,hours}:{market:number;item:number;variant:string;hours:24|48}) {
 const query=useQuery({queryKey:['private','intraday-history',market,item,variant,hours],queryFn:({signal})=>api<IntradayResponse>(`/markets/${market}/items/${item}/${variant}/intraday-history?hours=${hours}`,'GET',undefined,signal),refetchInterval:60_000});
 const rows=useMemo(()=>query.data?withMissingHours(query.data):[],[query.data]);
 const option=useMemo(()=>({animation:false,grid:{left:75,right:25,top:30,bottom:90},textStyle:{color:'#c1b296'},
  tooltip:{trigger:'axis',renderMode:'richText',formatter:(params:unknown)=>{const index=(params as {dataIndex:number}[])[0]?.dataIndex;return index===undefined?'':intradayTooltip(rows[index]);}},
  xAxis:{type:'category',data:rows.map(intradayLabel),axisLabel:{hideOverlap:true,color:'#c1b296'}},
  yAxis:{type:'value',name:'Gold / unit',nameTextStyle:{color:'#c1b296'},axisLabel:{color:'#c1b296',formatter:(v:number)=>(v/10000).toLocaleString(undefined,{maximumFractionDigits:4})},splitLine:{lineStyle:{color:'#4a3926',type:'dashed'}}},
  dataZoom:[{type:'inside',filterMode:'none'},{type:'slider',bottom:15,height:24,borderColor:'#4a3926',textStyle:{color:'#c1b296'}}],
  series:[{name:'Observed recent asking price',type:'line',connectNulls:false,showSymbol:true,symbolSize:6,itemStyle:{color:'#d9b365'},data:rows.map(r=>r.recent_price===null?null:Number(r.recent_price))}],
 }),[rows]);
 if(query.isPending)return <div className="chart-placeholder"><Loading label={`Loading ${hours}-hour observations…`} skeleton/></div>;
 if(query.error)return <p className="notice error" role="alert">{query.error.message} <button onClick={()=>query.refetch()}>Retry intraday history</button></p>;
 const actual=query.data!.points,priced=actual.filter(p=>p.recent_price!==null).length;
 return <div className="intraday-history">
  <p className="small muted">{hours}H · Latest recorded observation in each UTC hour, shown in your local time. Prices are per unit; missing hours remain gaps. Edge hours can be partial. Exact copper is available in the tooltip and table. Asking prices are not completed sales.</p>
  {!actual.length&&<p className="notice">No retained intraday observations exist in this {hours}-hour window. Collection or retention may limit detail; daily samples are not substituted.</p>}
  {!!actual.length&&!priced&&<p className="notice">No priced intraday samples are available for this exact variant. It may be unlisted, or its statistics may be compacted or unsupported.</p>}
  {actual.some(p=>p.status==='compacted'||p.status==='unsupported_algorithm')&&<p className="notice">Some recorded hours have compacted or unsupported statistics. Those prices remain unavailable.</p>}
  {query.data!.synthetic&&<p className="small muted">Synthetic fixture observations · not live market data.</p>}
  {!!actual.length&&<DeferredChart option={option} label={`${hours}-hour observed asking-price history with genuine hourly gaps`}/>}
  <p className="small muted">{priced} priced hourly samples · {actual.length} observed hours · {rows.length-actual.length} unobserved hourly buckets · {query.data!.source_observation_count} recorded checks. Each point retains its original observation time.</p>
  <details><summary>Hourly observations &amp; provenance</summary><DataTable<IntradayPoint> label="intraday observations" data={rows} getRowId={r=>r.bucket_start} columns={[
   {id:'time',header:'Observed locally',enableHiding:false,accessorFn:r=>r.observed_at||r.bucket_start,cell:({row})=>row.original.observed_at?<LocalTime value={row.original.observed_at}/>:<span>{intradayLabel(row.original)} · Unobserved</span>},
   {accessorKey:'recent_price',header:'Recent / unit',cell:({row})=><Currency value={row.original.recent_price}/>},
   {accessorKey:'lowest_buyout',header:'Lowest / unit',cell:({row})=><Currency value={row.original.lowest_buyout}/>},
   {accessorKey:'supply',header:'Listed units',cell:({row})=>row.original.supply===null?'Unknown':row.original.supply.toLocaleString()},
   {accessorKey:'status',header:'Evidence',cell:({row})=>row.original.status.replaceAll('_',' ')},
  ]} renderDetails={row=><dl className="record-details"><dt>Observation / snapshot</dt><dd>{row.observation_id||'Unobserved'} / {row.snapshot_id||'Unknown'}</dd><dt>Exact time</dt><dd>{row.observed_at||'Unobserved'}</dd><dt>Namespace</dt><dd>{row.namespace||'Unknown'}</dd><dt>Payload hash</dt><dd><code>{row.payload_hash||'Unknown'}</code></dd><dt>Upstream modification</dt><dd>{row.upstream_modified||'Unrecorded'}</dd></dl>}/></details>
 </div>;
}
