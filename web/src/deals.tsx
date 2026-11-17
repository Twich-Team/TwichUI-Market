import { Loading } from "./loading";
import { InfoTooltip, metricExplanations } from "./info-tooltip";
import {dealState,dealUrl,navigate,itemUrl,followItem,restoration,saveRestoration,useRestoreView} from "./navigation";
import { Currency } from "./currency";
import { useEffect, useState } from "react";
import { ItemInfo } from "./item-components";
import { api } from "./api";
import { Freshness, MarketSelect, useLoad } from "./research";
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
interface Results {
  history_coverage: {
    observed_days: number;
    required_days: number;
    status: string;
    basis: string;
  };
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
  searchParams,
}: {
  markets: Market[];
  market: number;
  setMarket: (id: number) => void;
  searchParams:string;
}) {
  const preferences=usePreferences();
  const saved=preferences.values;
  const browsing=dealState(searchParams,{market,mode:saved.deal_mode,filters:{change:saved.deal_change,spend:saved.deal_spend_gold,coverage:saved.deal_coverage,confidence:saved.deal_confidence,direction:saved.deal_direction}});
  market=browsing.market;const mode=browsing.mode;
  const restored=()=>restoration()?.dealDraft??browsing.filters;
  const [filters,setFilters]=useState<Filters>(restored);
  useEffect(()=>{setFilters(restored());},[searchParams]);
  function apply(next=filters,nextMode=mode,nextMarket=market,draft=next){saveRestoration({dealDraft:draft});navigate(dealUrl({market:nextMarket,mode:nextMode,filters:next}),true);}
  function changeFilters(changes:Partial<Filters>) {
    setFilters(previous=>({...previous,...changes}));
    const update:PreferenceChanges={};
    if(changes.change!==undefined&&Number.isInteger(changes.change)&&changes.change>=1&&changes.change<=1000)update.deal_change=changes.change;
    if(changes.spend!==undefined&&Number.isFinite(changes.spend)&&changes.spend>=0.01&&changes.spend<=100000000)update.deal_spend_gold=changes.spend;
    if(changes.coverage!==undefined&&Number.isInteger(changes.coverage)&&changes.coverage>=1&&changes.coverage<=15)update.deal_coverage=changes.coverage;
    if(changes.confidence!==undefined)update.deal_confidence=changes.confidence as Preferences['deal_confidence'];
    if(changes.direction!==undefined)update.deal_direction=changes.direction as Preferences['deal_direction'];
    if(Object.keys(update).length)preferences.update(update);
  }
  const submitted=browsing.filters;

  const result = useLoad(
    "opportunities",
    (signal) => {
      if (!market) return Promise.resolve(null);
      const shared = `minimum_coverage=${submitted.coverage}&minimum_confidence=${submitted.confidence}`;
      const path =
        mode === "listings"
          ? `/deals?minimum_discount=${submitted.change}&maximum_spend=${Math.round(submitted.spend * 10000)}&${shared}`
          : `/signals?kind=${mode}&minimum_change=${submitted.change}&direction=${submitted.direction}&${shared}`;
      return api<Results>(`/markets/${market}${path}`,"GET",undefined,signal);
    },
    [market, mode, submitted],
    true,
  );
  useRestoreView(!result.loading,searchParams);
  useEffect(()=>{if(markets.length&&location.pathname==='/deals'&&!searchParams)apply(browsing.filters);},[markets.length]);
  const deals = result.data?.deals || [],
    signals = result.data?.signals || [];
  const count = mode === "listings" ? deals.length : signals.length;
  function chooseMode(next: Mode) {
    const maximum = next === "listings" ? 99 : 1000;
    const days = next === "listings" ? 15 : 14;
    preferences.update({deal_mode:next,deal_change:Math.max(1,Math.min(filters.change,maximum)),deal_coverage:Math.max(1,Math.min(filters.coverage,days))});
    setFilters((previous) => ({
      ...previous,
      change: Math.max(1,Math.min(previous.change, maximum)),
      coverage: Math.max(1,Math.min(previous.coverage, days)),
    }));
    apply({...browsing.filters,change:Math.max(1,Math.min(browsing.filters.change,maximum)),coverage:Math.max(1,Math.min(browsing.filters.coverage,days))},next,market,{...filters,change:Math.max(1,Math.min(filters.change,maximum)),coverage:Math.max(1,Math.min(filters.coverage,days))});

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
          saveRestoration({dealDraft:filters});apply({...filters,change:mode==='listings'?Math.min(99,filters.change):filters.change});
        }}
      >
        <MarketSelect markets={markets} market={market} setMarket={id=>{setMarket(id);apply(browsing.filters,mode,id,filters);}} />
        <label>
          {mode === "listings" ? "Minimum discount (%)" : "Minimum change (%)"}
          <input
            type="number"
            min="1"
            max={mode === "listings" ? 99 : 1000}
            value={filters.change}
            onChange={(event) =>
              changeFilters({ change: Number(event.target.value) })
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
                changeFilters({ spend: Number(event.target.value) })
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
                changeFilters({ direction: event.target.value })
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
              changeFilters({ coverage: Number(event.target.value) })
            }
            required
          />
        </label>
        <label>
          Evidence <InfoTooltip label="market evidence">{metricExplanations.evidence}</InfoTooltip>
          <select
            aria-label="Evidence" value={filters.confidence}
            onChange={(event) =>
              changeFilters({ confidence: event.target.value })
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
      {(result.loading || result.refreshing) && (
        <Loading label="Evaluating observed market data…" skeleton={!result.data}/>
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
          {result.data.history_coverage?.status === "insufficient" && (
            <p className="notice" role="status">
              Still building market history:{" "}
              {result.data.history_coverage.observed_days} observed{" "}
              {result.data.history_coverage.basis === "prior_utc_days"
                ? "prior UTC days"
                : "UTC days"}
              ; these filters require{" "}
              {result.data.history_coverage.required_days}. Opportunities need
              more history. Collection will continue; missing days are never
              filled with invented prices.
            </p>
          )}
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
                  <h2>
                    <ItemInfo
                      market={market}
                      item={{
                        item_id: deal.item_id,
                        name: deal.name || `Item #${deal.item_id}`,
                        quality: deal.quality,
                        icon_url: deal.icon_url,
                        variant_key: deal.variant_key,
                      }}
                      prices={{
                        market_value: deal.market_value,
                      }}
                      label
                    />
                  </h2>
                  <strong className="discount">
                    −{deal.discount_percent}%
                  </strong>
                </div>
                <div className="deal-prices">
                  <div>
                    <label>TOTAL BUYOUT</label>
                    <strong>
                      <Currency value={deal.total_buyout} />
                    </strong>
                  </div>
                  <div>
                    <label>REFERENCE / UNIT</label>
                    <strong>
                      <Currency value={deal.market_value} />
                    </strong>
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
                <a id={`deal-${deal.auction_id}`} className="secondary" href={itemUrl(market,deal.item_id,deal.variant_key)} onClick={event=>{saveRestoration({dealDraft:filters});followItem(event);}}>
                  Inspect item ↗
                </a>
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
                  <h2>
                    <ItemInfo
                      market={market}
                      item={{
                        item_id: signal.item_id,
                        name: signal.name || `Item #${signal.item_id}`,
                        quality: signal.quality,
                        icon_url: signal.icon_url,
                        variant_key: signal.variant_key,
                      }}
                      prices={{
                        recent_price: signal.current_price,
                        supply: signal.current_supply,
                      }}
                      label
                    />
                  </h2>
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
                        <strong>
                          <Currency value={signal.current_price} />
                        </strong>
                      </div>
                      <div>
                        <label>PRIOR REFERENCE / UNIT</label>
                        <strong>
                          <Currency value={signal.reference_price} />
                        </strong>
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
                <a id={`signal-${signal.item_id}-${signal.variant_key}`} className="secondary" href={itemUrl(market,signal.item_id,signal.variant_key)} onClick={event=>{saveRestoration({dealDraft:filters});followItem(event);}}>
                  Inspect item ↗
                </a>
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
