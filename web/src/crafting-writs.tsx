import { useEffect, useMemo, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { LocalTime } from "./admin-table";
import { ExactCurrency } from "./currency";
import { DataTable } from "./data-table";
import { Loading } from "./loading";
import { currentLocation, navigate, restoration, saveRestoration, useRestoreView } from "./navigation";
import { MarketSelect } from "./research";
import { useCompactLayout } from "./responsive";
import type { Market } from "./types";
import { bases, basisDescriptions, tierLabel } from "./waylaid-crates-data";
import {
  compareWrits, maxConfirmedRecipes, maxRecipeSkill, methods, rewardSourceLabel, writColumns, writQueryKey, writRequest, writSortValue,
  writStatus, writUrl, writView, type Profession, type WritResults, type WritRow, type WritSort, type WritView,
} from "./crafting-writs-data";
import { DeliveryItems, WritAttribution, WritDetails, WritItemLink } from "./crafting-writs-details";
import "./waylaid-crates.css";
import "./crafting-writs.css";

const priceColumns = Object.keys(writColumns) as WritSort[];
const noProfessions: Profession[] = [];
const currentBasisDescription = "Uses the latest observed buyouts. Ranked costs require enough stock at the minimum, with whole auction stacks charged in full.";
function detailsLabel(row: WritRow, expanded: boolean) {
  return `${expanded ? "Hide" : "Show"} details for ${row.item.name}`;
}

function WritIdentity({ row, market }: { row: WritRow; market: number }) {
  const suffix = row.item.name.replace(/^(?:Craftsman[’']s|Crafting) Writ:\s+/, "");
  return <div>
    <WritItemLink item={row.item} market={market} id={`writ-item-${row.item.item_id}`}
      displayName={suffix === row.item.name ? undefined : suffix}/>
    {row.tier && <small className="muted writ-row-note">{tierLabel(row.tier)}</small>}
  </div>;
}

function WritProfession({ row, professions }: { row: WritRow; professions: Profession[] }) {
  const recipes = row.craft.recipes.length ? row.craft.recipes : row.craft.recipe_options;
  const skills = [...new Set(recipes.flatMap(recipe => recipe.skill === null ? [] : [recipe.skill]))].sort((a, b) => a - b);
  return <div>
    {professions.find(profession => profession.slug === row.profession)?.label ?? (row.profession ? tierLabel(row.profession) : "Unknown")}
    {skills.length > 0 && <small className="muted writ-row-note">Recipe skill {skills.join(", ")}</small>}
    {!skills.length && row.profession && <small className="muted writ-row-note">Recipe skill unknown</small>}
  </div>;
}

function WritMethodValue({ row }: { row: WritRow }) {
  const method = row.selected_method ?? row.display_method;
  const route = method ? row[method] : null;
  const reason = route?.reasons[0] ?? row.reasons[0];
  return <div>
    {method ? methods[method] : "Unavailable"}
    {!row.selected_method && reason && <small className="waylaid-estimate">{writStatus(reason)}</small>}
    {!row.selected_method && !reason && <small className="waylaid-estimate">Eligibility unverified</small>}
  </div>;
}

function WritValue({ row, field, owned }: { row: WritRow; field: WritSort; owned: boolean }) {
  if (field === "reputation") {
    return row.reputation === null ? <span className="muted">{rewardSourceLabel(row.reward_source)}</span> : <>
      {row.reputation.toLocaleString()}
      {row.faction && <small className="muted writ-row-note">{row.faction.name}</small>}
    </>;
  }
  if (field === "purchase" && owned) return <span className="muted">Owned</span>;
  const value = writSortValue(row, field);
  const valuation = (field === "total" && row.total_cost_exact === null) || (field === "completion" && row.completion_cost_exact === null);
  return <>
    <ExactCurrency exact={value}/>
    {value && valuation && <small className="waylaid-estimate">Unit valuation</small>}
  </>;
}

function WritSummary({ data, rows }: { data: WritResults; rows: WritRow[] }) {
  const ranked = rows.filter(row => writSortValue(row, "rate") !== null).sort((a, b) => compareWrits(a, b, "rate"));
  const best = ranked[0];
  return <div className="waylaid-metrics">
    <article>
      <span>Lowest cost / reputation</span>
      <strong><ExactCurrency exact={best?.cost_per_reputation}/></strong>
      <small>{best?.item.name ?? "No eligible writ with a priced reward"}</small>
    </article>
    <article>
      <span>Writs ranked by cost / reputation</span>
      <strong>{ranked.length.toLocaleString()} <small>of {rows.length.toLocaleString()}</small></strong>
      <small>In the current view</small>
    </article>
    <article>
      <span>Market observation</span>
      <strong>{tierLabel(data.pricing.freshness)}</strong>
      <small><LocalTime value={data.pricing.observed_at}/></small>
    </article>
  </div>;
}

export function CraftingWrits({ markets, market, setMarket, marketStatus, searchParams }: {
  markets: Market[];
  market: number;
  setMarket: (id: number) => void;
  marketStatus: "loading" | "unavailable" | "available";
  searchParams: string;
}) {
  const view = writView(searchParams, market);
  const [draftSearch, setDraftSearch] = useState(view.query);
  const [draftSkill, setDraftSkill] = useState(String(view.maxSkill ?? ""));
  const [expanded, setExpanded] = useState<Record<number, boolean>>(() => restoration()?.expanded ?? {});
  const compact = useCompactLayout();
  const active = markets.find(row => row.id === view.market);
  const request = writRequest(view);
  const result = useQuery({
    queryKey: [...writQueryKey, request],
    queryFn: ({ signal }) => api<WritResults>(request, "GET", undefined, signal),
    enabled: !!active,
    placeholderData: (prior, query) => {
      const previous = query?.queryKey.at(-1);
      return typeof previous === "string" && new URLSearchParams(previous.split("?")[1]).get("market_id") === String(view.market)
        ? keepPreviousData(prior) : undefined;
    },
    refetchInterval: 60_000,
    retry: false,
  });
  const data = active ? result.data : undefined;
  useRestoreView(Boolean(data), searchParams);
  useEffect(() => setDraftSearch(view.query), [view.query]);
  useEffect(() => setDraftSkill(String(view.maxSkill ?? "")), [view.maxSkill]);
  useEffect(() => {
    const canonical = writUrl(writView(searchParams, market));
    if (active && location.pathname === "/crafting-writs" && currentLocation() !== canonical) navigate(canonical, true);
  }, [active, searchParams, market]);

  function update(changes: Partial<WritView>) {
    navigate(writUrl({ ...view, ...changes }), true);
  }
  function toggle(row: WritRow) {
    const id = row.item.item_id;
    const next = { ...expanded, [id]: !expanded[id] };
    setExpanded(next);
    saveRestoration({ expanded: next });
  }
  function toggleRecipe(id: number) {
    const confirmedRecipes = view.confirmedRecipes.includes(id) ? view.confirmedRecipes.filter(recipe => recipe !== id)
      : [...view.confirmedRecipes, id].sort((a, b) => a - b).slice(0, maxConfirmedRecipes);
    update({ confirmedRecipes });
  }
  function sort(column: WritSort) {
    update({ sort: column, direction: view.sort === column && view.direction === "asc" ? "desc" : "asc" });
  }

  const query = view.query.toLowerCase();
  const rows = data?.rows ?? [];
  const professions = data?.professions ?? noProfessions;
  const filtered = rows.filter(row => {
    const items = [row.item, ...row.objectives.map(objective => objective.item)];
    return (!view.profession || view.profession === row.profession) &&
      (!query || items.some(item => item.name.toLowerCase().includes(query) || String(item.item_id) === query));
  }).sort((a, b) => compareWrits(a, b, view.sort, view.direction === "desc"));

  const columns = useMemo<ColumnDef<WritRow>[]>(() => [
    { id: "writ", header: "Writ", enableSorting: false, meta: { rowHeader: true },
      cell: ({ row }) => <WritIdentity row={row.original} market={view.market}/> },
    { id: "profession", header: "Profession", enableSorting: false,
      cell: ({ row }) => <WritProfession row={row.original} professions={professions}/> },
    { id: "delivery", header: "Delivery", enableSorting: false,
      cell: ({ row }) => <DeliveryItems row={row.original} market={view.market} context="delivery"/> },
    { id: "method", header: "Method", enableSorting: false,
      cell: ({ row }) => <WritMethodValue row={row.original}/> },
    ...priceColumns.map<ColumnDef<WritRow>>(field => ({
      id: field, header: writColumns[field], sortDescFirst: false, accessorFn: row => writSortValue(row, field),
      meta: { numeric: true }, cell: ({ row }) => <WritValue row={row.original} field={field} owned={view.owned}/>,
    })),
  ], [professions, view.market, view.owned]);
  const renderDetails = (row: WritRow) => <WritDetails row={row} market={view.market} owned={view.owned} current={view.basis === "current"}
    confirmed={view.confirmedRecipes} canConfirm={view.confirmedRecipes.length < maxConfirmedRecipes} toggleRecipe={toggleRecipe}/>;

  return <div className="waylaid-page writ-page">
    <div className="waylaid-heading">
      <div><h1>Crafting Writs</h1><p>Compare the gold cost of earning reputation with crafting writs.</p></div>
      <button className="secondary" disabled={!active || result.isFetching} onClick={() => void result.refetch()}>Refresh prices</button>
    </div>
    <section className="panel waylaid-controls writ-controls" aria-label="Pricing options">
      <label>Profession<select aria-label="Profession" value={view.profession ?? ""} onChange={event => update({ profession: event.target.value || null })}>
        <option value="">All professions</option>
        {view.profession && !professions.some(profession => profession.slug === view.profession) &&
          <option value={view.profession}>{tierLabel(view.profession)}</option>}
        {professions.map(profession => <option key={profession.slug} value={profession.slug}>{profession.label}</option>)}
      </select></label>
      <MarketSelect markets={markets} market={view.market} setMarket={id => { setMarket(id); update({ market: id }); }}/>
      <label>Price basis<select value={view.basis} onChange={event => update({ basis: event.target.value as WritView["basis"] })}>
        {Object.entries(bases).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select></label>
      <label>Completion method<select value={view.method} onChange={event => update({ method: event.target.value as WritView["method"] })}>
        {Object.entries(methods).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select></label>
      <label className="checkbox"><input type="checkbox" checked={view.owned} onChange={event => update({ owned: event.target.checked })}/>
        I already own the writ
      </label>
      <p className="small muted waylaid-basis-note">{view.basis === "current" ? currentBasisDescription : basisDescriptions[view.basis]}</p>
    </section>
    {marketStatus === "loading" && <Loading label="Loading available markets…" skeleton/>}
    {marketStatus === "unavailable" && !active && <p className="notice error" role="alert">Markets could not be loaded.</p>}
    {marketStatus === "available" && !active && <p className="notice" role="alert">
      {markets.length ? "This market is unavailable. Choose an available market to compare writs." : "No market mappings are configured."}
    </p>}
    {active && result.isPending && <Loading label="Loading Crafting Writs…" skeleton/>}
    {result.error && <p className="notice error" role="alert">
      {data ? "Refresh failed. Showing the last loaded estimates." : "Crafting Writs could not be loaded."}
      {" "}{result.error.message} <button type="button" onClick={() => void result.refetch()}>Retry estimates</button>
    </p>}
    {data && <>
      {view.basis === "regional" && <p className="notice">This market has no regional reference. Choose another price basis to see available estimates.</p>}
      {data.pricing.synthetic && <p className="notice warning">Synthetic fixture data · illustrative prices and availability.</p>}
      {data.catalogue.stale && <p className="notice warning">Catalogue data is stale. Showing the last verified catalogue.</p>}
      {data.pricing.freshness === "stale" && <p className="notice warning">Market observations are stale. Prices and stock may have changed.</p>}
      <div className="waylaid-source-line">
        <WritAttribution catalogue={data.catalogue} items={rows.flatMap(row => [
          row.item, ...row.objectives.map(objective => objective.item),
          ...[...row.craft.materials, ...row.buy.materials, ...row.craft.basket, ...row.buy.basket].map(quote => quote.item),
        ])}/>
        {data.catalogue.writ_count > 0 && <small>
          {data.catalogue.writ_count.toLocaleString()} catalogued
          {data.catalogue.incomplete_count > 0 && <> · {data.catalogue.incomplete_count.toLocaleString()} with no verified route</>}
          {data.catalogue.partial_count > 0 && <> · {data.catalogue.partial_count.toLocaleString()} with unverified details</>}
        </small>}
        {data.catalogue.refreshed_at && <small>Catalogue refreshed <LocalTime value={data.catalogue.refreshed_at}/></small>}
      </div>
      {!result.isPlaceholderData && <WritSummary data={data} rows={filtered}/>}
      <section className="panel waylaid-results writ-results" aria-label="Writ comparison" aria-busy={result.isFetching}>
        <div className="panel-heading">
          <div><h2>Writ comparison</h2><p className="small muted">Confirm recipes you can use in writ details. Writs with unknown rewards show any available costs.</p></div>
          <span className="small muted" role="status">
            {result.isPlaceholderData ? "Updating selection · previous estimates" : `${filtered.length.toLocaleString()} writs`}
          </span>
        </div>
        <form className="waylaid-filters writ-filters" onSubmit={event => {
          event.preventDefault();
          update({ query: draftSearch.trim(), maxSkill: draftSkill === "" ? null : Number(draftSkill) });
        }}>
          <label>Search writs<input type="search" value={draftSearch} maxLength={64} placeholder="Name or item ID"
            onChange={event => setDraftSearch(event.target.value)}/></label>
          <label>Maximum recipe skill<input type="number" min={1} max={maxRecipeSkill} step={1} inputMode="numeric"
            value={draftSkill} placeholder="Any" onChange={event => setDraftSkill(event.target.value)}/></label>
          <button className="secondary">Apply filters</button>
          {view.confirmedRecipes.length > 0 && <button className="secondary" type="button" onClick={() => update({ confirmedRecipes: [] })}>
            Reset confirmed recipes ({view.confirmedRecipes.length})
          </button>}
        </form>
        {!filtered.length && <p className="empty">{data.catalogue.writ_count ? "No writs match these filters." : "No writ catalogue is available yet."}</p>}
        {filtered.length > 0 && (compact ? <>
          <div className="mobile-sort waylaid-mobile-sort">
            <label>Sort writs<select value={view.sort} onChange={event => update({ sort: event.target.value as WritSort, direction: "asc" })}>
              {priceColumns.map(field => <option key={field} value={field}>{writColumns[field]}</option>)}
            </select></label>
            <button className="secondary" aria-label={`Sort direction: ${view.direction === "asc" ? "ascending" : "descending"}`}
              onClick={() => sort(view.sort)}>{view.direction === "asc" ? "Ascending ↑" : "Descending ↓"}</button>
          </div>
          <div className="waylaid-cards">
            {filtered.map(row => {
              const id = row.item.item_id;
              const open = !!expanded[id];
              return <article className="waylaid-card" key={id}>
                <WritIdentity row={row} market={view.market}/>
                <dl className="waylaid-card-prices">
                  <div><dt>Profession</dt><dd><WritProfession row={row} professions={professions}/></dd></div>
                  <div><dt>Method</dt><dd><WritMethodValue row={row}/></dd></div>
                  {priceColumns.map(field => <div key={field}><dt>{writColumns[field]}</dt>
                    <dd><WritValue row={row} field={field} owned={view.owned}/></dd></div>)}
                  <div className="waylaid-card-materials"><dt>Delivery</dt><dd><DeliveryItems row={row} market={view.market} context="delivery"/></dd></div>
                </dl>
                <button className="secondary waylaid-details-toggle" aria-expanded={open} aria-controls={`writ-details-${id}`}
                  aria-label={detailsLabel(row, open)} onClick={() => toggle(row)}>{open ? "Hide details" : "Details"}</button>
                <div id={`writ-details-${id}`} hidden={!open}>{open && renderDetails(row)}</div>
              </article>;
            })}
          </div>
        </> : <DataTable<WritRow>
          label="Crafting Writs estimates" data={filtered} columns={columns} compact
          getRowId={row => String(row.item.item_id)} renderDetails={renderDetails}
          detailsControl={{ isExpanded: row => !!expanded[row.item.item_id], toggle, label: detailsLabel }}
          server={{
            rowCount: filtered.length,
            pagination: { pageIndex: 0, pageSize: filtered.length },
            onPaginationChange: () => {},
            sorting: [{ id: view.sort, desc: view.direction === "desc" }],
            onSortingChange: change => {
              const before = [{ id: view.sort, desc: view.direction === "desc" }];
              const next = (typeof change === "function" ? change(before) : change).at(-1);
              if (next) update({ sort: next.id as WritSort, direction: next.desc ? "desc" : "asc" });
              else sort(view.sort);
            },
          }}
        />)}
      </section>
    </>}
  </div>;
}
