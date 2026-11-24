import {describe,it,expect} from 'vitest';
import {filesystemForecast} from './storage-forecast-data';
const day=86400000,now=Date.UTC(2026,10,24,20),sample=(hours:number,available:number)=>({sampled_at:new Date(now-hours*3600000).toISOString(),filesystem_available_bytes:available});
const trend=Array.from({length:25},(_,i)=>sample(24-i,800-i*10));
describe('filesystem forecasts',()=>{
  it('uses actual net filesystem free-space slope and reserve',()=>{const result=filesystemForecast(trend,1000,100,now);expect(result.reason).toBeNull();if(result.reason===null){expect(result.bytesPerDay).toBeCloseTo(240);expect(result.days).toBeCloseTo(460/240);expect(result.points.at(-1)?.[1]).toBe(440);}});
  it('does not forecast sparse, missing or stale samples',()=>{expect(filesystemForecast([sample(24,800),sample(0,560)],1000,100,now).reason).toContain('24 hours');expect(filesystemForecast(trend,1000,100,now+day).reason).toContain('fresh');expect(filesystemForecast([],null,100,now).reason).toContain('unavailable');});
  it('does not forecast stable or increasing free space',()=>{expect(filesystemForecast(trend.map(s=>({...s,filesystem_available_bytes:700})),1000,100,now).reason).toContain('stable');expect(filesystemForecast(trend.map((s,i)=>({...s,filesystem_available_bytes:500+i*10})),1000,100,now).reason).toContain('increasing');});
  it('uses only the continuous segment after a gap',()=>{expect(filesystemForecast(trend.filter((_,i)=>i!==20),1000,100,now).reason).toContain('24 hours');});
});
