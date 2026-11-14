import { useQuery } from '@tanstack/react-query';
import { api } from './api';
import type { Market } from './types';
import { PreferenceStatus, usePreferences } from './preferences';
import type { Preferences } from './preferences-store';

export function MyPreferences() {
  const {values,update,reset}=usePreferences();
  const markets=useQuery({queryKey:['private','personal-market-choices'],
    queryFn:({signal})=>api<{markets:Market[]}>('/markets','GET',undefined,signal)});
  const missing=values.market_id!==null&&markets.data&&!markets.data.markets.some(m=>m.id===values.market_id);
  return <section className="panel padded" aria-label="My Preferences">
    <h2>My Preferences</h2>
    <p>Your choices save automatically to your account and follow you across devices.</p>
    <div className="toolbar">
      <label>Preferred market
        <select value={values.market_id??''} onChange={event=>update({market_id:event.target.value?Number(event.target.value):null})} disabled={!markets.data}>
          <option value="">Use an available collecting market</option>
          {missing&&<option value={values.market_id!}>Preferred market currently unavailable</option>}
          {markets.data?.markets.map(market=><option key={market.id} value={market.id}>{market.label}</option>)}
        </select>
      </label>
      <label>Explorer chart range
        <select value={values.explorer_days} onChange={event=>update({explorer_days:Number(event.target.value) as Preferences['explorer_days']})}>
          {([7,14,60,365,3650] as const).map(days=><option key={days} value={days}>{days===3650?'10 years':`${days} days`}</option>)}
        </select>
      </label>
      <label>Item table page size
        <select value={values.item_page_size} onChange={event=>update({item_page_size:Number(event.target.value) as Preferences['item_page_size']})}>
          {[25,50,100].map(size=><option key={size} value={size}>{size} items</option>)}
        </select>
      </label>
    </div>
    <p className="small muted">Item columns and sorting save from Market Explorer. Your Deal Finder mode and filter choices save as you change them. These choices never change collection schedules.</p>
    {markets.error&&<p role="alert">Market choices could not be loaded.</p>}
    <PreferenceStatus />
    <p><button className="secondary" onClick={reset}>Reset my preferences</button></p>
  </section>;
}
