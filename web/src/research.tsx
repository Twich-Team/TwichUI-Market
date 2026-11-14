import { useQuery } from "@tanstack/react-query";
import { useLayoutEffect, useState, DependencyList } from "react";
import { api, money, when } from "./api";
import { PriceHistory, SupplyDistribution } from "./charts";
import { ItemCatalogue } from "./catalogue";
import { ItemInfo } from "./item-components";
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
            {row.label} · #{row.id}
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
    [range, setRange] = useState(14),
    [comparison, setComparison] = useState(0);
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
  const compared = useLoad(
    "comparison",
    () =>
      comparison && selected
        ? api<Detail>(
            `/markets/${comparison}/items/${selected.item_id}/${selected.variant_key}`,
          )
        : Promise.resolve(null),
    [comparison, selected?.item_id, selected?.variant_key],
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
            <ItemInfo market={market} item={detail.data} prices={value} />
            <div>
              <div className="eyebrow">ITEM #{detail.data.item_id}</div>
              <h2>{detail.data.name}</h2>
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
              <strong>{money(value.lowest_buyout)}</strong>
              <small>Current asking price</small>
            </article>
            <article>
              <label>RECENT PRICE</label>
              <strong>{money(value.recent_price)}</strong>
              <small>Quantity-weighted listings</small>
            </article>
            <article>
              <label>14-DAY MARKET VALUE</label>
              <strong>{money(value.market_value)}</strong>
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
                60-day historical value: {money(value.historical_value)} ·{" "}
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
          <section className="panel">
            <div className="panel-heading">
              <h3>Compare markets</h3>
              <select
                aria-label="Comparison market"
                value={comparison}
                onChange={(event) => setComparison(Number(event.target.value))}
              >
                <option value={0}>Choose a second market</option>
                {markets
                  .filter((row) => row.id !== market)
                  .map((row) => (
                    <option key={row.id} value={row.id}>
                      {row.label}
                    </option>
                  ))}
              </select>
            </div>
            {compared.loading && (
              <p className="panel-note">Loading comparison…</p>
            )}
            {compared.error && (
              <p className="panel-note error" role="alert">
                {compared.error}
              </p>
            )}
            {compared.data && (
              <div className="comparison">
                <span>
                  {current?.label}: <b>{money(value.recent_price)}</b>
                </span>
                <span>
                  {compared.data.market.label}:{" "}
                  <b>{money(compared.data.valuation.recent_price)}</b>
                </span>
                <span>Same item variant · source types remain separate</span>
              </div>
            )}
          </section>
          <section className="panel table-panel" tabIndex={0} role="region" aria-label="Scrollable current listings">
            <div className="panel-heading">
              <h3>Current listings</h3>
              <span className="muted">
                {detail.data.listings_truncated
                  ? "First 200 listings · partial view"
                  : "All observed listings"}
              </span>
            </div>
            <table>
              <thead>
                <tr>
                  <th>AUCTION</th>
                  <th>QUANTITY</th>
                  <th>STACK BUYOUT</th>
                  <th>UNIT PRICE</th>
                  <th>TIME LEFT</th>
                </tr>
              </thead>
              <tbody>
                {detail.data.listings.map((row) => (
                  <tr key={row.auction_id}>
                    <td>{row.auction_id}</td>
                    <td>{row.quantity}</td>
                    <td>
                      {row.buyout === null
                        ? "Bid only / commodity"
                        : money(row.buyout)}
                    </td>
                    <td>
                      {row.unit_price === null
                        ? "Stack total shown"
                        : money(row.unit_price)}
                    </td>
                    <td>{row.time_left || "Unknown"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!detail.data.listings.length && (
              <p className="empty">No current listings for this variant.</p>
            )}
          </section>
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
