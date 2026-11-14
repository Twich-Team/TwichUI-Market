import { MyPreferences } from "./user-preferences";
import { MarketConfiguration } from "./market-configuration";
import { RetentionControls } from "./retention-controls";
import { useState } from "react";
import { DataTable } from "./data-table";
import { api, User, when } from "./api";
import { Market } from "./types";
import { useLoad } from "./research";

interface Enrichment {
  name_coverage?: {
    item_ids: number;
    primary_names: number;
    supplemental_names: number;
    unresolved: number;
    percent: number | null;
  };
  rich_items: number;
  community_items: number;
  community_enabled: boolean;
  icon_cache_budget_bytes: number;
  icon_states: { status: string; count: number; bytes: number }[];
  media_failures: MetadataFailure[];
}
interface Device {
  id: number;
  user_id?: number;
  name: string;
  revoked: boolean;
  expires_at: string;
}
interface Invitation {
  id: number;
  expires_at: string;
  used: boolean;
}
interface Run {
  id: number;
  market_id: number;
  checked_at: string;
  status: string;
  http_status: number | null;
  duration_seconds: number;
  payload_bytes: number;
  error: string | null;
}
interface MetadataFailure {
  region: string;
  item_id: number;
  status: string;
  http_status: number | null;
  checked_at: string;
  retry_after: string;
}
interface Event {
  id: number;
  actor_id: number | null;
  action: string;
  detail: string;
  created_at: string;
}
interface Storage {
  growth: {
    samples: { sampled_at: string; database_bytes: number }[];
    delta_bytes: number | null;
    bytes_per_day: number | null;
    elapsed_seconds: number;
  };
  database_bytes: number | null;
  snapshots: number;
  observations: number;
  retention: {
    historical_observations: string;
    guidance: string;
    raw_listing_days: number;
    detailed_statistics_days: number;
    compaction_enabled: boolean;
  };
  backup: {
    status: string;
    last_success?: string;
    last_restoration_verified_at?: string;
    bytes?: number;
    error?: string;
  };
}
const bytes = (value: number | null | undefined) =>
  value == null
    ? "Unavailable"
    : value < 1048576
      ? `${(value / 1024).toFixed(1)} KiB`
      : `${(value / 1048576).toFixed(1)} MiB`;

