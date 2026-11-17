import { Loading } from "./loading";
import { AdministrationOverview } from "./admin-overview";
import type { MetadataOverview } from "./metadata-admin";
import { DatabaseGrowth } from "./storage-growth";
import { formatBytes as bytes } from "./size";
import { MemberArchive } from "./member-archive";
import { CollectionHistory, SecurityHistory } from "./admin-histories";
import { LocalTime } from "./admin-table";
import { DataSources, ItemMetadataAdmin } from "./metadata-admin";
import { MyPreferences } from "./user-preferences";
import { MarketConfiguration } from "./market-configuration";
import { RetentionControls } from "./retention-controls";
import { CompanionDevices } from "./companion-devices";
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
export interface Storage {
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

export function Account({
  signedOut,
  readOnly = false,
  userId,openCompanion,
}: {
  signedOut: () => void;
  readOnly?: boolean;
  userId:number;openCompanion:()=>void;
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
      {working && <Loading label="Updating your account…"/>}
      <MyPreferences />
      <section className="panel padded"><div className="eyebrow">WINDOWS COMPANION</div><h2>Your market, ready on your PC.</h2><p>Install the companion, then approve this device in your browser. Your password stays on the website.</p><button className="primary" onClick={openCompanion}>Get Desktop Companion</button></section>
      <CompanionDevices userId={userId}/>
      <section className="panel padded">
        <details className="legacy-device-access"><summary>Older companions &amp; API clients</summary>
        <h2>Legacy device tokens</h2>
        <p>
          These credentials are for older companions and API clients. New Windows
          installations use browser approval above. Legacy tokens expire after 90 days.
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
          getRowId={row=>String(row.id)}
          columns={[
            { accessorKey: "name", header: "Device", enableHiding: false },
            {
              accessorKey: "expires_at",
              header: "Expires",
              cell: ({ row }) => <LocalTime value={row.original.expires_at}/>,
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
        </details>
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
  const [includeArchived, setIncludeArchived] = useState(false);
  const [tab, setTab] = useState(new URLSearchParams(location.search).get("metadata_view")==="tracker"?"metadata":"overview"),
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
        storage,
        enrichment,
        deviceSummary,
        coverage,
      ] = await Promise.all([
        api<User[]>(`/admin/users?include_archived=${includeArchived}`),
        api<Invitation[]>("/admin/invitations"),
        api<Device[]>("/admin/devices"),
        api<Storage>("/admin/storage"),
        api<Enrichment>("/admin/item-enrichment"),
        api<{authorized:number;revoked:number;expired:number;recently_connected:number;authorized_names:string[];live_status:string}>("/companion/admin/device-summary"),
        api<MetadataOverview>("/admin/item-metadata"),
      ]);
      return {
        users,
        invitations,
        devices,
        storage,
        enrichment,
        deviceSummary,
        coverage,
      };
    },
    [includeArchived],
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
    metadata: "Item Metadata",
    sources: "Data Sources",
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
        <Loading label="Loading administration…" />
      )}
      {(working || data.refreshing) && <Loading inline label="Updating administration…"/>}
      <label className="mobile-admin-section">Administration section<select value={tab} onChange={event=>setTab(event.target.value)}>{Object.entries(titles).map(([key,title])=><option key={key} value={key}>{title}</option>)}</select></label>
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
      {tab === "metadata" && <ItemMetadataAdmin markets={markets} readOnly={readOnly} />}
      {tab === "sources" && <DataSources readOnly={readOnly} />}
      {state && (
        <>
          {tab === "overview" && <AdministrationOverview storage={state.storage} coverage={state.coverage} devices={state.deviceSummary} markets={markets} open={setTab}/>}
          {tab === "members" && (
            <>
              <section className="panel padded">
                <h3>Members</h3>
                <p className="small muted">Disabled accounts remain listed. Archiving hides an account and retains its audit and owned records. Restoring a listing does not restore access.</p>
                <label className="checkbox"><input type="checkbox" checked={includeArchived} onChange={e => setIncludeArchived(e.target.checked)}/>Include archived accounts</label>
                <DataTable<User>
                  label="members"
                  filters={[{id:"role",label:"Filter member role",options:[{value:"admin",label:"Administrator"},{value:"member",label:"Member"}]},{id:"status",label:"Filter member status",options:[{value:"Active",label:"Active"},{value:"Disabled",label:"Disabled"},{value:"Archived",label:"Archived"}]}]}
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
                          disabled={busy || row.original.id === user.id || Boolean(row.original.archived_at)}
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
                      accessorFn: (row) => (row.archived_at ? "Archived" : row.active ? "Active" : "Disabled"),
                    },
                    {
                      id: "action",
                      header: "Access",
                      enableSorting: false,
                      cell: ({ row }) => (
                        <button
                          className="secondary"
                          disabled={busy || row.original.id === user.id || Boolean(row.original.archived_at)}
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
                    {id:"archive",header:"Listing",enableSorting:false,cell:({row}) => <MemberArchive member={row.original} disabled={busy || row.original.id === user.id} run={action}/>},
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
                  filters={[{id:"status",label:"Filter invitation status",options:[{value:"Available",label:"Available"},{value:"Used or revoked",label:"Used or revoked"},{value:"Expired",label:"Expired"}]}]}
                  data={state.invitations}
                  getRowId={row=>String(row.id)}
                  columns={[
                    { accessorKey: "id", header: "Invitation" },
                    {
                      accessorKey: "expires_at",
                      header: "Expires",
                      cell: ({ row }) => <LocalTime value={row.original.expires_at}/>,
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
          {tab === "collection" && <CollectionHistory markets={markets}/>}
          {tab === "storage" && (
            <>
              <DatabaseGrowth samples={state.storage.growth.samples} current={state.storage.database_bytes}/>
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
                    getRowId={row=>row.sampled_at}
                    initialSorting={[{ id: "sampled_at", desc: true }]}
                    columns={[
                      {
                        accessorKey: "sampled_at",
                        header: "Measured at",
                        cell: ({ row }) => <LocalTime value={row.original.sampled_at}/>,
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
              <CompanionDevices userId={user.id} admin readOnly={readOnly} owners={Object.fromEntries(state.users.map(member=>[member.id,member.username]))}/>
              <h3>Connected devices</h3>
              <DataTable<Device>
                label="connected devices"
                filters={[{id:"access",label:"Filter legacy device access",options:[{value:"Active",label:"Active"},{value:"Revoked",label:"Revoked"},{value:"Expired",label:"Expired"}]}]}
                data={state.devices}
                getRowId={row=>String(row.id)}
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
                    cell: ({ row }) => <LocalTime value={row.original.expires_at}/>,
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
          {tab === "security" && <SecurityHistory/>}
        </>
      )}
    </>
  );
}
