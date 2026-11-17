import { money } from './api';
import { localTimestamp } from './local-time';
export interface IntradayPoint {
 bucket_start:string; observed_at:string|null; recent_price:string|null; lowest_buyout:string|null;
 supply:number|null; listing_count:number|null; status:string; synthetic?:boolean;
 observation_id?:string;snapshot_id?:string;namespace?:string;payload_hash?:string;upstream_modified?:string|null;observations_in_hour?:number;
}
export interface IntradayResponse {points:IntradayPoint[];window_start:string;window_end:string;hours:24|48;notice:string;synthetic:boolean;source_observation_count:number}
export function withMissingHours(data:IntradayResponse):IntradayPoint[] {
 const start=Math.floor(Date.parse(data.window_start)/3600000)*3600000,end=Math.floor(Date.parse(data.window_end)/3600000)*3600000;
 if(!Number.isFinite(start)||!Number.isFinite(end)||end<start||end-start>48*3600000)return [];
 const byHour=new Map(data.points.map(row=>[Date.parse(row.bucket_start),row]));const rows:IntradayPoint[]=[];
 for(let time=start;time<=end;time+=3600000)rows.push(byHour.get(time)||{bucket_start:new Date(time).toISOString(),observed_at:null,recent_price:null,lowest_buyout:null,supply:null,listing_count:null,status:'unobserved'});
 return rows;
}
export function intradayLabel(row:IntradayPoint):string {
 return new Date(row.observed_at||row.bucket_start).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'});
}
export function intradayTooltip(row:IntradayPoint):string {
 return `${row.observed_at?localTimestamp(row.observed_at):intradayLabel(row)+' · unobserved hour'}\nRecent asking: ${money(row.recent_price)}\nLowest asking: ${money(row.lowest_buyout)}\nSupply: ${row.supply===null?'Unknown':row.supply.toLocaleString()}\n${row.status.replaceAll('_',' ')}${row.observation_id?' · Observation #'+row.observation_id:''}`;
}
