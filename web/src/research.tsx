import { Loading } from "./loading";
import { canonicalizeExplorerUrl, explorerState, explorerUrl, navigate, restoration, saveRestoration, type ExplorerState } from "./navigation";
import { usePreferences } from "./preferences";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState, DependencyList } from "react";
import { api, when } from "./api";
import { ItemCatalogue } from "./catalogue";
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
export function Freshness({ market }: { market: Market }) {
  return (
    <div className="freshness">
      <span className={`dot ${market.freshness}`} />
      <strong>
        {market.freshness === "unknown"
          ? "Source freshness unknown"
          : market.freshness === "stale"
            ? "Source data is stale"
            : "Source data current"}
      </strong>
      <span>Last successful check: {when(market.last_success)}</span>
      {!market.verified && (
        <span>Mapping not live-verified · collection disabled</span>
      )}
    </div>
  );
}
export function Explorer({markets,market,setMarket,searchParams,marketsReady}: {
  markets:Market[];market:number;setMarket:(id:number)=>void;searchParams:string;marketsReady:boolean;
}) {
  const preferences=usePreferences();
  const state=explorerState(searchParams,{market,query:'',sort:preferences.values.item_sort,pageIndex:0,pageSize:preferences.values.item_page_size});
  const [search,setSearch]=useState(()=>restoration()?.draft??state.query);
  const [summary,setSummary]=useState({synthetic:false,empty:false});
  const current=markets.find(row=>row.id===state.market);
  useEffect(()=>{setSearch(restoration()?.draft??state.query);},[state.query,state.market]);
  useEffect(()=>{if(markets.length&&current)canonicalizeExplorerUrl(searchParams,state);},[searchParams,markets.length,state.market,state.query,state.sort.id,state.sort.desc,state.pageIndex,state.pageSize]);
  function change(next:ExplorerState){navigate(explorerUrl(next),true);}
  return <div className="explorer-page">
    <h1>Market Explorer</h1>

    <form className="toolbar" onSubmit={event=>{event.preventDefault();saveRestoration({draft:search,expanded:{}});change({...state,query:search,pageIndex:0});}}>
      <label className="grow">Search items<input value={search} onChange={e=>{setSearch(e.target.value);saveRestoration({draft:e.target.value});}} placeholder="Item name or ID, e.g. Arcane Crystal" maxLength={64}/></label>
      <MarketSelect markets={markets} market={state.market} setMarket={id=>{setMarket(id);saveRestoration({draft:'',expanded:{}});change({...state,market:id,query:'',pageIndex:0});}}/>
      <button className="primary" disabled={!current}>Search</button>
    </form>
    {current&&(current.freshness!=="current"||!current.verified)&&<p className="small muted explorer-freshness" title={`Last collection check: ${when(current.last_success)}`}>{current.freshness==="stale"?"Source data is stale":current.freshness==="unknown"?"Source freshness unknown":""}{!current.verified&&" · Mapping not live-verified; collection disabled"}</p>}
    {!marketsReady&&<Loading label="Loading available markets…" />}
    {marketsReady&&!markets.length&&<p className="empty panel">No market mappings are configured. An administrator can add a mapping under Administration.</p>}
    {markets.length>0&&!current&&<p className="notice" role="alert">This market is unavailable. Choose an available market to browse; your link has not been moved to another market.</p>}
    {summary.synthetic&&<p className="notice warning">Synthetic fixture data · not live Auction House observations.</p>}
    {current&&<ItemCatalogue key={`${state.market}:${state.query}`} market={state.market} query={state.query} state={state} onChange={change} onSummary={setSummary}/>}
  </div>;
}