export function Account({
  signedOut,
  readOnly = false,
}: {
  signedOut: () => void;
  readOnly?: boolean;
}) {
  const devices = useLoad(
      "account-devices",
      () => api<Device[]>("/devices"),
      [],
    ),
    [message, setMessage] = useState(""),
    [error, setError] = useState(""),
    [token, setToken] = useState(""),
    [working, setBusy] = useState(false);
  const busy = working || readOnly;
  async function action(job: () => Promise<void>) {
    if (readOnly) return;
    setError("");
    setBusy(true);
    try {
      await job();
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="eyebrow">YOUR PRIVATE WORKSHOP</div>
      <h1>Account & devices</h1>
      <p className="intro">
        Manage the companion’s access and keep your account secure.
      </p>
      {(error || devices.error) && (
        <p className="notice error" role="alert">
          {error || devices.error}
        </p>
      )}
      {message && (
        <p className="notice success" role="status">
          {message}
        </p>
      )}
      <MyPreferences />
      <section className="panel padded">
        <h2>Connect a desktop companion</h2>
        <p>
          Create a named device token, then paste it into the Windows companion.
          Tokens expire after 90 days.
        </p>
        <form
          className="toolbar"
          onSubmit={(event) => {
            event.preventDefault();
            const form = new FormData(event.currentTarget);
            action(async () => {
              const result = await api<{ token: string }>("/devices", "POST", {
                name: String(form.get("name")),
              });
              setToken(result.token);
              devices.refresh();
              setMessage(
                "Device credential created. Copy it now; it cannot be shown again.",
              );
            });
          }}
        >
          <label className="grow">
            Device name
            <input
              name="name"
              placeholder="My Windows PC"
              maxLength={80}
              required
            />
          </label>
          <button className="primary" disabled={busy}>
            Create device token
          </button>
        </form>
        {token && (
          <label className="token">
            New device token · treat it like a password
            <input
              aria-label="New device token"
              value={token}
              readOnly
              onFocus={(event) => event.currentTarget.select()}
            />
            <button className="text-button" onClick={() => setToken("")}>
              Hide token
            </button>
          </label>
        )}
        <DataTable<Device>
          label="devices"
          data={devices.data || []}
          columns={[
            { accessorKey: "name", header: "Device", enableHiding: false },
            {
              accessorKey: "expires_at",
              header: "Expires",
              cell: ({ row }) => when(row.original.expires_at),
            },
            {
              id: "access",
              header: "Access",
              accessorFn: (row) =>
                row.revoked
                  ? "Revoked"
                  : new Date(row.expires_at) < new Date()
                    ? "Expired"
                    : "Active",
            },
            {
              id: "action",
              header: "Action",
              enableSorting: false,
              cell: ({ row }) => (
                <button
                  className="secondary"
                  disabled={row.original.revoked || busy}
                  onClick={() =>
                    action(async () => {
                      await api(`/devices/${row.original.id}`, "DELETE");
                      devices.refresh();
                      setMessage("Device access revoked.");
                    })
                  }
                >
                  Revoke
                </button>
              ),
            },
          ]}
        />

        {devices.data?.length === 0 && (
          <p className="empty">No connected devices.</p>
        )}
      </section>
      <section className="panel padded">
        <h2>Change password</h2>
        <p>
          Changing your password signs out every browser and revokes all device
          tokens.
        </p>
        <form
          className="form-grid"
          onSubmit={(event) => {
            event.preventDefault();
            const form = new FormData(event.currentTarget);
            action(async () => {
              await api("/auth/password", "POST", {
                current_password: String(form.get("current")),
                new_password: String(form.get("new")),
              });
              signedOut();
            });
          }}
        >
          <label>
            Current password
            <input
              name="current"
              type="password"
              minLength={12}
              maxLength={128}
              autoComplete="current-password"
              required
            />
          </label>
          <label>
            New password
            <input
              name="new"
              type="password"
              minLength={12}
              maxLength={128}
              autoComplete="new-password"
              required
            />
          </label>
          <button className="primary" disabled={busy}>
            Change password and sign out
          </button>
        </form>
      </section>
    </>
  );
}

export function Administration({
  user,
  markets,
  refreshMarkets,
  readOnly = false,
}: {
  user: User;
  markets: Market[];
  refreshMarkets: () => Promise<void>;
  readOnly?: boolean;
}) {
  const [tab, setTab] = useState("overview"),
    [message, setMessage] = useState(""),
    [error, setError] = useState(""),
    [invitation, setInvitation] = useState(""),
    [working, setBusy] = useState(false);
  const data = useLoad(
    "administration",
    async () => {
      const [
        users,
        invitations,
        devices,
        runs,
        storage,
        events,
        metadata,
        enrichment,
      ] = await Promise.all([
        api<User[]>("/admin/users"),
        api<Invitation[]>("/admin/invitations"),
        api<Device[]>("/admin/devices"),
        api<{ runs: Run[] }>("/admin/collection-runs"),
        api<Storage>("/admin/storage"),
        api<Event[]>("/admin/security-events"),
        api<MetadataFailure[]>("/admin/metadata-failures"),
        api<Enrichment>("/admin/item-enrichment"),
      ]);
      return {
        users,
        invitations,
        devices,
        runs: runs.runs,
        storage,
        events,
        metadata,
        enrichment,
      };
    },
    [],
  );
  const busy = working || readOnly;
  async function action(job: () => Promise<void>) {
    if (readOnly) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await job();
      data.refresh();
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const state = data.data;
  const titles: Record<string, string> = {
    overview: "Overview",
    members: "Members & invitations",
    markets: "Markets & schedules",
    collection: "Collection",
    storage: "Storage & backups",
    devices: "Devices",
    security: "Security events",
  };
  const invite = () =>
    action(async () => {
      const result = await api<{ token: string }>("/admin/invitations", "POST");
      setInvitation(
        `${location.origin}/?invite=${encodeURIComponent(result.token)}`,
      );
      setMessage(
        "Invitation created. It expires in seven days and can be used once.",
      );
      setTab("members");
    });
  return (
    <>
      <div className="eyebrow">KEEP THE LEDGER RUNNING</div>
      <div className="title-row">
        <div>
          <h1>Administration</h1>
          <p className="intro">
            Members, market collection, storage, and security.
          </p>
        </div>
        <button className="primary" disabled={busy} onClick={invite}>
          Invite a friend
        </button>
      </div>
      {(error || data.error) && (
        <p className="notice error" role="alert">
          {error || data.error}
        </p>
      )}
      {message && (
        <p className="notice success" role="status">
          {message}
        </p>
      )}
      {data.loading && (
        <p role="status" className="muted">
          Loading administration…
        </p>
      )}
      <div className="admin-tabs" role="tablist">
        {Object.entries(titles).map(([key, title]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            className={tab === key ? "selected" : ""}
            onClick={() => setTab(key)}
          >
            {title}
          </button>
        ))}
      </div>
      {state && (
        <>
          {tab === "overview" && (
            <>
              <div className="stats">
                <article>
                  <label>COLLECTION</label>
                  <strong>
                    {markets.filter((row) => row.enabled).length} active markets
                  </strong>
                  <small>
                    {markets.filter((row) => row.failures).length} reporting
                    failures
                  </small>
                </article>
                <article>
                  <label>DATABASE SIZE</label>
                  <strong>{bytes(state.storage.database_bytes)}</strong>
                  <small>
                    {state.storage.observations.toLocaleString()} observations
                  </small>
                </article>
                <article>
                  <label>BACKUP STATUS</label>
                  <strong>
                    {state.storage.backup.status.replaceAll("_", " ")}
                  </strong>
                  <small>{when(state.storage.backup.last_success)}</small>
                </article>
                <article>
                  <label>DEVICE ACCESS</label>
                  <strong>
                    {
                      state.devices.filter(
                        (row) =>
                          !row.revoked && new Date(row.expires_at) > new Date(),
                      ).length
                    }{" "}
                    active devices
                  </strong>
                  <small>
                    {state.users.filter((row) => row.active).length} active
                    members
                  </small>
                </article>
              </div>
              <section className="panel padded">
                <h3>Item enrichment</h3>
                {state.enrichment.name_coverage && (
                  <p>
                    <strong>
                      {state.enrichment.name_coverage.percent ?? 0}% names
                      resolved
                    </strong>{" "}
                    across{" "}
                    {state.enrichment.name_coverage.item_ids.toLocaleString()}{" "}
                    current item IDs ·{" "}
                    {state.enrichment.name_coverage.primary_names.toLocaleString()}{" "}
                    Blizzard ·{" "}
                    {state.enrichment.name_coverage.supplemental_names.toLocaleString()}{" "}
                    attributed supplemental ·{" "}
                    {state.enrichment.name_coverage.unresolved.toLocaleString()}{" "}
                    unresolved.
                  </p>
                )}
                <p>
                  {state.enrichment.rich_items.toLocaleString()} items with base
                  attributes ·{" "}
                  {state.enrichment.community_items.toLocaleString()} separately
                  attributed community records.
                </p>
                <p>
                  Community fallback{" "}
                  {state.enrichment.community_enabled ? "enabled" : "disabled"}.
                  Artwork cache limit{" "}
                  {bytes(state.enrichment.icon_cache_budget_bytes)}.
                </p>
                <ul>
                  {state.enrichment.icon_states.map((row) => (
                    <li key={row.status}>
                      {row.status}: {row.count.toLocaleString()} icons ·{" "}
                      {bytes(row.bytes)}
                    </li>
                  ))}
                </ul>
                <details>
                  <summary>Recent artwork failures</summary>
                  <DataTable<MetadataFailure>
                    label="artwork failures"
                    data={state.enrichment.media_failures}
                    columns={[
                      {
                        accessorKey: "item_id",
                        header: "Item ID",
                        enableHiding: false,
                      },
                      { accessorKey: "region", header: "Region" },
                      { accessorKey: "status", header: "Status" },
                      { accessorKey: "http_status", header: "HTTP" },
                      {
                        accessorKey: "retry_after",
                        header: "Next attempt",
                        cell: ({ row }) => when(row.original.retry_after),
                      },
                    ]}
                  />
                </details>
                <h3>Collection readiness</h3>
                {!markets.length ? (
                  <p>
                    No markets configured. Add a mapping under Markets &
                    schedules.
                  </p>
                ) : (
                  <ul className="market-summary">
                    {markets.map((row) => (
                      <li key={row.id}>
                        <strong>{row.label}</strong>
                        <span>
                          {row.verified
                            ? "Mapping verified"
                            : "Live verification pending"}{" "}
                          · {row.enabled ? "Scheduled" : "Disabled"}
                        </span>
                        <small>
                          {row.last_error ||
                            `Last successful check: ${when(row.last_success)}`}
                        </small>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="notice">
                  Historical retention is configurable under Storage & backups.
                  Proposed policies require explicit owner approval before
                  destructive application.
                </p>
              </section>
            </>
          )}
          {tab === "members" && (
            <>
              <section className="panel padded">
                <h3>Members</h3>
                <DataTable<User>
                  label="members"
                  data={state.users}
                  getRowId={(row) => String(row.id)}
                  columns={[
                    {
                      accessorKey: "username",
                      header: "Player",
                      enableHiding: false,
                      cell: ({ row }) =>
                        `${row.original.username}${row.original.id === user.id ? " (you)" : ""}`,
                    },
                    {
                      accessorKey: "role",
                      header: "Role",
                      cell: ({ row }) => (
                        <select
                          aria-label={`Role for ${row.original.username}`}
                          value={row.original.role}
                          disabled={busy || row.original.id === user.id}
                          onChange={(event) =>
                            action(async () => {
                              await api(
                                `/admin/users/${row.original.id}`,
                                "PATCH",
                                {
                                  role: event.target.value,
                                  active: row.original.active,
                                },
                              );
                              setMessage("Member role updated.");
                            })
                          }
                        >
                          <option value="member">Member</option>
                          <option value="admin">Administrator</option>
                        </select>
                      ),
                    },
                    {
                      id: "status",
                      header: "Status",
                      accessorFn: (row) => (row.active ? "Active" : "Disabled"),
                    },
                    {
                      id: "action",
                      header: "Access",
                      enableSorting: false,
                      cell: ({ row }) => (
                        <button
                          className="secondary"
                          disabled={busy || row.original.id === user.id}
                          onClick={() =>
                            action(async () => {
                              await api(
                                `/admin/users/${row.original.id}`,
                                "PATCH",
                                {
                                  role: row.original.role,
                                  active: !row.original.active,
                                },
                              );
                              setMessage(
                                "Member access updated. Disabling also revokes their credentials.",
                              );
                            })
                          }
                        >
                          {row.original.active ? "Disable" : "Enable"}
                        </button>
                      ),
                    },
                  ]}
                />
              </section>
              <section className="panel padded">
                <h3>Invitations</h3>
                {invitation && (
                  <label className="token">
                    New invitation link · shown only now
                    <input
                      aria-label="New invitation link"
                      value={invitation}
                      readOnly
                      onFocus={(event) => event.currentTarget.select()}
                    />
                    <button
                      className="text-button"
                      onClick={() => setInvitation("")}
                    >
                      Hide invitation
                    </button>
                  </label>
                )}
                <DataTable<Invitation>
                  label="invitations"
                  data={state.invitations}
                  columns={[
                    { accessorKey: "id", header: "Invitation" },
                    {
                      accessorKey: "expires_at",
                      header: "Expires",
                      cell: ({ row }) => when(row.original.expires_at),
                    },
                    {
                      id: "status",
                      header: "Status",
                      accessorFn: (row) =>
                        row.used
                          ? "Used or revoked"
                          : new Date(row.expires_at) < new Date()
                            ? "Expired"
                            : "Available",
                    },
                    {
                      id: "action",
                      header: "Action",
                      enableSorting: false,
                      cell: ({ row }) => (
                        <button
                          className="secondary"
                          disabled={row.original.used || busy}
                          onClick={() =>
                            action(async () => {
                              await api(
                                `/admin/invitations/${row.original.id}`,
                                "DELETE",
                              );
                              setMessage("Invitation revoked.");
                            })
                          }
                        >
                          Revoke
                        </button>
                      ),
                    },
                  ]}
                />
              </section>
            </>
          )}
          {tab === "markets" && (
            <MarketConfiguration
              markets={markets}
              readOnly={busy}
              refreshMarkets={refreshMarkets}
              action={action}
            />
          )}
          {tab === "collection" && (
            <section className="panel table-panel">
              <div className="panel-heading">
                <h3>Collection checks</h3>
                <button className="secondary" onClick={data.refresh}>
                  Refresh
                </button>
              </div>
              <DataTable<Run>
                label="collection checks"
                data={state.runs}
                columns={[
                  {
                    accessorKey: "market_id",
                    header: "Market",
                    enableHiding: false,
                    cell: ({ row }) => `#${row.original.market_id}`,
                  },
                  {
                    accessorKey: "checked_at",
                    header: "Checked",
                    cell: ({ row }) => when(row.original.checked_at),
                  },
                  { accessorKey: "status", header: "Result" },
                  {
                    accessorKey: "http_status",
                    header: "HTTP",
                    cell: ({ row }) => row.original.http_status || "—",
                  },
                  {
                    accessorKey: "payload_bytes",
                    header: "Payload",
                    cell: ({ row }) => bytes(row.original.payload_bytes),
                  },
                  {
                    accessorKey: "error",
                    header: "Detail",
                    cell: ({ row }) =>
                      row.original.error || "No failure recorded",
                  },
                ]}
              />

              {!state.runs.length && (
                <p className="empty">
                  No collection attempts recorded. Markets may still be
                  disabled.
                </p>
              )}
              <div className="panel-heading">
                <h3>Unresolved item names</h3>
              </div>
              <DataTable<MetadataFailure>
                label="unresolved items"
                data={state.metadata}
                columns={[
                  {
                    accessorKey: "item_id",
                    header: "Item ID",
                    enableHiding: false,
                  },
                  { accessorKey: "region", header: "Region" },
                  { accessorKey: "status", header: "Status" },
                  { accessorKey: "http_status", header: "HTTP" },
                  {
                    accessorKey: "checked_at",
                    header: "Last lookup",
                    cell: ({ row }) => when(row.original.checked_at),
                  },
                  {
                    accessorKey: "retry_after",
                    header: "Next retry",
                    cell: ({ row }) => when(row.original.retry_after),
                  },
                ]}
              />

              {!state.metadata.length && (
                <p className="empty">No metadata lookup failures recorded.</p>
              )}
            </section>
          )}
          {tab === "storage" && (
            <>
              <RetentionControls readOnly={readOnly} />
              <section className="panel padded">
                <h3>Database & historical retention</h3>
                <dl>
                  <dt>Database size</dt>
                  <dd>{bytes(state.storage.database_bytes)}</dd>
                  <dt>Measured change</dt>
                  <dd>
                    {state.storage.growth.delta_bytes === null
                      ? "Waiting for two hourly measurements"
                      : `${state.storage.growth.delta_bytes < 0 ? "−" : "+"}${bytes(Math.abs(state.storage.growth.delta_bytes))} over ${(state.storage.growth.elapsed_seconds / 86400).toFixed(1)} days`}
                  </dd>
                  <dt>Average daily change</dt>
                  <dd>
                    {state.storage.growth.bytes_per_day === null
                      ? "Unavailable"
                      : `${state.storage.growth.bytes_per_day < 0 ? "−" : "+"}${bytes(Math.abs(state.storage.growth.bytes_per_day))} per day`}
                  </dd>
                  <dt>Distinct snapshots</dt>
                  <dd>{state.storage.snapshots.toLocaleString()}</dd>
                  <dt>Fetch observations</dt>
                  <dd>{state.storage.observations.toLocaleString()}</dd>
                  <dt>Historical retention</dt>
                  <dd>
                    Policy proposals are shown above; live historical pruning
                    remains disabled until authorized.
                  </dd>
                  <dt>Raw listing details</dt>
                  <dd>
                    {state.storage.retention.compaction_enabled
                      ? `${state.storage.retention.raw_listing_days} days plus the current snapshot`
                      : "Compaction disabled; raw details preserved"}
                  </dd>
                  <dt>Detailed price samples</dt>
                  <dd>
                    {state.storage.retention.compaction_enabled
                      ? `${state.storage.retention.detailed_statistics_days} days; daily policy protects valuation support`
                      : "Historical compaction is disabled"}
                  </dd>
                </dl>
                <p>
                  Operational logs have separate configurable retention.
                  Historical listings are never treated as completed sales.
                </p>
                <p className="notice">
                  Database size measures PostgreSQL allocation. Logical row
                  removal permits reuse; filesystem space recovery is unknown.
                </p>
              </section>
              <section className="panel padded">
                <h3>Backups & restoration</h3>
                <dl>
                  <dt>Backup service</dt>
                  <dd>{state.storage.backup.status.replaceAll("_", " ")}</dd>
                  <dt>Last successful dump</dt>
                  <dd>{when(state.storage.backup.last_success)}</dd>
                  <dt>Last restore rehearsal</dt>
                  <dd>
                    {when(state.storage.backup.last_restoration_verified_at)}
                  </dd>
                  <dt>Archive size</dt>
                  <dd>{bytes(state.storage.backup.bytes)}</dd>
                </dl>
                <p className="muted">
                  Hourly database measurements are retained for 90 days. Changes
                  include PostgreSQL allocation and maintenance, and do not
                  predict future growth.
                </p>
                <details>
                  <summary>Recent storage measurements</summary>
                  <DataTable<{ sampled_at: string; database_bytes: number }>
                    label="storage measurements"
                    data={state.storage.growth.samples}
                    initialSorting={[{ id: "sampled_at", desc: true }]}
                    columns={[
                      {
                        accessorKey: "sampled_at",
                        header: "Measured at",
                        cell: ({ row }) => when(row.original.sampled_at),
                      },
                      {
                        accessorKey: "database_bytes",
                        header: "Database allocation",
                        meta: { numeric: true },
                        cell: ({ row }) => bytes(row.original.database_bytes),
                      },
                    ]}
                  />
                </details>
                {state.storage.backup.error && (
                  <p className="notice error">{state.storage.backup.error}</p>
                )}
                <p>
                  Local backups are managed by the operations service. An
                  owner-managed encrypted off-host copy is still needed for
                  disaster recovery.
                </p>
              </section>
            </>
          )}
          {tab === "devices" && (
            <section className="panel padded">
              <h3>Connected devices</h3>
              <DataTable<Device>
                label="connected devices"
                data={state.devices}
                columns={[
                  {
                    accessorKey: "name",
                    header: "Device",
                    enableHiding: false,
                  },
                  {
                    id: "member",
                    header: "Member",
                    accessorFn: (row) =>
                      state.users.find((user) => user.id === row.user_id)
                        ?.username || `#${row.user_id}`,
                  },
                  {
                    accessorKey: "expires_at",
                    header: "Expires",
                    cell: ({ row }) => when(row.original.expires_at),
                  },
                  {
                    id: "access",
                    header: "Access",
                    accessorFn: (row) =>
                      row.revoked
                        ? "Revoked"
                        : new Date(row.expires_at) < new Date()
                          ? "Expired"
                          : "Active",
                  },
                  {
                    id: "action",
                    header: "Action",
                    enableSorting: false,
                    cell: ({ row }) => (
                      <button
                        className="secondary"
                        disabled={busy || row.original.revoked}
                        onClick={() =>
                          action(async () => {
                            await api(`/devices/${row.original.id}`, "DELETE");
                            setMessage("Device access revoked.");
                          })
                        }
                      >
                        Revoke
                      </button>
                    ),
                  },
                ]}
              />

              {!state.devices.length && (
                <p className="empty">No companion devices registered.</p>
              )}
            </section>
          )}
          {tab === "security" && (
            <section className="panel table-panel">
              <div className="panel-heading">
                <h3>Security events</h3>
                <span className="muted">Most recent 200 events</span>
              </div>
              <DataTable<Event>
                label="security events"
                data={state.events}
                columns={[
                  {
                    accessorKey: "created_at",
                    header: "Time",
                    enableHiding: false,
                    cell: ({ row }) => when(row.original.created_at),
                  },
                  {
                    id: "member",
                    header: "Member",
                    accessorFn: (row) =>
                      state.users.find((user) => user.id === row.actor_id)
                        ?.username || "Unauthenticated / system",
                  },
                  {
                    id: "event",
                    header: "Event",
                    accessorFn: (row) =>
                      row.action.replaceAll(".", " ").replaceAll("_", " "),
                  },
                  {
                    accessorKey: "detail",
                    header: "Reference",
                    cell: ({ row }) => row.original.detail || "—",
                  },
                ]}
              />
            </section>
          )}
        </>
      )}
    </>
  );
}
