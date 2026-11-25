import { Loading } from "./loading";
import { DataTable } from "./data-table";
import { useQuery } from "@tanstack/react-query";
import { variantLabel } from "./variant-label";
import "./deals-ux.css";
import {dealState,dealUrl,navigate,itemUrl,followItem,restoration,saveRestoration,useRestoreView} from "./navigation";
import { Currency, StackUnitPrice } from "./currency";
import { useEffect, useRef, useState } from "react";
import { ItemInfo } from "./item-components";
import { api } from "./api";
import { MarketPageHeading, MarketSelect, useLoad } from "./research";
import { Deal, Market, Signal } from "./types";

import { usePreferences } from "./preferences";
import type { PreferenceChanges, Preferences } from "./preferences-store";
type Mode = "listings" | "supply" | "price";
interface Filters {
  change: number;
  spend: number;
  coverage: number;
  confidence: string;
  direction: string;
}
type Quality = { state: "available" | "limited" | "needs_review" | "unavailable"; reason: string };
type ListingDeal = Deal & { reference_quality: Quality; variant: unknown; matching_listings: number; current_supply: number };
type ChangeSignal = Signal & { reference_quality?: Quality; variant?: unknown };
const pageSize = 20;
const modes = [["listings", "Below reference"], ["supply", "Supply changes"], ["price", "Price changes"]] as const;
interface Results {
  snapshot_id?: string;
  history_coverage: {
    observed_days: number;
    required_days: number;
    status: string;
    basis: string;
  };
  deals?: ListingDeal[];
  signals?: ChangeSignal[];
  synthetic: boolean;
  candidates_truncated: boolean;
  market: Market;
}

