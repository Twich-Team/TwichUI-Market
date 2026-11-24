export interface FilesystemSample {sampled_at:string;filesystem_available_bytes?:number|null}
export function filesystemForecast(samples:FilesystemSample[],total:number|null|undefined,reserve:number,now=Date.now()) {
  const rows=samples.filter((s):s is FilesystemSample&{filesystem_available_bytes:number}=>Number.isFinite(Date.parse(s.sampled_at))&&typeof s.filesystem_available_bytes==='number'&&Number.isFinite(s.filesystem_available_bytes)&&s.filesystem_available_bytes>=0).sort((a,b)=>Date.parse(a.sampled_at)-Date.parse(b.sampled_at));
  if(!total||total<=0||!Number.isFinite(total)||!Number.isFinite(reserve)||reserve<0||reserve>=total)return {reason:'Filesystem capacity or its safety reserve is unavailable.'} as const;
  const recent=rows.filter(r=>Date.parse(r.sampled_at)>=now-7*86400000&&Date.parse(r.sampled_at)<=now&&r.filesystem_available_bytes<=total);
  let start=0;for(let i=1;i<recent.length;i++){if(Date.parse(recent[i].sampled_at)-Date.parse(recent[i-1].sampled_at)>5400000)start=i;}
  const usable=recent.slice(start),last=usable.at(-1);
  if(!last||now-Date.parse(last.sampled_at)>7200000)return {reason:'A fresh filesystem measurement is needed before estimating capacity.'} as const;
  if(usable.length<3||Date.parse(last.sampled_at)-Date.parse(usable[0].sampled_at)<86400000)return {reason:'At least 24 hours of continuous filesystem measurements are needed for an estimate.'} as const;
  const end=Date.parse(last.sampled_at),xs=usable.map(r=>(Date.parse(r.sampled_at)-end)/86400000),ys=usable.map(r=>r.filesystem_available_bytes);
  const meanX=xs.reduce((a,b)=>a+b,0)/xs.length,meanY=ys.reduce((a,b)=>a+b,0)/ys.length;
  const slope=xs.reduce((sum,x,i)=>sum+(x-meanX)*(ys[i]-meanY),0)/xs.reduce((sum,x)=>sum+(x-meanX)**2,0);
  if(!Number.isFinite(slope)||slope>=0)return {reason:'Available space is stable or increasing. The measured trend does not support a time-to-capacity estimate.'} as const;
  const variance=ys.reduce((sum,y)=>sum+(y-meanY)**2,0),error=xs.reduce((sum,x,i)=>sum+(ys[i]-(meanY+slope*(x-meanX)))**2,0);
  if(!variance||1-error/variance<0.5)return {reason:'Recent filesystem measurements vary too much for a useful capacity estimate.'} as const;
  const days=Math.max(0,(last.filesystem_available_bytes-reserve)/-slope),horizon=Math.min(90,Math.max(1,days));
  return {reason:null,days,bytesPerDay:-slope,total,reserve,points:usable.map(r=>[Date.parse(r.sampled_at),total-r.filesystem_available_bytes] as [number,number]),projected:[[end,total-last.filesystem_available_bytes],[end+horizon*86400000,Math.min(total,total-last.filesystem_available_bytes-slope*horizon)]] as [number,number][]} as const;
}
