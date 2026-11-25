import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { IntradayHistory } from "./intraday-history";
import { Loading } from "./loading";
import { type ItemRoute, backDestination, returnToBrowse, navigate, itemUrl, currentLocation } from "./navigation";
import { usePreferences } from "./preferences";
import { type Group, type Page, type VariantPage, Variants, range } from "./catalogue";
import { ItemInfo, ItemFacts, type ItemProfile } from "./item-components";
import { ItemName } from "./item-name";
import { Currency } from "./currency";
import { LastSeen } from "./local-time";
import { PriceHistory, SupplyDistribution } from "./charts";
import { CurrentListings } from "./listings";
import { Freshness } from "./research";
import type { Detail, Market, ReferenceQuality, Valuation } from "./types";
import { variantLabel } from "./variant-label";

export function ItemDetails({ route, markets, marketsReady }: { route: ItemRoute; markets: Market[]; marketsReady: boolean }) {
  const current = markets.find((market) => market.id === route.market);
  if (!marketsReady) return <Loading label="Loading linked market…" />;
  if (!current) return <section className="empty panel"><h1>Market unavailable</h1><p>Market #{route.market} is unavailable to this account. Return to Explorer to choose another market.</p><a href="/" onClick={(event) => { event.preventDefault(); navigate("/"); }}>Back to Explorer</a></section>;
  return <Research key={`${route.market}:${route.item}`} route={route} market={current}/>;
}

const ranges = [
  { value: "24h", short: "24H", label: "24 hours" },
  { value: "48h", short: "48H", label: "48 hours" },
  { value: "7d", short: "7D", label: "7 days" },
  { value: "14d", short: "14D", label: "14 days" },
  { value: "60d", short: "60D", label: "60 days" },
  { value: "365d", short: "1Y", label: "1 year" },
  { value: "3650d", short: "10Y", label: "10 years" },
] as const;