export function Deals({
  markets,
  marketsReady = true,
  market,
  setMarket,
  searchParams,
}: {
  markets: Market[];
  marketsReady?: boolean;
  market: number;
  setMarket: (id: number) => void;
  searchParams:string;
}) {
  const preferences=usePreferences();
  const saved=preferences.values;
  const browsing=dealState(searchParams,{market,mode:saved.deal_mode,filters:{change:saved.deal_change,spend:saved.deal_spend_gold,coverage:saved.deal_coverage,confidence:saved.deal_confidence,direction:saved.deal_direction}});
  market=browsing.market;const mode=browsing.mode;
  const pageText = new URLSearchParams(searchParams).get("page") ?? "0";
  const page = /^(0|[1-9]\d{0,5})$/.test(pageText) ? Number(pageText) : 0;
  const [showFilters, setShowFilters] = useState(() => !window.matchMedia("(max-width: 700px)").matches);
  const restored=()=>restoration()?.dealDraft??browsing.filters;
  const [filters,setFilters]=useState<Filters>(restored);
  useEffect(()=>{setFilters(restored());},[searchParams]);
  function apply(next=filters,nextMode=mode,nextMarket=market,draft=next,nextPage=0) {
    saveRestoration({dealDraft:draft});
    navigate(dealUrl({market:nextMarket,mode:nextMode,filters:next}) + (nextPage ? `&page=${nextPage}` : ""), true);
  }
  function changeFilters(changes:Partial<Filters>) {
    setFilters(previous=>({...previous,...changes}));
    const update:PreferenceChanges={};
    if(changes.change!==undefined&&Number.isInteger(changes.change)&&changes.change>=1&&changes.change<=(mode==="listings"?99:1000))update.deal_change=changes.change;
    if(changes.spend!==undefined&&Number.isFinite(changes.spend)&&changes.spend>=0.01&&changes.spend<=100000000)update.deal_spend_gold=changes.spend;
    if(changes.coverage!==undefined&&Number.isInteger(changes.coverage)&&changes.coverage>=1&&changes.coverage<=(mode==="listings"?15:14))update.deal_coverage=changes.coverage;
    if(changes.confidence!==undefined)update.deal_confidence=changes.confidence as Preferences['deal_confidence'];
    if(changes.direction!==undefined)update.deal_direction=changes.direction as Preferences['deal_direction'];
    if(Object.keys(update).length)preferences.update(update);
  }
  const submitted=browsing.filters;

  const common = new URLSearchParams({minimum_coverage: String(submitted.coverage), minimum_confidence: submitted.confidence});
  if (mode === "listings") {
    common.set("minimum_discount", String(submitted.change));
    common.set("maximum_spend", String(Math.round(submitted.spend * 10000)));
  } else {
    common.set("kind", mode);
    common.set("minimum_change", String(submitted.change));
    common.set("direction", submitted.direction);
  }
  const endpoint = `/markets/${market}/${mode === "listings" ? "deals" : "signals"}?${common}`;
  const result = useLoad("opportunities",
    signal => market ? api<Results>(`${endpoint}&limit=${pageSize}&offset=${page * pageSize}${mode === "listings" ? "&grouped=true" : ""}`, "GET", undefined, signal) : Promise.resolve(null),
    [market, mode, endpoint, page], true);
  useRestoreView(!result.loading,searchParams);
  const focusAfterPaging = useRef(false);
  useEffect(() => {
    if (!focusAfterPaging.current || result.loading) return;
    const frame = requestAnimationFrame(() => {
      document.getElementById("deal-result-count")?.focus();
      document.getElementById("deal-result-count")?.scrollIntoView({block:"start"});
      focusAfterPaging.current = false;
    });
    return () => cancelAnimationFrame(frame);
  }, [page, result.loading]);
  const turnPage = (next: number) => {
    focusAfterPaging.current = true;
    apply(submitted,mode,market,filters,next);
  };
  useEffect(()=>{if(markets.length&&location.pathname==='/deals'&&!searchParams)apply(browsing.filters);},[markets.length]);
  const deals = result.data?.deals || [],
    signals = result.data?.signals || [];
  const count = mode === "listings" ? deals.length : signals.length;
  function chooseMode(next: Mode) {
    const clamp = (value:Filters):Filters => ({
      ...value,
      change: Math.max(1, Math.min(value.change, next === "listings" ? 99 : 1000)),
      coverage: Math.max(1, Math.min(value.coverage, next === "listings" ? 15 : 14)),
    });
    const draft = clamp(filters);
    preferences.update({deal_mode:next,deal_change:draft.change,deal_coverage:draft.coverage});
    setFilters(draft);
    apply(clamp(submitted),next,market,draft);
  }
  const inspect = (event: React.MouseEvent<HTMLAnchorElement>) => {
    saveRestoration({ dealDraft: filters });
    followItem(event);
  };
  const selectedMarket = markets.find(row => row.id === market);
  const marketName = selectedMarket?.label;
  if (!marketsReady) return <section className="deals-view"><h1>Deal Finder</h1><Loading label="Loading markets…" skeleton/></section>;
  return <section className="deals-view">
    <MarketPageHeading title="Deal Finder" market={result.data?.market ?? selectedMarket}/>
    <div className="deal-modes" role="tablist" aria-label="Opportunity type">
      {modes.map(([key, title], index) => <button key={key} id={`deal-mode-${key}`}
        role="tab" aria-selected={mode === key} tabIndex={mode === key ? 0 : -1}
        aria-controls="deal-results" onClick={() => chooseMode(key)}
        onKeyDown={event => {
          const next = event.key === "ArrowRight" ? (index + 1) % 3 : event.key === "ArrowLeft" ? (index + 2) % 3 :
            event.key === "Home" ? 0 : event.key === "End" ? 2 : null;
          if (next === null) return;
          event.preventDefault();
          chooseMode(modes[next][0]);
          document.getElementById(`deal-mode-${modes[next][0]}`)?.focus();
        }}>{title}</button>)}
    </div>
    <div className="deal-controls panel">
      <button className="deal-filter-toggle" aria-expanded={showFilters} aria-controls="deal-filters" onClick={() => setShowFilters(!showFilters)}>
        <strong>Filters</strong><span>{submitted.change}% minimum · {submitted.coverage}d observed
          {mode === "listings" ? ` · ≤ ${submitted.spend.toLocaleString()}g` : submitted.direction !== "any" ? ` · ${submitted.direction}` : ""}
          {submitted.confidence !== "limited" && ` · ${submitted.confidence} coverage`}
        </span><b aria-hidden="true">{showFilters ? "−" : "+"}</b>
      </button>
      <form hidden={!showFilters} id="deal-filters" className="deal-filter-form" onSubmit={event => {
        event.preventDefault();
        apply(filters);
        if (window.matchMedia("(max-width: 700px)").matches) {
          setShowFilters(false);
          document.querySelector<HTMLButtonElement>(".deal-filter-toggle")?.focus();
        }
      }}>
        <MarketSelect markets={markets} market={market} setMarket={id => { setMarket(id); apply(submitted,mode,id,filters); }}/>
        <label>{mode === "listings" ? "Minimum discount (%)" : "Minimum change (%)"}
          <input type="number" min="1" max={mode === "listings" ? 99 : 1000} required
            value={filters.change || ""} onChange={e => changeFilters({change:Number(e.target.value)})}/></label>
        {mode === "listings" ? <label>Maximum spend (gold)
          <input type="number" min="0.01" max="100000000" step="0.01" required
            value={filters.spend || ""} onChange={e => changeFilters({spend:Number(e.target.value)})}/></label> :
          <label>Direction<select value={filters.direction} onChange={e => changeFilters({direction:e.target.value})}>
            <option value="any">Both directions</option><option value="increase">Increase only</option><option value="decrease">Decrease only</option>
          </select></label>}
        <label>Minimum observed days<input type="number" min="1" max={mode === "listings" ? 15 : 14} required
          value={filters.coverage || ""} onChange={e => changeFilters({coverage:Number(e.target.value)})}/></label>
        <label>Source evidence<select aria-label="Evidence" value={filters.confidence} onChange={e => changeFilters({confidence:e.target.value})}>
          <option value="limited">All sources</option><option value="moderate">Current, verified · 3+ days</option><option value="strong">Current, verified · 7+ days</option>
        </select></label>
        <button className="primary" disabled={!market}>Apply filters</button>
      </form>
    </div>
    <section id="deal-results" role="tabpanel" aria-labelledby={`deal-mode-${mode}`}>
      {(result.loading || result.refreshing) && <Loading label={result.data ? "Refreshing opportunities…" : "Loading opportunities…"} skeleton={!result.data}/>}
      {result.error && <div className="notice error" role="alert">Could not refresh these results. {result.error} <button onClick={() => result.refresh()}>Retry results</button></div>}
      {!market && <p className="empty panel">An administrator can add a market to start collecting prices.</p>}
      {result.data && <>
        <div className="deal-result-heading">
          <div><h2 id="deal-result-count" tabIndex={-1}>{count} {count === 1 ? "opportunity" : "opportunities"}{result.data.candidates_truncated || page > 0 ? " on this page" : ""}</h2>
            <span className="muted">{mode === "listings" ? "Matching listings by exact variant" : "Compared with prior observed UTC days"}{marketName && ` · ${marketName}`}</span></div>
          {result.data.synthetic && <span className="fixture-label">Test data</span>}
        </div>
        {result.data.history_coverage?.status === "insufficient" &&
          <p className="notice">{result.data.history_coverage.observed_days} of {result.data.history_coverage.required_days} required {mode === "listings" ? "" : "prior "}UTC days observed. Lower the day filter or check again after more collection.</p>}
        <div className="deal-list">
          {deals.map(deal => <DealCard key={`${deal.item_id}-${deal.variant_key}-${result.data?.snapshot_id}-${endpoint}`}
            deal={deal} market={market} endpoint={endpoint} snapshot={result.data!.snapshot_id} inspect={inspect} refresh={result.refresh}/>)}
          {signals.map(signal => <article className="panel deal" key={`${signal.item_id}-${signal.variant_key}`}>
            <div className="deal-heading"><div><h3><ItemInfo market={market} item={signal} label
              prices={{recent_price:signal.current_price,supply:signal.current_supply}}/></h3><span className="deal-variant">{variantLabel(signal.variant)}</span></div>
              {signal.reference_quality && signal.reference_quality.state !== "available" ? <span className="deal-review">{signal.reference_quality.state === "needs_review" ? "Reference needs review" : "Limited price history"}</span> :
                <strong className="deal-change">{signal.change_percent > 0 ? "+" : ""}{signal.change_percent}%</strong>}</div>
            <dl className="deal-metrics">{signal.kind === "price" ? <>
              <div><dt>Current ask / unit</dt><dd><Currency value={signal.current_price}/></dd></div>
              <div><dt>Prior reference / unit</dt><dd><Currency value={signal.reference_price}/></dd></div>
            </> : <>
              <div><dt>Current market supply</dt><dd>{signal.current_supply.toLocaleString()} units</dd></div>
              <div><dt>Prior average supply</dt><dd>{signal.reference_supply.toLocaleString()} units</dd></div>
            </>}</dl>
            {signal.reference_quality?.state === "needs_review" && <p className="deal-note">{signal.reference_quality.reason}</p>}
            <div className="deal-actions"><span className="muted">{signal.kind === "price" ? `${signal.coverage_days} priced days` : `${signal.coverage_days} listed days · ${signal.observed_market_days} market days`}</span>
              <a id={`signal-${signal.item_id}-${signal.variant_key}`} href={itemUrl(market,signal.item_id,signal.variant_key)} onClick={inspect}>Inspect item ↗</a></div>
          </article>)}
        </div>
        {!count && result.data.history_coverage.status !== "insufficient" && <p className="empty panel">No {mode === "listings" ? "listings" : "changes"} match these filters. Try a lower percentage or fewer observed days.</p>}
        {(page > 0 || result.data.candidates_truncated) && <nav className="deal-pager" aria-label="Opportunity pages">
          <button disabled={!page || result.loading} onClick={() => turnPage(page-1)}>Previous</button>
          <span aria-live="polite">Page {page+1}</span>
          <button disabled={!result.data.candidates_truncated || result.loading} onClick={() => turnPage(page+1)}>Next</button>
        </nav>}
        <p className="deal-note">References use asking prices. Completed sales and resale value are unknown.</p>
      </>}
    </section>
  </section>;
}

