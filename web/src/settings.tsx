import type { StorageOperations } from "./storage-operations";
import { StorageDashboard, useStorageSummary } from "./storage-dashboard";
import { navigate, useLocation } from "./navigation";
import { administrationGroups, administrationSection } from "./admin-navigation";
import { useQuery } from "@tanstack/react-query";
import { useBackupOverview } from "./backup-management";
import "./administration.css";
import { Loading } from "./loading";
import { AdministrationOverview } from "./admin-overview";
import { MemberArchive } from "./member-archive";
import { CollectionHistory, SecurityHistory } from "./admin-histories";
import { LocalTime, Status } from "./admin-table";
import { DataSources, ItemMetadataAdmin, defaultMetadataMarket, useMetadataCoverage, useMetadataSourceSummary } from "./metadata-admin";
import { MyPreferences } from "./user-preferences";
import { MarketConfiguration } from "./market-configuration";
import { CompanionDevices } from "./companion-devices";
import { useState } from "react";
import { DataTable } from "./data-table";
import { api, User } from "./api";
import { Market } from "./types";
import { useLoad } from "./research";

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
export interface AdminAccessSummary {
  active_members: number;
  active_admins: number;
  pending_invitations: number;
  latest_security_event: string | null;
}

export interface Storage {
  operations?: StorageOperations;
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
      <h1>Account &amp; devices</h1>
      <nav className="account-task-nav" aria-label="Account tasks">
        <a href="#account-devices">Devices</a><a href="#account-preferences">Preferences</a><a href="#account-security" onClick={()=>{const section=document.querySelector<HTMLDetailsElement>("#account-security");if(section)section.open=true;}}>Security</a>
      </nav>
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
      <div id="account-devices"><CompanionDevices userId={userId} readOnly={readOnly} openCompanion={openCompanion}/></div>
      <div id="account-preferences"><MyPreferences /></div>
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
          loading={devices.loading || devices.refreshing}
          error={devices.error}
          emptyMessage="No legacy device tokens."
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

        </details>
      </section>
      <details id="account-security" className="panel padded account-security">
        <summary>Security · Change password</summary>
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
      </details>
    </>
  );
}