function Research({ route, market }: { route: ItemRoute; market: Market }) {
  const { market: marketId, item, variant } = route;
  const preferences = usePreferences();
  const cache = useQueryClient();
  const days = route.days ?? preferences.values.explorer_days;
  const rangeValue = route.hours ? `${route.hours}h` : `${days}d`;
  const profile = useQuery({
    queryKey: ["private", "item-profile", marketId, item],
    queryFn: ({ signal }) => api<ItemProfile>(`/markets/${marketId}/item-profiles/${item}`, "GET", undefined, signal),
    refetchInterval: 60_000,
  });
  const overview = useQuery({
    queryKey: ["private", "item-overview", marketId, item],
    queryFn: ({ signal }) => api<Page>(`/markets/${marketId}/catalogue?q=${item}&page_size=25`, "GET", undefined, signal),
    refetchInterval: 60_000,
  });
  const detail = useQuery({
    queryKey: ["private", "item-detail", marketId, item, variant],
    enabled: !!variant,
    queryFn: ({ signal }) => api<Detail>(`/markets/${marketId}/items/${item}/${variant}`, "GET", undefined, signal),
    refetchInterval: 60_000,
  });
  const group = overview.data?.items.find((row) => row.item_id === item);
  const snapshot = overview.data?.snapshot_id;
  const sole = useQuery({
    queryKey: ["private", "sole-variant", marketId, item, snapshot],
    enabled: !variant && group?.variant_count === 1,
    queryFn: ({ signal }) => api<VariantPage>(`/markets/${marketId}/catalogue/${item}/variants?page_size=2&expected_snapshot=${snapshot ?? ""}`, "GET", undefined, signal),
    retry: false,
  });
  useEffect(() => {
    const result = sole.data;
    if (variant || group?.variant_count !== 1 || !result || result.snapshot_id !== snapshot || result.total_variants !== 1 || result.variants.length !== 1) return;
    const key = result.variants[0].variant_key;
    if (!/^[a-f0-9]{64}$/.test(key)) return;
    navigate(itemUrl(marketId, item, key) + (route.days ? `&days=${route.days}` : "") + (route.hours ? `&hours=${route.hours}` : ""), true);
  }, [variant, group?.variant_count, sole.data, snapshot, marketId, item, route.days, route.hours]);

  const identity = profile.data ?? group ?? detail.data ?? { item_id: item, name: `Item #${item}`, quality: null };
  const value = variant ? detail.data?.valuation : undefined;
  const back = backDestination(marketId);
  const browseLabel = back.startsWith("/waylaid-crates") ? "Waylaid Crates" : back.startsWith("/deals") ? "Deal Finder" : "Explorer";
  const refreshing = overview.isFetching || profile.isFetching || (variant && detail.isFetching);
  useEffect(() => {
    document.title = `${identity.name} · ${market.label} | TwichUI Market`;
    return () => { document.title = "TwichUI Market"; };
  }, [identity.name, market.label]);

  function setRange(range: typeof ranges[number]["value"]) {
    const url = new URL(currentLocation(), location.origin);
    if (range === "24h" || range === "48h") {
      url.searchParams.set("hours", range.slice(0, -1));
    } else {
      const nextDays = Number(range.slice(0, -1)) as typeof days;
      preferences.update({ explorer_days: nextDays });
      url.searchParams.delete("hours");
      url.searchParams.set("days", String(nextDays));
    }
    navigate(url.pathname + url.search, true);
  }
  function refresh() {
    void overview.refetch();
    void profile.refetch();
    if (!variant) return;
    void detail.refetch();
    for (const key of ["chart-history", "intraday-history", "distribution", "current-listings"]) {
      void cache.invalidateQueries({ queryKey: ["private", key, marketId, item, variant] });
    }
  }

  return <div className="item-research">
    <div className="research-breadcrumb">
      <a href={back} onClick={returnToBrowse}>← Back to {browseLabel}</a>
      <button className="text-button" onClick={refresh} disabled={!!refreshing}>{refreshing ? "Refreshing…" : "Refresh item"}</button>
    </div>

    <div className="item-heading research-heading">
      <ItemInfo eager market={marketId} item={identity}/>
      <div>
        <h1 id="research-title" tabIndex={-1}><ItemName name={identity.name} quality={identity.quality}/></h1>
        <p className="research-identity-line">
          <span>{market.label}</span>{variant ? (detail.data?.variant ? ` · ${variantLabel(detail.data.variant)}` : " · Exact variant")
            : group && group.variant_count > 1 ? " · All variants" : ""}
        </p>
      </div>
    </div>
    <Freshness market={detail.data?.market ?? overview.data?.market ?? market} refreshedAt={variant ? detail.dataUpdatedAt : overview.dataUpdatedAt}/>

    {!variant && group?.variant_count === 1 && sole.isPending && <Loading label="Opening current variant…" />}
    {sole.error && <p role="alert" className="notice error">Current variant could not be verified. <button onClick={() => { void overview.refetch(); void sole.refetch(); }}>Retry variant selection</button></p>}
    {(overview.data?.synthetic || value?.synthetic) && <p className="research-fixture">Fixture data</p>}
    {!variant && overview.isPending && <Loading label="Loading current market overview…" skeleton/>}
    {overview.error && <p role="alert" className="notice error">Current variant comparison could not be loaded. <button onClick={() => overview.refetch()}>Retry overview</button></p>}
    {variant && detail.isPending && <Loading label="Loading exact variant research…" skeleton/>}
    {detail.error && <p role="alert" className="notice error">Prices and supply could not refresh. <button onClick={() => detail.refetch()}>Retry variant research</button></p>}
    {!variant && !overview.isPending && !overview.error && !group && <p className="notice" role="status">No listings for this item in the current market.</p>}
    {variant && value?.listing_count === 0 && <p className="notice" role="status">This exact variant is not currently listed. You can still review its price history below.</p>}

    {value ? <VariantOverview value={value}/> : !variant && group ? <ParentOverview group={group}/> : null}

    {variant && <div className="research-charts">
      <section className="panel research-price-card" aria-label="Price history">
        <div className="panel-heading">
          <h2>Price history</h2>
          <div className="segmented research-range-buttons" aria-label="History range">
            {ranges.map(({ value, short, label }) => <button key={value} title={label}
              className={rangeValue === value ? "selected" : ""} aria-pressed={rangeValue === value}
              onClick={() => setRange(value)}>{short}</button>)}
          </div>
          <label className="research-range-select">
            <span className="sr-only">History range</span>
            <select value={rangeValue} onChange={(event) => setRange(event.target.value as typeof ranges[number]["value"])}>
              {ranges.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
        </div>
        {route.hours
          ? <IntradayHistory key={`${marketId}:${item}:${variant}:${route.hours}`} market={marketId} item={item} variant={variant} hours={route.hours}/>
          : <PriceHistory key={`${marketId}:${item}:${variant}:${days}`} market={marketId} item={item} variant={variant} days={days}/>}
        {value && <details className="research-history-reference">
          <summary>60-day reference</summary>
          <p><Currency value={value.historical_value}/> · {value.coverage_days} observed days</p>
          <ReferenceStatus quality={value.historical_reference_quality}/>
        </details>}
      </section>
      <section className="panel research-supply-card" aria-label="Supply information">
        <div className="panel-heading"><h2>Supply by price</h2></div>
        <SupplyDistribution key={`${marketId}:${item}:${variant}`} market={marketId} item={item} variant={variant}/>
      </section>
    </div>}

    {group && group.variant_count > 1 && <details className="panel research-variants" open={!variant} aria-label="Item variants">
      <summary>{group.variant_count} variants · {variant ? "Change variant" : "Choose a variant to see its history"}</summary>
      <Variants key={`${marketId}:${item}`} market={marketId} item={group} replaceSelection selectedVariant={variant}
        snapshot={snapshot} onRefreshCatalogue={() => { void overview.refetch(); }}/>
    </details>}
    {variant && <CurrentListings key={`${marketId}:${item}:${variant}`} market={marketId} item={item} variant={variant}/>}

    <section className="panel padded research-metadata" aria-label="Item metadata">
      <details open={!!profile.error}>
        <summary><h2>Item metadata</h2></summary>
        {profile.isPending && <Loading label="Loading item metadata…" />}
        {profile.error && <p className="notice error" role="alert">Item metadata could not be loaded. <button onClick={() => profile.refetch()}>Retry metadata</button></p>}
        {profile.data && <ItemFacts profile={profile.data}/>}
      </details>
      <details className="research-technical">
        <summary>Market technical details</summary>
        <dl className="record-details">
          <dt>Item / market / house</dt><dd>{item} / {marketId} / {market.house_id}</dd>
          {variant && <><dt>Exact variant identifier</dt><dd><code className="variant-key">{variant}</code></dd></>}
          <dt>Last observed</dt><dd><LastSeen value={variant ? detail.data?.last_seen_at : overview.data?.observed_at}/></dd>
          <dt>Current snapshot</dt><dd>{snapshot || "Unrecorded"}</dd>
          {value && <>
            <dt>Current prices</dt><dd>Lowest and recent asking prices are rounded to copper. Recent price is the total buyout cost divided by units priced. Asking prices do not establish completed sales.</dd>
            <dt>Reference basis</dt><dd>Average of the last priced observation per UTC day in the reference window. Unpriced days are excluded. Algorithm {value.algorithm}.</dd>
            <dt>Market supply</dt><dd>All {value.supply.toLocaleString()} listed units, including {(value.supply - value.priced_supply).toLocaleString()} bid-only units.</dd>
          </>}
        </dl>
      </details>
    </section>
  </div>;
}

function ReferenceStatus({ quality }: { quality?: ReferenceQuality }) {
  if (!quality || quality.state === "available") return null;
  return <div className="research-reference-status">
    <strong>{quality.state === "needs_review" ? "Reference needs review" : quality.state === "limited" ? "Limited reference" : "Reference unavailable"}</strong>
    <div>{quality.reason}</div>
  </div>;
}

function VariantOverview({ value }: { value: Valuation }) {
  const state = value.reference_quality?.state;
  const questionable = state === "needs_review";
  return <div className="stats research-stats" aria-label="Exact variant current market">
    <article><span className="research-metric-label">Lowest / unit</span><strong><Currency value={value.lowest_buyout}/></strong><small>Current buyout</small></article>
    <article><span className="research-metric-label">Recent asking / unit</span><strong><Currency value={value.recent_price}/></strong><small>Weighted by quantity</small></article>
    <article>
      <span className="research-metric-label">14-day reference</span>
      {questionable ? <strong className="research-reference-review">Needs review</strong> : <strong><Currency value={value.market_value}/></strong>}
      {state && state !== "available" ? <details className="research-reference-detail">
        <summary>{value.market_coverage_days} observed days{state === "limited" ? " · Limited" : ""}</summary>
        {questionable && <p><Currency value={value.market_value}/></p>}
        <ReferenceStatus quality={value.reference_quality}/>
      </details> : <small>{value.market_coverage_days} observed days</small>}
    </article>
    <article><span className="research-metric-label">Market supply</span><strong>{value.supply.toLocaleString()} units</strong><small>{value.listing_count.toLocaleString()} listings</small></article>
  </div>;
}

function ParentOverview({ group }: { group: Group }) {
  return <div className="stats research-stats" aria-label="Variant ranges and total supply">
    <article><span className="research-metric-label">Lowest / unit range</span><strong>{group.price_ranges.lowest_buyout ? range(group.price_ranges.lowest_buyout) : "Unavailable"}</strong></article>
    <article><span className="research-metric-label">Recent asking / unit range</span><strong>{range(group.price_ranges.recent_price)}</strong></article>
    <article><span className="research-metric-label">14-day reference range</span><strong>{range(group.price_ranges.market_value)}</strong></article>
    <article><span className="research-metric-label">Total market supply</span><strong>{group.supply.toLocaleString()} units</strong><small>{group.listing_count.toLocaleString()} listings · {group.variant_count} variants</small></article>
  </div>;
}
