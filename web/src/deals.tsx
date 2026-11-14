import { useState } from "react";
import { api, money } from "./api";
import { Freshness, MarketSelect, useLoad } from "./research";
import { Deal, Market, Signal } from "./types";

type Mode = "listings" | "supply" | "price";
type Target = { item_id: number; variant_key: string };
interface Filters {
  change: number;
  spend: number;
  coverage: number;
  confidence: string;
  direction: string;
}
interface Results {
  deals?: Deal[];
  signals?: Signal[];
  synthetic: boolean;
  candidates_truncated: boolean;
  market: Market;
}

export function Deals({
  markets,
  market,
  setMarket,
  inspect,
}: {
  markets: Market[];
  market: number;
  setMarket: (id: number) => void;
  inspect: (target: Target) => void;
}) {
  const [mode, setMode] = useState<Mode>("listings");
  const [filters, setFilters] = useState<Filters>({
    change: 15,
    spend: 500,
    coverage: 3,
    confidence: "limited",
    direction: "any",
  });
  const [submitted, setSubmitted] = useState(filters);
  const result = useLoad(() => {
    if (!market) return Promise.resolve(null);
    const shared = `minimum_coverage=${submitted.coverage}&minimum_confidence=${submitted.confidence}`;
    const path =
      mode === "listings"
        ? `/deals?minimum_discount=${submitted.change}&maximum_spend=${Math.round(submitted.spend * 10000)}&${shared}`
        : `/signals?kind=${mode}&minimum_change=${submitted.change}&direction=${submitted.direction}&${shared}`;
    return api<Results>(`/markets/${market}${path}`);
  }, [market, mode, submitted]);
  const deals = result.data?.deals || [],
    signals = result.data?.signals || [];
  const count = mode === "listings" ? deals.length : signals.length;
  function chooseMode(next: Mode) {
    const maximum = next === "listings" ? 99 : 1000;
    const days = next === "listings" ? 15 : 14;
    setMode(next);
    setFilters((previous) => ({
      ...previous,
      change: Math.min(previous.change, maximum),
      coverage: Math.min(previous.coverage, days),
    }));
    setSubmitted((previous) => ({
      ...previous,
      change: Math.min(previous.change, maximum),
      coverage: Math.min(previous.coverage, days),
    }));
  }
  return (
    <>
      <div className="eyebrow">FIND YOUR NEXT OPPORTUNITY</div>
      <h1>Deal Finder</h1>
      <p className="intro">
        Promising listings, supply changes, and price moves—with the evidence
        behind each.
      </p>
      <div className="admin-tabs" role="tablist" aria-label="Opportunity type">
        {(
          [
            ["listings", "Below reference"],
            ["supply", "Supply changes"],
            ["price", "Price changes"],
          ] as const
        ).map(([key, title]) => (
          <button
            key={key}
            role="tab"
            aria-selected={mode === key}
            className={mode === key ? "selected" : ""}
            onClick={() => chooseMode(key)}
          >
            {title}
          </button>
        ))}
      </div>
      <form
        className="toolbar"
        onSubmit={(event) => {
          event.preventDefault();
          setSubmitted({
            ...filters,
            change:
              mode === "listings"
                ? Math.min(99, filters.change)
                : filters.change,
          });
        }}
      >
        <MarketSelect {...{ markets, market, setMarket }} />
        <label>
          {mode === "listings" ? "Minimum discount (%)" : "Minimum change (%)"}
          <input
            type="number"
            min="1"
            max={mode === "listings" ? 99 : 1000}
            value={filters.change}
            onChange={(event) =>
              setFilters({ ...filters, change: Number(event.target.value) })
            }
            required
          />
        </label>
        {mode === "listings" ? (
          <label>
            Maximum spend (gold)
            <input
              type="number"
              min="0.01"
              max="100000000"
              step="0.01"
              value={filters.spend}
              onChange={(event) =>
                setFilters({ ...filters, spend: Number(event.target.value) })
              }
              required
            />
          </label>
        ) : (
          <label>
            Direction
            <select
              value={filters.direction}
              onChange={(event) =>
                setFilters({ ...filters, direction: event.target.value })
              }
            >
              <option value="any">Both directions</option>
              <option value="increase">Increase only</option>
              <option value="decrease">Decrease only</option>
            </select>
          </label>
        )}
        <label>
          Minimum observed days
          <input
            type="number"
            min="1"
            max={mode === "listings" ? 15 : 14}
            value={filters.coverage}
            onChange={(event) =>
              setFilters({ ...filters, coverage: Number(event.target.value) })
            }
            required
          />
        </label>
        <label>
          Evidence
          <select
            value={filters.confidence}
            onChange={(event) =>
              setFilters({ ...filters, confidence: event.target.value })
            }
          >
            <option value="limited">All evidence levels</option>
            <option value="moderate">Moderate or stronger</option>
            <option value="strong">Strong only</option>
          </select>
        </label>
        <button className="primary" disabled={!market || result.loading}>
          Apply filters
        </button>
      </form>
      {result.loading && (
        <p className="muted" role="status">
          Evaluating observed market data…
        </p>
      )}
      {result.error && (
        <p className="notice error" role="alert">
          {result.error}
        </p>
      )}
      {!market && (
        <p className="empty panel">
          An administrator must configure a market before opportunities can be
          researched.
        </p>
      )}
      {result.data && (
        <>
          <Freshness market={result.data.market} />
          {result.data.synthetic && (
            <p className="notice warning">
              Synthetic opportunities for testing · no live Blizzard data.
            </p>
          )}
          <div className="panel-heading">
            <h3>
              {count} {count === 1 ? "opportunity" : "opportunities"}
            </h3>
            <span className="muted">
              {mode === "listings"
                ? "Sorted by discount · 14-day asking-price reference"
                : "Sorted by change · prior UTC days, excluding today"}
            </span>
          </div>
          {result.data.candidates_truncated && (
            <p className="notice">
              Showing the first 100 matching results. More matches exist.
            </p>
          )}
          <div className="deal-grid">
            {deals.map((deal) => (
              <article className="panel deal" key={deal.auction_id}>
                <div className="deal-top">
                  <span className="badge">BELOW REFERENCE</span>
                  <span>{deal.confidence} evidence</span>
                </div>
                <div className="item-heading">
                  <div className="item-icon">◇</div>
                  <h2>{deal.name || `Item #${deal.item_id}`}</h2>
                  <strong className="discount">
                    −{deal.discount_percent}%
                  </strong>
                </div>
                <div className="deal-prices">
                  <div>
                    <label>TOTAL BUYOUT</label>
                    <strong>{money(deal.total_buyout)}</strong>
                  </div>
                  <div>
                    <label>REFERENCE / UNIT</label>
                    <strong>{money(deal.market_value)}</strong>
                  </div>
                  <div>
                    <label>QUANTITY</label>
                    <strong>{deal.quantity}</strong>
                  </div>
                </div>
                <h4>Why it stands out</h4>
                <p>{deal.reason}</p>
                <ul className="cautions">
                  {deal.cautions.map((caution) => (
                    <li key={caution}>{caution}</li>
                  ))}
                </ul>
                <button className="secondary" onClick={() => inspect(deal)}>
                  Inspect item ↗
                </button>
              </article>
            ))}
            {signals.map((signal) => (
              <article
                className="panel deal"
                key={`${signal.item_id}:${signal.variant_key}`}
              >
                <div className="deal-top">
                  <span className="badge">
                    {signal.kind === "supply"
                      ? "SUPPLY CHANGE"
                      : "PRICE CHANGE"}
                  </span>
                  <span>{signal.confidence} evidence</span>
                </div>
                <div className="item-heading">
                  <div className="item-icon">◇</div>
                  <h2>{signal.name || `Item #${signal.item_id}`}</h2>
                  <strong className="discount">
                    {signal.change_percent > 0 ? "+" : ""}
                    {signal.change_percent}%
                  </strong>
                </div>
                <div className="deal-prices">
                  {signal.kind === "price" ? (
                    <>
                      <div>
                        <label>CURRENT / UNIT</label>
                        <strong>{money(signal.current_price)}</strong>
                      </div>
                      <div>
                        <label>PRIOR REFERENCE / UNIT</label>
                        <strong>{money(signal.reference_price)}</strong>
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <label>CURRENT SUPPLY</label>
                        <strong>
                          {signal.current_supply.toLocaleString()} units
                        </strong>
                      </div>
                      <div>
                        <label>PRIOR AVERAGE SUPPLY</label>
                        <strong>
                          {signal.reference_supply.toLocaleString()} units
                        </strong>
                      </div>
                    </>
                  )}
                </div>
                <h4>Why it stands out</h4>
                <p>{signal.reason}</p>
                <ul className="cautions">
                  {signal.cautions.map((caution) => (
                    <li key={caution}>{caution}</li>
                  ))}
                </ul>
                <button className="secondary" onClick={() => inspect(signal)}>
                  Inspect item ↗
                </button>
              </article>
            ))}
          </div>
          {count === 0 && (
            <p className="empty panel">
              {mode === "listings"
                ? "No listings match these filters with sufficient historical coverage."
                : "No changes match these filters with sufficient historical coverage."}{" "}
              Try a lower threshold or a broader evidence level.
            </p>
          )}
        </>
      )}
      <p className="notice">
        Evidence reflects coverage, source freshness, and verified mappings—not
        a probability of profit. Asking prices and supply changes do not
        establish completed sales. Fees, deposits and your time still matter.
      </p>
    </>
  );
}