type Inspect = (event: React.MouseEvent<HTMLAnchorElement>) => void;
function DealCard({deal,market,endpoint,snapshot,inspect,refresh}:{deal:ListingDeal;market:number;endpoint:string;snapshot?:string;inspect:Inspect;refresh:()=>unknown}) {
  const [expanded,setExpanded] = useState(false);
  const review = deal.reference_quality.state === "needs_review";
  const limited = deal.reference_quality.state === "limited";
  return <article className="panel deal">
    <div className="deal-heading"><div><h3><ItemInfo market={market} item={deal} prices={{supply:deal.current_supply}} label/></h3>
      <span className="deal-variant">{variantLabel(deal.variant)}</span></div>
      {review || limited ? <span className="deal-review">{review ? "Reference needs review" : "Limited price history"}</span> : <strong className="deal-change">{deal.discount_percent}% below</strong>}</div>
    <dl className="deal-metrics">
      <div><dt>Lowest matching ask / unit</dt><dd><StackUnitPrice total={deal.total_buyout} quantity={deal.quantity}/></dd></div>
      <div><dt>14-day reference / unit</dt><dd><Currency value={deal.market_value}/></dd></div>
      <div><dt>Current market supply</dt><dd>{deal.current_supply.toLocaleString()} units</dd></div>
    </dl>
    <p className="deal-note">{review ? deal.reference_quality.reason + " " : ""}{deal.coverage_days} priced {deal.coverage_days === 1 ? "day" : "days"} observed.</p>
    <div className="deal-actions">
      <button type="button" className="text-button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
        {expanded ? "Hide" : "Show"} {deal.matching_listings.toLocaleString()} matching {deal.matching_listings === 1 ? "listing" : "listings"}</button>
      <a id={`deal-${deal.auction_id}`} href={itemUrl(market,deal.item_id,deal.variant_key)} onClick={inspect}>Inspect item ↗</a>
    </div>
    {expanded && <DealStacks deal={deal} endpoint={endpoint} snapshot={snapshot} refresh={refresh}/>}
  </article>;
}

