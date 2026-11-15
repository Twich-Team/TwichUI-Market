import {useEffect} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api,when} from './api';
import {type ItemRoute,backDestination,returnToBrowse,navigate,itemUrl,currentLocation} from './navigation';
import {usePreferences} from './preferences';
import {type Group,type Page,type VariantPage,Variants,range} from './catalogue';
import {ItemInfo,ItemFacts,ItemAttribution,type ItemProfile} from './item-components';
import {ItemName} from './item-name';
import {Currency} from './currency';
import {LastSeen,localTimestamp} from './local-time';
import {PriceHistory,SupplyDistribution} from './charts';
import {CurrentListings} from './listings';
import type {Detail,Market} from './types';

export function ItemDetails({route,markets,marketsReady}:{route:ItemRoute;markets:Market[];marketsReady:boolean}){
  const current=markets.find(m=>m.id===route.market);
  if(!marketsReady)return <p role="status">Loading linked market…</p>;
  if(!current)return <section className="empty panel"><h1>Market unavailable</h1><p>Market #{route.market} is not available to this account. This item link has not been moved to another market.</p><a href="/" onClick={e=>{e.preventDefault();navigate('/');}}>Back to Explorer</a></section>;
  return <Research key={`${route.market}:${route.item}`} route={route} market={current}/>;
}
function Research({route,market}:{route:ItemRoute;market:Market}){
  const {market:marketId,item,variant}=route,preferences=usePreferences();
  const days=route.days??preferences.values.explorer_days;
  const profile=useQuery({queryKey:['private','item-profile',marketId,item],queryFn:({signal})=>api<ItemProfile>(`/markets/${marketId}/item-profiles/${item}`,'GET',undefined,signal),refetchInterval:60_000});
  const overview=useQuery({queryKey:['private','item-overview',marketId,item],queryFn:({signal})=>api<Page>(`/markets/${marketId}/catalogue?q=${item}&page_size=25`,'GET',undefined,signal),refetchInterval:60_000});
  const detail=useQuery({queryKey:['private','item-detail',marketId,item,variant],enabled:!!variant,queryFn:({signal})=>api<Detail>(`/markets/${marketId}/items/${item}/${variant}`,'GET',undefined,signal),refetchInterval:60_000});
  const group=overview.data?.items.find(row=>row.item_id===item);
  const sole=useQuery({queryKey:['private','sole-variant',marketId,item,overview.data?.snapshot_id],enabled:!variant&&group?.variant_count===1,queryFn:({signal})=>api<VariantPage>(`/markets/${marketId}/catalogue/${item}/variants?page_size=2&expected_snapshot=${overview.data?.snapshot_id || ''}`,'GET',undefined,signal),retry:false});
  useEffect(()=>{
    const result=sole.data;
    if(variant || group?.variant_count!==1 || !result || result.snapshot_id!==overview.data?.snapshot_id || result.total_variants!==1 || result.variants.length!==1)return;
    const key=result.variants[0].variant_key;
    if(!/^[a-f0-9]{64}$/.test(key))return;
    navigate(itemUrl(marketId,item,key)+(route.days?`&days=${route.days}`:''),true);
  },[variant,group?.variant_count,sole.data,overview.data?.snapshot_id,marketId,item,route.days]);
  const identity=profile.data??group??{item_id:item,name:`Item #${item}`,quality:null};
  const value=variant?detail.data?.valuation:undefined;
  const back=backDestination(marketId);
  useEffect(()=>{document.title=`${identity.name} · ${market.label} | TwichUI Market`;return()=>{document.title="TwichUI Market";};},[identity.name,market.label]);
  function setDays(next:typeof days){preferences.update({explorer_days:next});const url=new URL(currentLocation(),location.origin);url.searchParams.set('days',String(next));navigate(url.pathname+url.search,true);}
  return <div className="item-research">
    <div className="research-breadcrumb"><a href={back} onClick={returnToBrowse}>{back.startsWith('/deals')?'← Back to Deal Finder':'← Back to Explorer'}</a><span>{market.label}</span><button className="text-button" onClick={()=>{void overview.refetch();void profile.refetch();if(variant)void detail.refetch();}}>Refresh item</button></div>
    <div className="item-heading research-heading">
      <ItemInfo eager market={marketId} item={identity} prices={value} ranges={group?.price_ranges}/>
      <div><div className="eyebrow">ITEM RESEARCH</div><h1><ItemName name={identity.name} quality={identity.quality}/></h1><ItemAttribution item={identity}/>
        <p className="small muted">{variant?'Exact variant':'Overview across current variants'}</p>
      </div>
    </div>
    <div className="research-observation"><LastSeen value={variant ? detail.data?.last_seen_at : overview.data?.observed_at}/>
      {market.freshness==='stale'&&<span className="notice warning">Source data is stale</span>}
    </div>
    <details className="research-technical"><summary>Market technical details</summary><dl className="record-details">
      <dt>Item / market / house</dt><dd>{item} / {marketId} / {market.house_id}</dd>
      {variant&&<><dt>Exact variant</dt><dd><code className="variant-key">{variant}</code></dd></>}
      <dt>Last collection check</dt><dd>{localTimestamp(market.last_success)}</dd>
      <dt>Current snapshot</dt><dd>{overview.data?.snapshot_id || 'Unknown'}</dd>
      {value&&<><dt>Reference algorithm</dt><dd>{value.algorithm}. Workshop compatibility remains unverified.</dd></>}
    </dl></details>
    {!variant&&group?.variant_count===1&&sole.isPending&&<p role="status">Opening current variant…</p>}
    {sole.error&&<p role="alert" className="notice error">Current variant could not be verified. <button onClick={()=>{void overview.refetch();void sole.refetch();}}>Retry variant selection</button></p>}
    {(overview.data?.synthetic||value?.synthetic)&&<p className="notice warning">Synthetic fixture data · not live Auction House observations.</p>}
    {overview.isPending&&<p role="status">Loading current market overview…</p>}
    {overview.error&&<p role="alert" className="notice error">Current overview unavailable: {overview.error.message} <button onClick={()=>overview.refetch()}>Retry overview</button></p>}
    {variant&&detail.isPending&&<p role="status">Loading exact variant research…</p>}
    {detail.error&&<p role="alert" className="notice error">Variant research unavailable: {detail.error.message} <button onClick={()=>detail.refetch()}>Retry variant research</button></p>}
    {!overview.isPending&&!overview.error&&!group&&<p className="notice" role="status">This item has no listings in the current market snapshot. Retained metadata and exact-variant history can still be researched when available.</p>}
    {variant&&value&&value.listing_count===0&&<p className="notice" role="status">This exact variant is not currently listed in this market. Its URL is retained; no other variant has been substituted. Historical observations may still be available.</p>}
    {value?<div className="stats" aria-label="Exact variant current market">
      <article><label>LOWEST BUYOUT / UNIT</label><strong><Currency value={value.lowest_buyout}/></strong><small>Current asking price</small></article>
      <article><label>RECENT PRICE / UNIT</label><strong><Currency value={value.recent_price}/></strong><small>Quantity-weighted listings</small></article>
      <article><label>14-DAY MARKET REFERENCE</label><strong><Currency value={value.market_value}/></strong><small>{value.market_coverage_days} observed UTC days</small></article>
      <article><label>CURRENT MARKET SUPPLY</label><strong>{value.supply.toLocaleString()} units</strong><small>{value.listing_count.toLocaleString()} listings · {value.priced_supply.toLocaleString()} priced units</small></article>
    </div>:!variant&&group?<ParentOverview group={group}/>:null}
    {group&&group.variant_count>1&&<details className="panel research-variants" open={!variant} aria-label="Item variants"><summary>{group.variant_count} variants · {variant?'Change variant':'Choose a variant'}</summary><Variants key={`${marketId}:${item}`} market={marketId} item={group} replaceSelection selectedVariant={variant} snapshot={overview.data?.snapshot_id}/></details>}
    {!variant&&group&&group.variant_count>1&&<p className="notice">Prices above are ranges across variants. Select a variant to inspect its lowest buyout, historical charts and paginated auctions.</p>}
    {variant&&<>
      <div className="two-col research-charts">
        <section className="panel" aria-label="Price history"><div className="panel-heading"><h2>Price history</h2><div className="segmented" aria-label="History range">{([7,14,60,365,3650] as const).map(d=><button key={d} className={days===d?'selected':''} aria-pressed={days===d} onClick={()=>setDays(d)}>{d===3650?'10Y':`${d}D`}</button>)}</div></div>
          <PriceHistory key={`${marketId}:${item}:${variant}:${days}`} market={marketId} item={item} variant={variant} days={days}/>
          {value&&<p className="panel-note">60-day historical value: <Currency value={value.historical_value}/> · {value.coverage_days} observed days</p>}
        </section>
        <section className="panel" aria-label="Supply information"><div className="panel-heading"><h2>Supply by price</h2></div><SupplyDistribution key={`${marketId}:${item}:${variant}`} market={marketId} item={item} variant={variant}/></section>
      </div>
      <CurrentListings key={`${marketId}:${item}:${variant}`} market={marketId} item={item} variant={variant}/>
      <p className="small muted">Asking listings do not establish sales. Missing days remain unobserved.</p>
    </>}
    <section className="panel padded research-metadata" aria-label="Item metadata"><h2>Item metadata</h2>
      {profile.isPending&&<p role="status">Loading item metadata independently for this link…</p>}
      {profile.error&&<p className="notice error" role="alert">Item metadata could not be loaded. <button onClick={()=>profile.refetch()}>Retry metadata</button></p>}
      {profile.data&&<ItemFacts profile={profile.data}/>}
    </section>
  </div>;
}
function ParentOverview({group}:{group:Group}){
  return <div className="stats" aria-label="Variant ranges and total supply">
    <article><label>RECENT PRICE / UNIT RANGE</label><strong>{range(group.price_ranges.recent_price)}</strong><small>Across {group.priced_variant_count} priced variants</small></article>
    <article><label>14-DAY REFERENCE RANGE</label><strong>{range(group.price_ranges.market_value)}</strong><small>Variant references kept separate</small></article>
    <article><label>60-DAY REFERENCE RANGE</label><strong>{range(group.price_ranges.historical_value)}</strong><small>Existing observed-day references</small></article>
    <article><label>TOTAL CURRENT MARKET SUPPLY</label><strong>{group.supply.toLocaleString()} units</strong><small>{group.listing_count.toLocaleString()} listings · {group.variant_count} variants</small></article>
  </div>;
}
