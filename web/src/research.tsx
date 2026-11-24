import { Loading } from "./loading";
import { currentLocation, explorerState, explorerUrl, navigate, restoration, saveRestoration, type ExplorerState } from "./navigation";
import { usePreferences } from "./preferences";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState, DependencyList } from "react";
import { localTimestamp } from "./local-time";
import { ItemCatalogue, type CatalogueSummary } from "./catalogue";
import { Market } from "./types";

export function useLoad<T>(
  key: string,
  load: (signal?: AbortSignal) => Promise<T>,
  dependencies: DependencyList,
  retainPrevious = false,
) {
  const query = useQuery({
    queryKey: ["private", key, ...dependencies],
    queryFn: ({ signal }) => load(signal),
    // A filter refresh can retain rows only within the same market and result mode.
    placeholderData: (previous, previousQuery) => retainPrevious && previousQuery?.queryKey[2] === dependencies[0] && previousQuery?.queryKey[3] === dependencies[1] ? previous : undefined,
    refetchInterval: 60_000,
  });
  return {
    data: query.data,
    error: query.error?.message || "",
    loading: query.isPending || query.isPlaceholderData,
    refreshing:query.isFetching&&!query.isPending,
    refreshedAt: query.dataUpdatedAt,
    refresh: () => query.refetch(),
  };
}
export function MarketSelect({
  markets,
  market,
  setMarket,
}: {
  markets: Market[];
  market: number;
  setMarket: (id: number) => void;
}) {
  return (
    <label className="market-select">
      Market
      <select
        value={market}
        onChange={(event) => setMarket(Number(event.target.value))}
        disabled={!markets.length}
      >
        {!markets.length && <option value={0}>No markets configured</option>}
        {!!markets.length&&!markets.some(m=>m.id===market)&&<option value={market}>Unavailable market #{market}</option>}
        {markets.map((row) => (
          <option key={row.id} value={row.id}>
            {row.label}
          </option>
        ))}
      </select>
    </label>
  );
}
function sourceAge(timestamp: number, now: number): string {
  const minutes = Math.max(0, Math.floor((now - timestamp) / 60_000));
  if (minutes === 0) return "less than a minute ago";
  const [amount, unit] = minutes < 60 ? [minutes, "minute"] : minutes < 1440
    ? [Math.floor(minutes / 60), "hour"] : [Math.floor(minutes / 1440), "day"];
  return `${amount} ${unit}${amount === 1 ? "" : "s"} ago`;
}

export function Freshness({ market, refreshedAt }: { market: Market; refreshedAt?: number }) {
  const modified = Date.parse(market.last_modified ?? "");
  const now = Date.now();
  const validSourceTime = Number.isFinite(modified) && modified <= now + 5 * 60_000;
  const issue = !market.verified
    ? "Collection waits for an administrator to verify this market."
    : !market.enabled
      ? "Collection is paused. Prices come from the last available snapshot."
      : market.coverage_status === "partial"
        ? "Some auction data could not be checked. Prices and supply may be incomplete."
        : market.freshness === "stale"
          ? "Prices may have changed since the last source update. Market checks run automatically."
          : !validSourceTime ? "The source has supplied no usable update time." : undefined;
  return (
    <div className="player-freshness">
      <div className="player-freshness-line">
        <span className={`dot ${market.freshness}`} aria-hidden="true"/>
        <span>{validSourceTime ? `Source updated ${sourceAge(modified, now)}` : "Source update time unavailable"}</span>
        <details className="player-freshness-details">
          <summary>Timing</summary>
          <dl>
            <dt>Source updated</dt><dd>{validSourceTime ? localTimestamp(market.last_modified) : "Unrecorded"}</dd>
            <dt>Last checked</dt><dd>{localTimestamp(market.last_success)}</dd>
            <dt>View refreshed</dt><dd>{localTimestamp(refreshedAt ? new Date(refreshedAt).toISOString() : undefined)}</dd>
          </dl>
        </details>
      </div>
      {issue && <p className="player-freshness-issue">{issue}</p>}
    </div>
  );
}
export function Explorer({markets,market,setMarket,searchParams,marketsReady}: {
  markets:Market[];market:number;setMarket:(id:number)=>void;searchParams:string;marketsReady:boolean;
}) {
  const preferences=usePreferences();
  const state=explorerState(searchParams,{market,query:'',sort:preferences.values.item_sort,pageIndex:0,pageSize:preferences.values.item_page_size});
  const [search,setSearch]=useState(()=>restoration()?.draft??state.query);
  const [summary,setSummary]=useState<CatalogueSummary>({synthetic:false});
  const current=markets.find(row=>row.id===state.market);
  useEffect(()=>{setSearch(restoration()?.draft??state.query);},[state.query,state.market]);
  useEffect(()=>{if(markets.length&&current&&currentLocation()!==explorerUrl(state))navigate(explorerUrl(state),true);},[markets.length,state.market,state.query,state.sort.id,state.sort.desc,state.pageIndex,state.pageSize]);
  function change(next:ExplorerState){navigate(explorerUrl(next),true);}
  return <div className="explorer-page">
    <h1>Market Explorer</h1>

    <form className="toolbar explorer-search" onSubmit={event=>{event.preventDefault();saveRestoration({draft:search,expanded:{},variantComparison:{},catalogueScrollLeft:0});change({...state,query:search.trim(),pageIndex:0});}}>
      <div className="explorer-search-field">
        <label>Search items<input type="search" enterKeyHint="search" value={search} onChange={e=>{setSearch(e.target.value);saveRestoration({draft:e.target.value});}} placeholder="Item name or ID" maxLength={64}/></label>
        {(search || state.query) && <button type="button" className="secondary" onClick={() => {
          setSearch("");
          saveRestoration({draft:"",expanded:{},variantComparison:{},catalogueScrollLeft:0});
          change({...state,query:"",pageIndex:0});
        }}>Clear</button>}
      </div>
      <MarketSelect markets={markets} market={state.market} setMarket={id=>{setMarket(id);setSummary({synthetic:false});saveRestoration({draft:'',expanded:{},variantComparison:{},catalogueScrollLeft:0});change({...state,market:id,query:'',pageIndex:0});}}/>
      <button className="primary" disabled={!current}>Search</button>
    </form>
    {current && <Freshness market={summary.market?.id === current.id ? summary.market : current} refreshedAt={summary.refreshedAt}/>}
    {!marketsReady&&<Loading label="Loading available markets…" />}
    {marketsReady&&!markets.length&&<p className="empty panel">No market mappings are configured. An administrator can add a mapping under Administration.</p>}
    {markets.length>0&&!current&&<p className="notice" role="alert">This market is unavailable. Choose an available market to browse; your link has not been moved to another market.</p>}
    {summary.synthetic&&<p className="notice warning">Synthetic fixture data · not live Auction House observations.</p>}
    {current&&<ItemCatalogue key={`${state.market}:${state.query}`} market={state.market} query={state.query} state={state} onChange={change} onSummary={setSummary}/>}
  </div>;
}