function DealStacks({deal,endpoint,snapshot,refresh}:{deal:ListingDeal;endpoint:string;snapshot?:string;refresh:()=>unknown}) {
  const [pagination,setPagination] = useState({pageIndex:0,pageSize:10});
  const rows = useQuery({queryKey:["private","deal-stacks",endpoint,snapshot,deal.item_id,deal.variant_key,pagination],
    queryFn:({signal}) => api<Results>(`${endpoint}&item_id=${deal.item_id}&variant_key=${deal.variant_key}&limit=${pagination.pageSize}&offset=${pagination.pageIndex*pagination.pageSize}${snapshot ? `&expected_snapshot=${snapshot}` : ""}`, "GET", undefined, signal)});
  if (rows.isPending) return <Loading label="Loading matching listings…" skeleton/>;
  if (rows.isError) return <p className="notice error" role="alert">{rows.error.message} <button onClick={()=>{refresh();void rows.refetch();}}>Refresh listings</button></p>;
  return <DataTable<ListingDeal> compact label="Matching listings" data={rows.data?.deals ?? []} getRowId={row=>row.auction_id}
    server={{rowCount:deal.matching_listings,pagination,onPaginationChange:setPagination,sorting:[],onSortingChange:()=>{}}}
    columns={[
      {id:"quantity",header:"Stack size",cell:({row})=><span>{row.original.quantity.toLocaleString()}<small className="deal-stack-id">Listing {row.original.auction_id}</small></span>,enableSorting:false,meta:{numeric:true}},
      {id:"unit",header:"Per unit",cell:({row})=><StackUnitPrice total={row.original.total_buyout} quantity={row.original.quantity}/>,enableSorting:false,meta:{numeric:true}},
      {id:"total",header:"Stack cost",cell:({row})=><Currency value={row.original.total_buyout}/>,enableSorting:false,meta:{numeric:true}},
    ]}/>;
}
