import { Currency } from "./currency";
import { CurrentListings } from "./listings";
import { variantLabel } from "./variant-label";
import { useQuery } from "@tanstack/react-query";
import { useLayoutEffect, useState, DependencyList } from "react";
import { api, when } from "./api";
import { PriceHistory, SupplyDistribution } from "./charts";
import { ItemCatalogue } from "./catalogue";
import { ItemInfo, ItemAttribution } from "./item-components";
import { Detail, Item, Market } from "./types";

export function useLoad<T>(
  key: string,
  load: (signal?: AbortSignal) => Promise<T>,
  dependencies: DependencyList,
) {
  const query = useQuery({
    queryKey: ["private", key, ...dependencies],
    queryFn: ({ signal }) => load(signal),
    refetchInterval: 60_000,
  });
  return {
    data: query.data,
    error: query.error?.message || "",
    loading: query.isPending,
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
    <label>
      Market
      <select
        value={market}
        onChange={(event) => setMarket(Number(event.target.value))}
        disabled={!markets.length}
      >
        {!markets.length && <option value={0}>No markets configured</option>}
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
function Loading({ error, loading }: { error: string; loading: boolean }) {
  return (
    <>
      {loading && (
        <p role="status" className="muted">
          Loading your research…
        </p>
      )}
      {error && (
        <p role="alert" className="notice error">
          {error}
        </p>
      )}
    </>
  );
}

export function Explorer({
  markets,
  market,
  setMarket,
  focus,
}: {
  markets: Market[];
  market: number;
  setMarket: (id: number) => void;
  focus?: { item_id: number; variant_key: string } | null;
}) {
  const [query, setQuery] = useState(focus?.item_id.toString() || ""),
    [search, setSearch] = useState(focus?.item_id.toString() || ""),
    [selected, setSelected] = useState<Item | null>(null),
    [range, setRange] = useState(14);
  const [catalogueSummary, setCatalogueSummary] = useState({
    synthetic: false,
    empty: false,
  });
  useLayoutEffect(() => {
    setSelected(
      focus
        ? {
            ...focus,
            name: `Item #${focus.item_id}`,
            name_verified: false,
            variant: null,
          }
        : null,
    );
  }, [market, focus?.item_id, focus?.variant_key]);
  const detail = useLoad(
    "item-detail",
    () =>
      market && selected
        ? api<Detail>(
            `/markets/${market}/items/${selected.item_id}/${selected.variant_key}`,
          )
        : Promise.resolve(null),
    [market, selected?.item_id, selected?.variant_key],
  );
  const current = markets.find((row) => row.id === market),
    value = detail.data?.valuation;
  const cutoff = new Date(Date.now() - range * 86400000)
    .toISOString()
    .slice(0, 10);
  return (
    <>
      <div className="eyebrow">KNOW YOUR MARKET</div>
      <h1>Market Explorer</h1>
      <p className="intro">
        Understand current listings, long-term references, and the evidence
        behind them.
      </p>
      <form
        className="toolbar"
        onSubmit={(event) => {
          event.preventDefault();
          setQuery(search);
        }}
      >
        <label className="grow">
          Search items
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Item name or ID, e.g. Arcane Crystal"
            maxLength={64}
          />
        </label>
        <MarketSelect {...{ markets, market, setMarket }} />
        <button className="primary" disabled={!market}>
          Search
        </button>
      </form>
      {current && <Freshness market={current} />}
      <Loading error={detail.error} loading={detail.loading} />
      {!market && (
        <div className="empty panel">
          No market mappings are configured. An administrator can add a mapping
          under Administration.
        </div>
      )}
      {catalogueSummary.synthetic && (
        <p className="notice warning">
          Synthetic fixture data · not live Auction House observations.
        </p>
      )}
      {!!market && (
        <ItemCatalogue
          key={market}
          market={market}
          query={query}
          focus={focus}
          onSelect={setSelected}
          onSummary={setCatalogueSummary}
        />
      )}
      {detail.data && value && (
        <>
          <div className="item-heading">
            <ItemInfo
              eager
              market={market}
              item={{
                ...detail.data,
                icon_url: selected?.icon_url,
                quality: selected?.quality,
              }}
              prices={value}
            />
            <div>
              <div className="eyebrow">ITEM #{detail.data.item_id}</div>
              <h2
                className={`quality-text-${selected?.quality?.toLowerCase() || "unknown"}`}
              >
                {detail.data.name}
              </h2>
              <ItemAttribution
                item={{
                  ...detail.data,
                  metadata_attribution: selected?.metadata_attribution,
                }}
              />
              <small className="muted">{variantLabel(selected?.variant)}</small>
              <br />
              <small className="muted">
                {detail.data.name_verified
                  ? "Verified item metadata"
                  : "Item name is unverified · variant kept separate"}
              </small>
            </div>
          </div>
          <div className="stats">
            <article>
              <label>LOWEST BUYOUT / UNIT</label>
              <strong>
                <Currency value={value.lowest_buyout} />
              </strong>
              <small>Current asking price</small>
            </article>
            <article>
              <label>RECENT PRICE</label>
              <strong>
                <Currency value={value.recent_price} />
              </strong>
              <small>Quantity-weighted listings</small>
            </article>
            <article>
              <label>14-DAY MARKET VALUE</label>
              <strong>
                <Currency value={value.market_value} />
              </strong>
              <small>{value.market_coverage_days} observed UTC days</small>
            </article>
            <article>
              <label>AVAILABLE SUPPLY</label>
              <strong>{value.supply.toLocaleString()} units</strong>
              <small>
                {value.listing_count.toLocaleString()} listings ·{" "}
                {value.priced_supply.toLocaleString()} priced units
              </small>
            </article>
          </div>
          <div className="two-col">
            <section className="panel">
              <div className="panel-heading">
                <h3>Price history</h3>
                <div className="segmented">
                  {[7, 14, 60, 365, 3650].map((days) => (
                    <button
                      key={days}
                      className={range === days ? "selected" : ""}
                      onClick={() => setRange(days)}
                    >
                      {days === 3650 ? "10Y" : `${days}D`}
                    </button>
                  ))}
                </div>
              </div>
              <PriceHistory
                key={`${market}:${selected!.item_id}:${selected!.variant_key}:${range}`}
                market={market}
                item={selected!.item_id}
                variant={selected!.variant_key}
                days={range}
              />
              <p className="panel-note">
                60-day historical value:{" "}
                <Currency value={value.historical_value} /> ·{" "}
                {value.coverage_days} observed days
              </p>
            </section>
            <section className="panel">
              <div className="panel-heading">
                <h3>Supply by price</h3>
              </div>
              <SupplyDistribution
                market={market}
                item={selected!.item_id}
                variant={selected!.variant_key}
              />
            </section>
          </div>
          <CurrentListings
            key={`${market}:${selected!.item_id}:${selected!.variant_key}`}
            market={market}
            item={selected!.item_id}
            variant={selected!.variant_key}
          />
          <p className="notice">
            Reference algorithm: {value.algorithm}. Workshop compatibility
            remains unverified. Missing days are not filled in, and disappearing
            listings do not establish sales.
          </p>
        </>
      )}
    </>
  );
}
