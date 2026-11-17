export interface StorageSample { sampled_at:string; database_bytes:number }
export function growthView(input:StorageSample[], days:number|null=null) {
  const sorted=input.filter(row=>Number.isFinite(Date.parse(row.sampled_at))&&Number.isFinite(row.database_bytes)&&row.database_bytes>=0).slice().sort((a,b)=>Date.parse(a.sampled_at)-Date.parse(b.sampled_at));
  const end=sorted.length ? Date.parse(sorted[sorted.length-1].sampled_at) : 0;
  const rows=sorted.filter(row=>days===null||Date.parse(row.sampled_at)>=end-days*86400000);
  const elapsed=rows.length>1 ? (Date.parse(rows[rows.length-1].sampled_at)-Date.parse(rows[0].sampled_at))/1000 : 0;
  const delta=elapsed ? rows[rows.length-1].database_bytes-rows[0].database_bytes : null;
  const points: [number,number|null][]=[];let gaps=0;
  rows.forEach((row,index)=>{const stamp=Date.parse(row.sampled_at);if(index&&stamp-Date.parse(rows[index-1].sampled_at)>5400000){points.push([Date.parse(rows[index-1].sampled_at)+3600000,null]);gaps++;}points.push([stamp,row.database_bytes]);});
  return {rows,points,elapsed,delta,gaps,bytesPerDay:delta!==null&&elapsed>=86400 ? delta*86400/elapsed : null,availableDays:sorted.length>1 ? (end-Date.parse(sorted[0].sampled_at))/86400000 : 0};
}