export function Administration({
  user,
  markets,
  marketStatus,
  refreshMarkets,
  readOnly = false,
}: {
  user: User;
  markets: Market[];
  marketStatus: "loading" | "unavailable" | "available";
  refreshMarkets: () => Promise<void>;
  readOnly?: boolean;
}) {
  const [memberHistory, setMemberHistory] = useState(false);
  const url = useLocation();
  const tab = administrationSection(url);
  const title = administrationGroups.flatMap(group => group.sections).find(section => section.id === tab)?.label;
  function setTab(value: string) { navigate(value === "overview" ? "/administration" : `/administration?admin_tab=${value}`); }
  const overview = tab === "overview";
  const storageQuery = useStorageSummary(overview);
  const backupQuery = useBackupOverview(0, undefined, 1, overview);
  const users = useAdminSection<User[]>(`/admin/users?include_archived=${memberHistory}`, tab === "members" || tab === "devices");
  const invitations = useAdminSection<Invitation[]>("/admin/invitations", tab === "invitations");
  const devices = useAdminSection<Device[]>("/admin/devices", tab === "devices");
  const access = useAdminSection<AdminAccessSummary>("/admin/access-summary", overview, 60_000);
  const deviceSummary = useAdminSection<{
    authorized: number;
    recently_connected: number;
    recent_window_minutes?: number;
    as_of?: string;
  }>("/companion/admin/device-summary", overview, 60_000);
  const coverageMarket = defaultMetadataMarket(markets);
  const coverage = useMetadataCoverage(coverageMarket?.id ?? 0, overview && marketStatus === "available", 120_000);
  const providerSummary = useMetadataSourceSummary(overview);
  const [message, setMessage] = useState(""), [error, setError] = useState(""),
    [invitation, setInvitation] = useState(""), [working, setBusy] = useState(false);
  const busy = working || readOnly;
  async function action(job: () => Promise<void>) {
    if (readOnly) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await job();
      await Promise.all([users, invitations, devices].filter(query=>query.fetchStatus !== "paused" && query.isEnabled).map(query=>query.refetch()));
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const invite = () =>
    action(async () => {
      const result = await api<{ token: string }>("/admin/invitations", "POST");
      setInvitation(
        `${location.origin}/?invite=${encodeURIComponent(result.token)}`,
      );
      setMessage(
        "Invitation created. It expires in seven days and can be used once.",
      );
    });
  return (
    <>
      <label className="mobile-admin-section">Administration section
        <select value={tab} onChange={event=>setTab(event.target.value)}>
          {administrationGroups.map(group=><optgroup key={group.label} label={group.label}>
            {group.sections.map(section=><option key={section.id} value={section.id}>{section.label}</option>)}
          </optgroup>)}
        </select>
      </label>
      {!["storage","metadata","sources"].includes(tab) && <h1>{tab === "overview" ? "Administration" : title}</h1>}
      {error && <p className="notice error" role="alert">{error}</p>}
      {message && <p className="notice success" role="status">{message}</p>}
      {working && <Loading inline label="Updating administration…"/>}
      {tab === "metadata" && <ItemMetadataAdmin markets={markets} readOnly={readOnly} />}
      {tab === "sources" && <DataSources readOnly={readOnly} />}
      {tab === "storage" && <StorageDashboard readOnly={readOnly}/>}
      {overview && <AdministrationOverview
        access={access.data}
        storage={storageQuery.data}
        backups={backupQuery.data}
        coverage={coverage.data}
        coverageMarket={coverageMarket}
        devices={deviceSummary.data}
        sources={providerSummary.sources}
        markets={markets}
        marketStatus={marketStatus}
        pending={{
          access: access.isPending,
          storage: storageQuery.isPending,
          backups: backupQuery.isPending,
          coverage: marketStatus === "loading" || (marketStatus === "available" && !!coverageMarket && coverage.isPending),
          devices: deviceSummary.isPending,
          sources: providerSummary.isPending,
        }}
        errors={{
          access: access.isError,
          storage: storageQuery.isError,
          backups: backupQuery.isError,
          coverage: marketStatus === "unavailable" || coverage.isError,
          devices: deviceSummary.isError,
          sources: providerSummary.isError,
        }}
      />}
          {tab === "members" && (
              <section className="panel padded">
                <div className="admin-view-switch" aria-label="Member views">
                  <button aria-pressed={!memberHistory} onClick={()=>setMemberHistory(false)}>Active members</button>
                  <button aria-pressed={memberHistory} onClick={()=>setMemberHistory(true)}>Disabled &amp; archived</button>
                  <button onClick={()=>setTab("invitations")}>Invitations</button>
                </div>
                {memberHistory && <p className="muted">Restoring an archived account returns it to the member list. Enable access separately.</p>}
                <DataTable<User>
                  label="members"
                  compact
                  filters={[{id:"role",label:"Filter member role",options:[{value:"admin",label:"Administrator"},{value:"member",label:"Member"}]}]}
                  loading={users.isFetching}
                  error={users.error?.message}
                  emptyMessage={memberHistory ? "No disabled or archived members." : "No active members."}
                  data={(users.data||[]).filter(member=>memberHistory ? !member.active || member.archived_at : member.active && !member.archived_at)}
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
                      accessorFn: (row) => row.archived_at ? "Archived" : row.active ? "Active" : "Disabled",
                      cell: ({getValue}) => <Status tone={getValue()==="Active"?"success":"neutral"}>{String(getValue())}</Status>,
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
          )}
          {tab === "invitations" && (
              <section className="panel padded">
                <div className="admin-view-switch">
                  <button onClick={()=>setTab("members")}>Members</button>
                  <button className="primary" disabled={busy} onClick={invite}>Create invitation</button>
                </div>
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
                  data={invitations.data||[]}
                  compact
                  loading={invitations.isFetching}
                  error={invitations.error?.message}
                  emptyMessage="No matching invitations. Create one to invite a member."
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
          {tab === "devices" && (
            <>
              <CompanionDevices userId={user.id} admin readOnly={readOnly} owners={Object.fromEntries((users.data||[]).map(member=>[member.id,member.username]))}/>
              <details className="panel padded"><summary>Older device tokens</summary>
              <DataTable<Device>
                compact label="legacy device tokens"
                loading={devices.isFetching}
                error={devices.error?.message}
                emptyMessage="No matching legacy device tokens."
                filters={[{id:"access",label:"Filter legacy device access",options:[{value:"Active",label:"Active"},{value:"Revoked",label:"Revoked"},{value:"Expired",label:"Expired"}]}]}
                data={devices.data||[]}
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
                      users.data?.find((user) => user.id === row.user_id)
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

              </details>
            </>
          )}
          {tab === "security" && <SecurityHistory/>}
    </>
  );
}

function useAdminSection<T>(path: string, enabled: boolean, refetchInterval?: number) {
  return useQuery({ queryKey: ["private", "administration", path], enabled, retry: false, refetchInterval,
    queryFn: ({signal}) => api<T>(path, "GET", undefined, signal) });
}
