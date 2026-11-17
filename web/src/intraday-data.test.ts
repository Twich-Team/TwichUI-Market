import { expect,it } from 'vitest';
import { withMissingHours,intradayLabel,intradayTooltip,type IntradayResponse } from './intraday-data';
const data:IntradayResponse={hours:24,window_start:'2026-11-01T05:00:00Z',window_end:'2026-11-01T08:00:00Z',notice:'fixture',synthetic:true,source_observation_count:2,points:[
 {bucket_start:'2026-11-01T05:00:00Z',observed_at:'2026-11-01T05:10:00Z',recent_price:'9007199254740993',lowest_buyout:'100',supply:3,listing_count:1,status:'available',observation_id:'1'},
 {bucket_start:'2026-11-01T06:00:00Z',observed_at:'2026-11-01T06:10:00Z',recent_price:'200',lowest_buyout:'100',supply:4,listing_count:1,status:'available',observation_id:'2'},
]};
it('only inserts unknown hour markers and preserves original observed times and exact money',()=>{
 const rows=withMissingHours(data);expect(rows).toHaveLength(4);expect(rows[0]).toBe(data.points[0]);
 expect(rows[2]).toMatchObject({status:'unobserved',observed_at:null,recent_price:null,supply:null});
 expect(intradayTooltip(rows[0])).toContain('900,719,925,474g 09s 93c');expect(intradayTooltip(rows[2])).toContain('Unknown');
 expect(withMissingHours({...data,window_end:'2030-01-01T00:00:00Z'})).toEqual([]);
});
it('disambiguates the repeated player-local DST hour while retaining UTC identity',()=>{
 const env=(globalThis as unknown as {process:{env:Record<string,string|undefined>}}).process.env,previous=env.TZ;env.TZ='America/New_York';
 try {const rows=withMissingHours(data);expect(intradayLabel(rows[0])).toContain('EDT');expect(intradayLabel(rows[1])).toContain('EST');expect(intradayLabel(rows[0])).not.toBe(intradayLabel(rows[1]));}finally{env.TZ=previous;}
});
