import { useState } from "react";
import { api, when } from "./api";
import { SourceAge } from "./admin-histories";
import { Status } from "./admin-table";
import { Loading } from "./loading";
import { DataTable } from "./data-table";
import { useLoad } from "./research";
import { Market } from "./types";
interface Options {
  regions: string[];
  rulesets: string[];
  factions: string[];
  choices: {
    region: string;
    ruleset: string;
    faction: string;
    available: boolean;
  }[];
  notice: string;
}
function Diagnostics({ market }: { market: Market }) {
  const [open, setOpen] = useState(false);
  const data = useLoad(
    `market-diagnostics-${market.id}`,
    () =>
      open
        ? api<Record<string, unknown>>(
            `/admin/markets/${market.id}/diagnostics`,
          )
        : Promise.resolve(null),
    [open],
  );
  return (
    <div className="admin-status-details">
      {market.feeds?.map(feed => <p key={feed.source_kind}>
        <strong>{feed.source_kind === 'commodities' ? 'Commodities' : 'Regular auctions'}: {feed.enabled ? feed.status.replaceAll("_"," ") : "Disabled"}</strong><br/>
        Last successful check: {when(feed.last_success)} · Listings: {feed.listing_count?.toLocaleString() ?? 'Unknown'} · Items: {feed.item_count?.toLocaleString() ?? 'Unknown'}<br/>
        Source updated: {feed.upstream_modified ?? 'Unknown'} · Failures: {feed.failures}
        {feed.last_error && <><br/>{feed.last_error}</>}
      </p>)}
    <details onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>Advanced market diagnostics</summary>
      <p>
        Region {market.region.toUpperCase()} · transport ruleset{" "}
        {market.ruleset_id} · upstream house {market.house_id} ·{" "}
        {market.source_kind}
      </p>
      {open && data.loading && <Loading label="Loading feed diagnostics…"/>}
      {open && data.error && <p role="alert">{data.error} <button onClick={data.refresh}>Retry</button></p>}
      <pre className="diagnostic-json">
        {open && data.data && JSON.stringify(data.data, null, 2)}
      </pre>
    </details>
    </div>
  );
}
export function MarketConfiguration({
  markets,
  readOnly,
  refreshMarkets,
  action,
}: {
  markets: Market[];
  readOnly: boolean;
  refreshMarkets: () => Promise<void>;
  action: (job: () => Promise<void>) => void;
}) {
  const options = useLoad(
    "market-options",
    () => api<Options>("/admin/market-options"),
    [],
  );
  const [region, setRegion] = useState("us"),
    [ruleset, setRuleset] = useState("Normal"),
    [faction, setFaction] = useState("Horde");
  const available = !!options.data?.choices.find(
    (c) =>
      c.region === region && c.ruleset === ruleset && c.faction === faction,
  )?.available;
  return (
    <>
      <section className="panel padded">
        <h2>Configured markets</h2>
        <p className="muted">{markets.filter(market=>market.enabled).length} of {markets.length} collecting.</p>
        <DataTable<Market>
          label="market schedules"
          compact
          emptyMessage="No markets are configured. Open Add a market to begin."
          data={markets}
          getRowId={(m) => String(m.id)}
          columns={[
            {
              accessorKey: "label",
              header: "Market",
              enableHiding: false,
            },
            {
              id: "status",
              header: "Collection",
              accessorFn: market => !market.enabled ? "Disabled" : market.failures || market.last_error ? "Check failed" : "Collecting",
              cell: ({getValue}) => <Status tone={getValue()==="Check failed"?"error":getValue()==="Collecting"?"success":"neutral"}>{String(getValue())}</Status>,
            },
            {
              accessorKey: "last_modified",
              header: "Source updated",
              cell: ({row}) => <SourceAge market={row.original}/>,
            },
            {
              accessorKey: "last_success",
              header: "Last successful check",
              cell: ({ row }) => when(row.original.last_success),
            },
            {
              accessorKey: "failures",
              header: "Failures",
              meta: { numeric: true },
            },
            {
              accessorKey: "interval_seconds",
              header: "Interval",
              cell: ({row}) => `${row.original.interval_seconds / 60} min`,
            },
          ]}
          renderDetails={market=><div className="admin-status-details">
            {market.last_error && <p role="status">{market.last_error}</p>}
            <Diagnostics market={market}/>
            <details><summary>Edit collection schedule</summary>
              {!market.player_identity_verified && !market.enabled && <p>This market must pass live identity verification before you can enable collection.</p>}
                <form
                  className="schedule"
                  key={`${market.id}:${market.enabled}:${market.interval_seconds}`}
                  onSubmit={(event) => {
                    event.preventDefault();
                    const form = new FormData(event.currentTarget);
                    action(async () => {
                      await api(
                        `/admin/markets/${market.id}/schedule`,
                        "PATCH",
                        {
                          enabled: form.get("enabled") === "on",
                          interval_seconds: Number(form.get("minutes")) * 60,
                        },
                      );
                      await refreshMarkets();
                    });
                  }}
                >
                  <label>
                    Interval (minutes)
                    <input
                      name="minutes"
                      type="number"
                      min="5"
                      max="1440"
                      defaultValue={market.interval_seconds / 60}
                      required
                    />
                  </label>
                  <label className="checkbox">
                    <input
                      name="enabled"
                      type="checkbox"
                      defaultChecked={market.enabled}
                      disabled={
                        readOnly ||
                        (!market.enabled &&
                          !market.player_identity_verified)
                      }
                    />
                    Enabled
                  </label>
                  <button disabled={readOnly}>Save schedule</button>
                </form>
            </details>
          </div>}
        />
      </section>
      <details className="panel padded admin-status-details"><summary>Add a market</summary>
        <form
          className="form-grid"
          onSubmit={(event) => {
            event.preventDefault();
            const form = new FormData(event.currentTarget);
            action(async () => {
              await api("/admin/configured-markets", "POST", {
                region,
                ruleset,
                faction,
                enabled: false,
                interval_seconds: Number(form.get("interval")),
              });
              await refreshMarkets();
            });
          }}
        >
          <label>
            Region
            <select
              aria-label="Region"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
            >
              {(options.data?.regions || ["us", "eu", "kr", "tw"]).map((r) => (
                <option key={r} value={r}>
                  {r.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
          <label>
            Ruleset
            <select
              aria-label="Ruleset"
              value={ruleset}
              onChange={(e) => setRuleset(e.target.value)}
            >
              {(
                options.data?.rulesets || [
                  "Normal",
                  "PvP",
                  "Roleplay",
                  "Roleplay PvP",
                ]
              ).map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </label>
          <label>
            Faction / auction house
            <select
              aria-label="Faction / auction house"
              value={faction}
              onChange={(e) => setFaction(e.target.value)}
            >
              {(
                options.data?.factions || ["Horde", "Alliance", "Blackwater"]
              ).map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
          </label>
          <label>
            Collection interval
            <select name="interval" defaultValue="300">
              <option value="300">5 minutes</option>
              <option value="900">15 minutes</option>
              <option value="1800">30 minutes</option>
              <option value="3600">1 hour</option>
              <option value="86400">1 day</option>
            </select>
          </label>
          <p className="muted">New schedules stay disabled until live verification.</p>
          <button className="primary" disabled={readOnly || !available}>
            Add disabled market
          </button>
        </form>
        {options.loading && <Loading label="Checking available markets…" inline/>}
        {options.data && !available && <p className="notice" role="status">This market still needs identity verification before it can be added.</p>}
        {options.error && <p role="alert">{options.error} <button onClick={options.refresh}>Retry market choices</button></p>}
      </details>
    </>
  );
}
