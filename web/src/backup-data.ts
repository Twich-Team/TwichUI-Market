export interface RecoveryPoint {
 id:string;filename:string;created_at:string|null;type:string;bytes:number|null;protected:boolean;verification:string;restoration_verified_at:string|null;storage_id?:string;storage_name?:string;
}
export interface BackupFilters {search:string;storage:string;protection:string;verified:string;backupType:string;sort:string}
export function backupQueryParams(offset:number,filters?:BackupFilters,limit=100):URLSearchParams {
 const params=new URLSearchParams({offset:String(offset),limit:String(limit)});
 if(filters){if(filters.search)params.set('search',filters.search);if(filters.storage!=='all')params.set('storage_id',filters.storage);if(filters.protection!=='all')params.set('protection',filters.protection);if(filters.verified!=='all')params.set('verification',filters.verified);if(filters.backupType!=='all')params.set('backup_type',filters.backupType);if(filters.sort!=='created_desc')params.set('sort',filters.sort);}
 return params;
}
export interface ReliabilityDay {date:string;status:string;successes:number;failures:number;missed?:number;reason?:string}
/** No schedule history can be inferred from an empty day or today's enabled setting. */
export function reliabilityFromInventory(items:RecoveryPoint[],receipts:{at:string;action:string}[],now=new Date()):ReliabilityDay[]{
 return Array.from({length:42},(_,index)=>{
  const day=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate()-41+index)),date=day.toISOString().slice(0,10);
  const successes=items.filter(r=>r.created_at?.slice(0,10)===date&&r.verification==='archive_integrity_verified').length;
  const failures=receipts.filter(r=>r.at.slice(0,10)===date&&(r.action==='backup.failed'||r.action==='backup.creation.failed')).length;
  return {date,status:successes&&failures?'mixed':successes?'success':failures?'failed':'unknown',successes,failures,reason:successes||failures?'Recorded archive or execution receipt':'No complete historical schedule evidence'};
 });
}
export function recordedReliabilityDays(records:{day:string;succeeded:number;failed:number}[],now=new Date()):ReliabilityDay[]{
 const counts=new Map(records.map(row=>[row.day,row]));
 return reliabilityFromInventory([],[],now).map(day=>{
  const row=counts.get(day.date);
  return row?{...day,status:row.succeeded&&row.failed?'mixed':row.succeeded?'success':row.failed?'failed':'unknown',successes:row.succeeded,failures:row.failed,reason:'Recorded execution receipts'}:day;
 });
}
