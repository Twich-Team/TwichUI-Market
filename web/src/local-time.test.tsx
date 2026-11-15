import {expect,it} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {LastSeen,localTimestamp} from './local-time';
import {observationLabel,exactPriceTooltip,withMissingDays} from './chart-data';
for(const zone of ['America/Denver','Pacific/Auckland'])it(`formats midnight and DST instants locally without moving UTC buckets in ${zone}`,()=>{
  const env=(globalThis as unknown as {process:{env:Record<string,string|undefined>}}).process.env;const previous=env.TZ;env.TZ=zone;
  try{
    for(const stamp of ['2026-11-01T07:30:00Z','2026-11-01T08:30:00Z','2026-03-08T08:30:00Z','2026-03-08T09:30:00Z','2026-11-15T00:05:00Z']){
      const row={date:stamp.slice(0,10),observed_at:stamp,recent_price:'100',supply:1};
      expect(observationLabel(row)).toBe(new Date(stamp).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}));
      expect(exactPriceTooltip(row)).toContain(localTimestamp(stamp));
      expect(exactPriceTooltip(row)).toContain(`UTC-day bucket: ${row.date}`);
      expect(withMissingDays([row])[0]).toEqual(row);
      const date=new Date(stamp),label=`${String(date.getMonth()+1).padStart(2,'0')}/${String(date.getDate()).padStart(2,'0')}/${date.getFullYear()}`;
      expect(renderToStaticMarkup(<LastSeen value={stamp}/>)).toContain(`Last seen ${label}`);
    }
  }finally{env.TZ=previous;}
});
it('retains an explicitly labelled bucket when the historical instant is unknown',()=>{expect(observationLabel({date:'2026-11-15',recent_price:null,supply:null})).toBe('2026-11-15 UTC day');expect(renderToStaticMarkup(<LastSeen/>)).toContain('Last seen unknown');});
