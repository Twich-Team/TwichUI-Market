import { useEffect, useMemo, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { LocalTime, Status } from "./admin-table";
import { Coin, Currency } from "./currency";
import { DataTable } from "./data-table";
import { ItemAttribution, ItemIcon } from "./item-components";
import { ItemName } from "./item-name";
import { Loading } from "./loading";
import { currentLocation, followItem, itemUrl, navigate, restoration, saveRestoration, useRestoreView } from "./navigation";
import { MarketSelect } from "./research";
import { CrateAttribution } from "./waylaid-attribution";
import { useCompactLayout } from "./responsive";
import type { Market } from "./types";
import {
  bases, basisDescriptions, compareCrates, crateColumns, crateSortValue, crateUrl, crateView, tierLabel,
  type CrateItem, type CrateQuote, type CrateResults, type CrateRow, type CrateView, type ExactCopper,
} from "./waylaid-crates-data";
import "./waylaid-crates.css";

type Column = CrateView["sort"];
const columns = Object.keys(crateColumns) as Column[];

const quoteStatuses: Record<string, string> = {
  available: "Price observed",
  insufficient_at_minimum: "Insufficient quantity at the minimum",
  limited: "Limited historical price coverage",
  missing_price: "Price unobserved",
  needs_review: "Price reference needs review",
  no_supported_bundles: "No supported material bundles",
  unsupported_tier: "Crate tier could not be verified",
  no_fully_priced_bundle: "No fully priced bundle",
  regional_unavailable: "Market has no regional reference",
  rounded_estimate: "Whole-stack buyout needed to validate the unit estimate",
  stale_freshness: "Market observations are stale",
  sufficient_at_minimum: "Required quantity available at the minimum",
  synthetic_observations: "Illustrative observations",
  unknown: "Current stock unknown",
  unavailable: "Price reference unavailable",
  unknown_favor: "Favor reward unconfigured",
  unknown_freshness: "Market freshness unknown",
  unsupported_statistics: "Compatible retained statistics unavailable",
  unverified_market: "Market mapping unverified",
  unverified_reward_quality: "Favor is unverified for this crate quality",
  whole_stack_overshoot: "Exact quantity unavailable in whole stacks at the minimum",
};

function Cost({ copper, exact }: { copper?: string | null; exact?: ExactCopper | null }) {
  if (!exact) return copper == null ? <span className="muted">Unknown</span> : <Currency value={copper}/>;
  const numerator = BigInt(exact.numerator_copper);
  const denominator = BigInt(exact.denominator);
  const rounded = (numerator + denominator / 2n) / denominator;
  if (numerator > 0n && rounded === 0n) {
    return <span className="currency" role="img" aria-label="Less than 1 copper">
      <span className="currency-part" aria-hidden="true">&lt;1<Coin metal="copper"/></span>
    </span>;
  }
  const approximate = numerator % denominator !== 0n;
  return <span title={approximate ? "Rounded to the nearest copper. Sorting uses the exact value." : undefined}>
    {approximate && <><span aria-hidden="true">≈ </span><span className="sr-only">Approximately </span></>}
    <Currency value={String(rounded)}/>
  </span>;
}

function CrateItemLink({ item, market, id }: { item: CrateItem; market: number; id: string }) {
  return <div>
    <a className="waylaid-item" href={itemUrl(market, item.item_id)} id={id} onClick={followItem}>
      <ItemIcon item={item}/>
      <ItemName name={item.name} quality={item.quality}/>
    </a>
    <ItemAttribution item={item}/>
  </div>;
}

function SelectedMaterials({ row, market }: { row: CrateRow; market: number }) {
  const chosen = row.bundles.find(bundle => bundle.bundle_id === row.selected_bundle_id);
  if (!chosen) return <span className="muted">No priced choice</span>;
  return <ul className="waylaid-selected-materials">
    {chosen.materials.map(quote => <li key={quote.item_id}>
      <span className="waylaid-material-quantity">{quote.quantity.toLocaleString()} × </span>
      <a href={itemUrl(market, quote.item_id)} id={`waylaid-${row.item.item_id}-chosen-${quote.item_id}`} onClick={followItem}>
        <ItemIcon item={quote.item}/>
        <ItemName name={quote.item.name} quality={quote.item.quality}/>
      </a>
      <ItemAttribution item={quote.item}/>
    </li>)}
  </ul>;
}

function detailsLabel(row: CrateRow, open: boolean) {
  return `${open ? "Hide" : "Show"} materials for ${row.item.name}`;
}

function CrateValue({ row, field }: { row: CrateRow; field: Column }) {
  switch (field) {
    case "tier": return row.tier ? tierLabel(row.tier) : <span className="muted">Unknown</span>;
    case "favor": return row.favor?.toLocaleString() ?? <span className="muted">{(row.reward_unavailable_reason || row.unavailable_reason) ? "Unavailable" : "Unconfigured"}</span>;
    case "purchase": return <Cost exact={row.purchase_cost_exact}/>;
    case "fill": return <Cost exact={row.fill_cost_exact}/>;
    case "total": return <Cost exact={row.total_cost_exact}/>;
    case "rate": return <>
      <Cost exact={row.cost_per_favor}/>
      {!row.eligible && row.cost_per_favor && <small className="waylaid-estimate">Estimate only</small>}
    </>;
  }
}

function quoteStatus(value: string) {
  return quoteStatuses[value] ?? value.replaceAll("_", " ").replace(/^./, character => character.toUpperCase());
}

function Quote({ quote, market, id }: { quote: CrateQuote; market: number; id: string }) {
  return <li className="waylaid-quote">
    <div>
      <CrateItemLink item={quote.item} market={market} id={id}/>
      <p className="small muted">
        {quote.quantity.toLocaleString()} required
        {quote.current_priced_quantity != null && <> · {quote.current_priced_quantity.toLocaleString()} currently priced</>}
        {quote.available_at_minimum != null && <> · {quote.available_at_minimum.toLocaleString()} at minimum</>}
      </p>
    </div>
    <div>
      <p><Cost exact={quote.unit_price_exact}/> <span className="small muted">/ unit</span></p>
      <p><Cost exact={quote.subtotal_exact}/> <span className="small muted">subtotal</span></p>
      {quote.minimum_purchase_copper !== null && quote.minimum_purchase_copper !== quote.subtotal_copper &&
        <p><Cost copper={quote.minimum_purchase_copper}/> <span className="small muted">minimum purchase</span></p>}
      {quote.coverage_days != null && <p className="small muted">{quote.coverage_days} observed days</p>}
      {quote.source_kind === "auctions" && <p className="small muted">Auction listings</p>}
      {quote.source_kind === "commodities" && <p className="small muted">Commodity listings</p>}
    </div>
    <div className="small muted">
      <p>{quoteStatus(quote.stock_status)}</p>
      {quote.quote_status !== "available" && quote.quote_status !== quote.stock_status && <p>{quoteStatus(quote.quote_status)}</p>}
      {quote.quality_reason && quote.quote_status !== "available" && <p>{quote.quality_reason}</p>}
      {quote.minimum_unit_copper !== null && quote.minimum_unit_copper !== quote.unit_price_copper &&
        <p>Current minimum <Cost copper={quote.minimum_unit_copper}/></p>}
    </div>
  </li>;
}

function CrateDetails({ row, market, owned }: { row: CrateRow; market: number; owned: boolean }) {
  const prefix = `waylaid-${row.item.item_id}`;
  const reasons = row.reasons.filter(reason =>
    reason !== row.unavailable_reason && !(reason === "unknown_favor" && row.reward_unavailable_reason));
  return <div className="waylaid-details">
    <div className="waylaid-detail-heading">
      <h3>Choose one</h3>
      {row.required_level != null && <span className="small muted">Required level {row.required_level}</span>}
    </div>
    {row.unavailable_reason && <p className="small muted">{quoteStatus(row.unavailable_reason)}</p>}
    {row.reward_unavailable_reason && <p className="small muted">{quoteStatus(row.reward_unavailable_reason)}</p>}
    {reasons.length > 0 &&
      <ul className="waylaid-reasons small muted">
        {reasons.map(reason => <li key={reason}>{quoteStatus(reason)}</li>)}
      </ul>}
    {!row.bundles.length && <p className="small muted">No supported material bundles are recorded for this crate.</p>}
    <div className="waylaid-bundles">
      {row.bundles.map((bundle, index) => (
        <section className="waylaid-bundle" key={bundle.bundle_id}>
          <div className="waylaid-detail-heading">
            <h4>Bundle {index + 1}</h4>
            {bundle.bundle_id === row.selected_bundle_id
              ? <Status tone={bundle.eligible ? "success" : "warning"}>Used in estimate</Status>
              : <Status tone={bundle.eligible ? "neutral" : "warning"}>{bundle.eligible ? "Alternative" : bundle.fill_cost_copper === null ? "Incomplete estimate" : "Estimate only"}</Status>}
          </div>
          <ul className="waylaid-materials">
            {bundle.materials.map(quote => <Quote key={quote.item_id} quote={quote} market={market}
              id={`${prefix}-bundle-${bundle.bundle_id}-${quote.item_id}`}/>)}
          </ul>
          <p className="waylaid-subtotal">Bundle cost <Cost exact={bundle.fill_cost_exact}/></p>
        </section>
      ))}
    </div>
    <section className="waylaid-bundle waylaid-purchase">
      <div className="waylaid-detail-heading">
        <h4>Crate purchase</h4>
        {owned && <span className="small muted">Already owned · excluded from cash cost</span>}
      </div>
      <ul className="waylaid-materials">
        <Quote quote={row.purchase_quote} market={market} id={`${prefix}-purchase`}/>
      </ul>
    </section>
  </div>;
}

function CrateSummary({ data, rows }: { data: CrateResults; rows: CrateRow[] }) {
  const ranked = rows.filter(row => row.eligible && row.cost_per_favor !== null);
  const best = ranked.reduce<CrateRow | undefined>((lowest, row) =>
    !lowest || compareCrates(row, lowest, "rate") < 0 ? row : lowest, undefined);
  return <div className="waylaid-metrics">
    <article>
      <span>Lowest comparable cost / Favor</span>
      <strong><Cost exact={best?.cost_per_favor}/></strong>
      <small>{best ? best.item.name : "No comparable crate in this view"}</small>
    </article>
    <article>
      <span>Comparable crates</span>
      <strong>{ranked.length.toLocaleString()} <small>of {rows.length.toLocaleString()}</small></strong>
      <small>In the current view</small>
    </article>
    <article>
      <span>Market observation</span>
      <strong>{data.pricing.freshness === "current" ? "Current" : data.pricing.freshness === "stale" ? "Stale" : "Unknown"}</strong>
      <small><LocalTime value={data.pricing.observed_at}/></small>
    </article>
  </div>;
}

export function WaylaidCrates({ markets, market, setMarket, marketStatus, searchParams }: {
  markets: Market[];
  market: number;
  setMarket: (id: number) => void;
  marketStatus: "loading" | "unavailable" | "available";
  searchParams: string;
}) {
  const view = crateView(searchParams, market);
  const [search, setSearch] = useState(view.query);
  const [expanded, setExpanded] = useState<Record<number, boolean>>(() => restoration()?.expanded ?? {});
  const compact = useCompactLayout();
  const active = markets.find(row => row.id === view.market);
  const response = useQuery({
    queryKey: ["private", "waylaid-crates", view.market, view.basis, view.owned],
    queryFn: ({ signal }) => api<CrateResults>(`/waylaid-crates?market_id=${view.market}&basis=${view.basis}&owned=${view.owned}`, "GET", undefined, signal),
    enabled: !!active,
    refetchInterval: 60_000,
    retry: false,
  });
  const data = response.data;
  useRestoreView(Boolean(data), searchParams);
  useEffect(() => setSearch(view.query), [view.query]);
  useEffect(() => {
    if (active && location.pathname === "/waylaid-crates") {
      const destination = crateUrl(view);
      if (currentLocation() !== destination) navigate(destination, true);
    }
  }, [active, searchParams, market]);
  function update(changes: Partial<CrateView>) {
    navigate(crateUrl({ ...view, ...changes }), true);
  }
  function toggle(item: number) {
    const next = { ...expanded, [item]: !expanded[item] };
    setExpanded(next);
    saveRestoration({ expanded: next });
  }
  function sort(column: Column) {
    update({ sort: column, direction: view.sort === column && view.direction === "asc" ? "desc" : "asc" });
  }
  const rows = data?.rows ?? [];
  const tiers = [...new Set(rows.flatMap(row => row.tier ? [row.tier] : []))];
  if (view.tier && !tiers.includes(view.tier)) tiers.push(view.tier);
  const query = view.query.toLowerCase();
  const filtered = rows.filter(row =>
    (!view.tier || row.tier === view.tier) &&
    (!view.known || (row.eligible && row.cost_per_favor !== null)) &&
    (!query || row.item.name.toLowerCase().includes(query) || String(row.item.item_id) === query)
  ).sort((left, right) => {
    if (view.sort === "rate" && left.eligible !== right.eligible) return left.eligible ? -1 : 1;
    return compareCrates(left, right, view.sort, view.direction === "desc");
  });
  const tableColumns = useMemo<ColumnDef<CrateRow>[]>(() => [
    { id: "crate", header: "Crate", enableSorting: false, meta: { rowHeader: true },
      cell: ({ row: { original } }) => <CrateItemLink item={original.item} market={view.market} id={`waylaid-item-${original.item.item_id}`}/> },
    { id: "materials", header: "Materials", enableSorting: false,
      cell: ({ row: { original } }) => <SelectedMaterials row={original} market={view.market}/> },
    ...columns.map<ColumnDef<CrateRow>>(field => ({
      id: field, header: crateColumns[field], sortDescFirst: false,
      accessorFn: row => field === "tier" ? row.tier : crateSortValue(row, field),
      meta: { numeric: true }, cell: ({ row: { original } }) => <CrateValue row={original} field={field}/>,
    })),
  ], [view.market]);
  return <div className="waylaid-page">
    <div className="waylaid-heading">
      <div><h1>Waylaid Crates</h1><p>Compare the cost of filling crates and earning Merchant’s Favor.</p></div>
      <button className="secondary" disabled={!active || response.isFetching} onClick={() => void response.refetch()}>Refresh prices</button>
    </div>
    <section className="panel waylaid-controls" aria-label="Pricing options">
      <MarketSelect markets={markets} market={view.market} setMarket={id => { setMarket(id); update({ market: id }); }}/>
      <label>Price basis<select value={view.basis} onChange={event => update({ basis: event.target.value as CrateView["basis"] })}>
        {Object.entries(bases).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select></label>
      <label className="checkbox"><input type="checkbox" checked={view.owned} onChange={event => update({ owned: event.target.checked })}/>I already own the crate</label>
      <p className="small muted waylaid-basis-note">{basisDescriptions[view.basis]}{view.owned && " Cash cost includes only materials."}</p>
    </section>
    {marketStatus === "loading" && <Loading label="Loading available markets…" skeleton/>}
    {marketStatus === "available" && (!markets.length
      ? <p className="empty panel">No market mappings are configured.</p>
      : !active && <p className="notice" role="alert">This market is unavailable. Choose an available market to compare crates.</p>)}
    {active && response.isPending && <Loading label="Loading Waylaid Crates…" skeleton/>}
    {response.error && <p className="notice error" role="alert">
      {data ? "Refresh failed. Showing the last loaded estimates." : "Waylaid Crates could not be loaded."}
      {" "}{response.error.message} <button onClick={() => void response.refetch()}>Retry estimates</button>
    </p>}
    {data && <>
      {view.basis === "regional" && <p className="notice">This market has no regional reference. Choose a different price basis to see available estimates.</p>}
      {data.pricing.synthetic && <p className="notice warning">Synthetic fixture data · illustrative prices and availability.</p>}
      {data.catalogue.stale && data.catalogue.refreshed_at && <p className="notice warning">Catalogue data is stale. Showing the last verified catalogue.</p>}
      {data.pricing.freshness === "stale" && <p className="notice warning">Market observations are stale. Prices and stock may have changed.</p>}
      <CrateSummary data={data} rows={filtered}/>
      <section className="panel waylaid-results" aria-label="Crate comparison" aria-busy={response.isFetching}>
        <div className="panel-heading">
          <div><h2>Crate comparison</h2>
            <p className="small muted">Favor uses administrator-configured values for Common crates. Rewards for other qualities are unavailable.</p>
          </div>
          <span className="small muted" role="status">{response.isFetching ? "Refreshing estimates…" : `${filtered.length.toLocaleString()} crates`}</span>
        </div>
        <form className="waylaid-filters" onSubmit={event => { event.preventDefault(); update({ query: search.trim() }); }}>
          <label>Search crates<input value={search} maxLength={64} placeholder="Name or item ID" onChange={event => setSearch(event.target.value)}/></label>
          <button className="secondary">Search</button>
          <label>Tier<select value={view.tier ?? ""} onChange={event => update({ tier: event.target.value || null })}>
            <option value="">All tiers</option>
            {tiers.map(tier => <option key={tier} value={tier}>{tierLabel(tier)}</option>)}
          </select></label>
          <label className="checkbox"><input type="checkbox" checked={view.known} onChange={event => update({ known: event.target.checked })}/>Comparable costs only</label>
        </form>
        {!rows.length && <p className="empty">No crate catalogue is available yet.</p>}
        {!!rows.length && !filtered.length && <p className="empty">No crates match these filters.</p>}
        {!!filtered.length && (compact ? <>
          <div className="mobile-sort waylaid-mobile-sort">
            <label>Sort crates<select value={view.sort} onChange={event => update({ sort: event.target.value as Column, direction: "asc" })}>
              {columns.map(column => <option key={column} value={column}>{crateColumns[column]}</option>)}
            </select></label>
            <button className="secondary" aria-label={`Sort direction: ${view.direction === "asc" ? "ascending" : "descending"}`} onClick={() => sort(view.sort)}>
              {view.direction === "asc" ? "Ascending ↑" : "Descending ↓"}
            </button>
          </div>
          <div className="waylaid-cards">
            {filtered.map(row => {
              const id = row.item.item_id;
              return <article className="waylaid-card" key={id}>
                <CrateItemLink item={row.item} market={view.market} id={`waylaid-item-${id}`}/>
                <dl className="waylaid-card-prices">{columns.map(column => <div key={column}><dt>{crateColumns[column]}</dt><dd><CrateValue row={row} field={column}/></dd></div>)}
                  <div className="waylaid-card-materials"><dt>Materials</dt><dd><SelectedMaterials row={row} market={view.market}/></dd></div>
                </dl>
                <DetailsButton row={row} open={!!expanded[id]} toggle={toggle}/>
                <div id={`waylaid-details-${id}`} hidden={!expanded[id]}>{expanded[id] && <CrateDetails row={row} market={view.market} owned={view.owned}/>}</div>
              </article>;
            })}
          </div>
        </> : <DataTable<CrateRow>
          label="Waylaid Crates estimates" data={filtered} columns={tableColumns} compact
          getRowId={row => String(row.item.item_id)}
          renderDetails={row => <CrateDetails row={row} market={view.market} owned={view.owned}/>}
          detailsControl={{
            isExpanded: row => !!expanded[row.item.item_id],
            toggle: row => toggle(row.item.item_id),
            label: detailsLabel,
          }}
          server={{
            rowCount: filtered.length,
            pagination: { pageIndex: 0, pageSize: filtered.length },
            onPaginationChange: () => {},
            sorting: [{ id: view.sort, desc: view.direction === "desc" }],
            onSortingChange: change => {
              const before = [{ id: view.sort, desc: view.direction === "desc" }];
              const next = (typeof change === "function" ? change(before) : change).at(-1);
              if (next) update({ sort: next.id as Column, direction: next.desc ? "desc" : "asc" });
              else sort(view.sort);
            },
          }}
        />)}
      </section>
      <CrateAttribution catalogue={data.catalogue}/>
    </>}
  </div>;
}

function DetailsButton({ row, open, toggle }: { row: CrateRow; open: boolean; toggle: (id: number) => void }) {
  return <button className="secondary waylaid-details-toggle" aria-expanded={open}
    aria-controls={`waylaid-details-${row.item.item_id}`}
    aria-label={detailsLabel(row, open)}
    onClick={() => toggle(row.item.item_id)}>
    {open ? "Hide details" : "Details"} <span aria-hidden="true">{open ? "−" : "+"}</span>
  </button>;
}
