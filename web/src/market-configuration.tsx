import { useState } from "react";
import { api, when } from "./api";
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
    <details onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>Advanced market diagnostics</summary>
      <p>
        Region {market.region.toUpperCase()} · transport ruleset{" "}
        {market.ruleset_id} · upstream house {market.house_id} ·{" "}
        {market.source_kind}
      </p>
      {data.error && <p role="alert">{data.error}</p>}
      <pre className="diagnostic-json">
        {JSON.stringify(data.data, null, 2)}
      </pre>
    </details>
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
        <h3>Configure a market</h3>
        <p>
          Choose the market you play. Numeric IDs are resolved from verified
          evidence.
        </p>
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
          <label>
            Collection status
            <select disabled value="disabled">
              <option value="disabled">Disabled until live verification</option>
            </select>
          </label>
          <button className="primary" disabled={readOnly || !available}>
            Add disabled market
          </button>
        </form>
        {!available && (
          <p className="notice" role="status">
            {region.toUpperCase()} — {ruleset} — {faction}: identity
            verification is pending. Collection cannot be started for this
            choice. The existing feed continues unchanged.
          </p>
        )}
        {options.error && <p role="alert">{options.error}</p>}
        <p className="small muted">{options.data?.notice}</p>
      </section>
      <section className="panel padded">
        <h3>Collection schedules</h3>
        <p>
          {markets.filter((m) => m.enabled).length} active market(s) consuming
          API requests and storage. Disabled schedules retain their existing
          history.
        </p>
        <DataTable<Market>
          label="market schedules"
          data={markets}
          getRowId={(m) => String(m.id)}
          columns={[
            {
              accessorKey: "label",
              header: "Market",
              enableHiding: false,
              cell: ({ row }) => (
                <>
                  <strong>{row.original.label}</strong>
                  <Diagnostics market={row.original} />
                </>
              ),
            },
            {
              id: "status",
              header: "Resources",
              accessorFn: (m) =>
                m.enabled
                  ? "Actively collecting"
                  : "Disabled · history retained",
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
              header: "Schedule",
              cell: ({ row }) => (
                <form
                  className="schedule"
                  key={`${row.original.id}:${row.original.enabled}:${row.original.interval_seconds}`}
                  onSubmit={(event) => {
                    event.preventDefault();
                    const form = new FormData(event.currentTarget);
                    action(async () => {
                      await api(
                        `/admin/markets/${row.original.id}/schedule`,
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
                      defaultValue={row.original.interval_seconds / 60}
                      required
                    />
                  </label>
                  <label className="checkbox">
                    <input
                      name="enabled"
                      type="checkbox"
                      defaultChecked={row.original.enabled}
                      disabled={
                        readOnly ||
                        (!row.original.enabled &&
                          !row.original.player_identity_verified)
                      }
                    />
                    Enabled
                  </label>
                  <button disabled={readOnly}>Save schedule</button>
                </form>
              ),
            },
          ]}
        />
      </section>
    </>
  );
}
