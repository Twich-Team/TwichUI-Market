import { ConfirmationDialog } from "./confirmation-dialog";
import { DataTable } from "./data-table";
import { LocalTime, Status } from "./admin-table";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, when } from "./api";
import { queryClient } from "./query";
export interface CompanionDevice {
  id: number;
  user_id: number;
  name: string;
  platform: string;
  app_version: string;
  authorized_at: string;
  expires_at: string;
  renewal_expires_at?: string;
  last_connection_at: string | null;
  last_sync_at: string | null;
  selected_market_id: number | null;
  selected_market_name: string | null;
  archived_at?: string | null;
  revoked: boolean;
}
export interface DeviceList {
  devices: CompanionDevice[];
  legacy_devices?: {
    id: number;
    name: string;
    revoked: boolean;
    expires_at: string;
  }[];
}
export const deviceKey = (userId: number, admin = false) => [
  "private",
  "companion",
  admin ? "admin-devices" : "devices",
  userId,
];
export function useCompanionDevices(
  userId: number,
  admin = false,
  poll = false,
  includeArchived = false,
) {
  return useQuery({
    queryKey: [...deviceKey(userId, admin), includeArchived],
    queryFn: ({ signal }) =>
      api<DeviceList>(
        `${admin ? "/companion/admin/devices" : "/companion/devices"}?include_archived=${includeArchived}`,
        "GET",
        undefined,
        signal,
      ),
    refetchInterval: poll ? 5000 : false,
    staleTime: 10_000,
  });
}
function DeviceCard({
  device,
  userId,
  admin,
  readOnly,
  owner,
}: {
  device: CompanionDevice;
  userId: number;
  admin: boolean;
  readOnly: boolean;
  owner?: string;
}) {
  const [editing, setEditing] = useState(false),
    [draft, setDraft] = useState(device.name),
    [confirm, setConfirm] = useState(false),
    [archiveConfirm, setArchiveConfirm] = useState(false),
    [archiveName, setArchiveName] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const expired =
    new Date(device.expires_at).getTime() <= Date.now() ||
    Boolean(
      device.renewal_expires_at &&
        new Date(device.renewal_expires_at).getTime() <= Date.now(),
    );
  async function act(operation: "rename" | "revoke" | "archive" | "restore") {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (operation === "rename")
        await api(`/companion/devices/${device.id}`, "PATCH", {
          name: draft.trim(),
        });
      else if (operation === "archive" || operation === "restore")
        await api(`/companion/${admin ? "admin/" : ""}devices/${device.id}/${operation}`, "POST", operation === "archive" ? {confirmation: archiveName} : undefined);
      else
        await api(
          `/companion/${admin ? "admin/" : ""}devices/${device.id}`,
          "DELETE",
        );
      await queryClient.invalidateQueries({
        queryKey: deviceKey(userId, admin),
      });
      setEditing(false);
      setConfirm(false);
      setArchiveConfirm(false);
      setMessage(
        operation === "rename"
          ? "Device renamed."
          : operation === "archive" ? "Entry archived. Security evidence is retained." : operation === "restore" ? "Entry restored; access remains revoked." : "Access revoked. Offline data on that PC is preserved.",
      );
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <article className="companion-device" aria-label={`${device.name} device`}>
      <div className="device-heading">
        <span className="device-glyph" aria-hidden="true">
          ▣
        </span>
        <div>
          <h3>{device.name}</h3>
          <p className="small muted">
            {device.platform} · Companion {device.app_version}
            {owner && ` · ${owner}`}
          </p>
        </div>
        <span
          className={`badge ${device.revoked ? "muted" : expired ? "warning" : "success"}`}
        >
          {device.revoked
            ? "Revoked"
            : expired
              ? "Sign-in expired"
              : "Authorized"}
        </span>
      </div>
      <dl className="companion-device-facts">
        <div>
          <dt>Authorized</dt>
          <dd>{when(device.authorized_at)}</dd>
        </div>
        <div>
          <dt>Last connection</dt>
          <dd>
            {device.last_connection_at
              ? when(device.last_connection_at)
              : "Not yet"}
          </dd>
        </div>
        <div>
          <dt>Last sync delivered</dt>
          <dd>
            {device.last_sync_at
              ? when(device.last_sync_at)
              : "Waiting for first sync"}
          </dd>
        </div>
        <div>
          <dt>Selected market</dt>
          <dd>{device.selected_market_name || "Not selected yet"}</dd>
        </div>
        <div>
          <dt>Authorization expires</dt>
          <dd>{when(device.expires_at)}</dd>
        </div>
      </dl>
      {editing ? (
        <form
          className="toolbar"
          onSubmit={(event) => {
            event.preventDefault();
            void act("rename");
          }}
        >
          <label className="grow">
            New name for {device.name}
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              minLength={1}
              maxLength={80}
              required
              autoComplete="off"
              autoFocus
            />
          </label>
          <button className="primary" disabled={busy || !draft.trim()}>
            Save name
          </button>
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => setEditing(false)}
          >
            Cancel
          </button>
        </form>
      ) : (
        <div className="companion-device-actions">
          {!admin && !device.archived_at && (
            <button
              className="secondary"
              disabled={busy}
              onClick={() => {
                setDraft(device.name);
                setEditing(true);
                setConfirm(false);
              }}
            >
              Rename
            </button>
          )}
          {device.revoked && !device.archived_at && <button className="secondary" disabled={busy || readOnly} onClick={() => setArchiveConfirm(true)}>Archive entry</button>}
          {device.archived_at && !admin && <button className="secondary" disabled={busy || readOnly} onClick={() => act("restore")}>Restore listing</button>}
          {!device.revoked && !confirm && (
            <button
              className="secondary"
              disabled={busy || readOnly}
              onClick={() => {
                setConfirm(true);
                setEditing(false);
              }}
            >
              Revoke access
            </button>
          )}
        </div>
      )}
      {archiveConfirm && <ConfirmationDialog title={`Archive ${device.name}?`} onClose={() => setArchiveConfirm(false)}>
        <p>Hide {device.name} from the ordinary device list? Access is already revoked. Security and delivery evidence is retained; no database records are deleted.</p>
        <label>Type {device.name} to confirm<input value={archiveName} onChange={e => setArchiveName(e.target.value)} autoComplete="off"/></label>
        <button className="primary" disabled={busy || readOnly || archiveName !== device.name} onClick={() => act("archive")}>Confirm archive</button>
        <button className="text-button" disabled={busy} onClick={() => setArchiveConfirm(false)}>Cancel</button>
      </ConfirmationDialog>}
      {confirm && (
        <div className="notice">
          <p>
            Stop future synchronization on <strong>{device.name}</strong>?
            Cached prices remain on that PC.
          </p>
          <button
            className="primary"
            disabled={busy || readOnly}
            onClick={() => act("revoke")}
          >
            Revoke {device.name}
          </button>
          <button
            className="text-button"
            disabled={busy}
            onClick={() => setConfirm(false)}
          >
            Keep connected
          </button>
        </div>
      )}
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="small success" role="status">
          {message}
        </p>
      )}
    </article>
  );
}
export function CompanionDevices({
  userId,
  admin = false,
  readOnly = false,
  owners,
}: {
  userId: number;
  admin?: boolean;
  readOnly?: boolean;
  owners?: Record<number, string>;
}) {
  const [includeArchived, setIncludeArchived] = useState(false);
  const devices = useCompanionDevices(userId, admin, admin, includeArchived),
    [shown, setShown] = useState(10);
  return (
    <section
      className="panel padded companion-devices"
      aria-label={
        admin ? "Registered desktop companions" : "My desktop companions"
      }
    >
      <div className="panel-heading">
        <div>
          <h2>{admin ? "Desktop companions" : "Your desktop companions"}</h2>
          <p className="muted">
            Browser-approved connections. Revoking access keeps existing market
            history and the PC’s offline cache. Authorized does not mean online. Last connection records an authenticated request. Archive revoked entries to hide them while retaining security evidence.
          </p>
        </div>
        <button
          className="secondary"
          onClick={() => devices.refetch()}
          disabled={devices.isFetching}
        >
          Refresh devices
        </button>
      </div>
      <label className="checkbox"><input type="checkbox" checked={includeArchived} onChange={e => setIncludeArchived(e.target.checked)}/>Include archived entries</label>
      {devices.isPending && <p role="status">Loading your connections…</p>}
      {devices.error && (
        <p className="notice error" role="alert">
          {devices.error.message}{" "}
          <button className="text-button" onClick={() => devices.refetch()}>
            Try again
          </button>
        </p>
      )}
      {devices.data?.devices.length === 0 && (
        <p className="empty">
          No companion registrations to display. Open Get Desktop Companion to set up this
          PC.
        </p>
      )}
      {admin ? <DataTable<CompanionDevice> label="desktop companions" filters={[{id:"status",label:"Filter desktop connection",options:[{value:"Authorized",label:"Authorized"},{value:"Expired",label:"Expired"},{value:"Revoked",label:"Revoked"}]}]} data={devices.data?.devices || []} getRowId={row=>String(row.id)} loading={devices.isPending} error={devices.error?.message} columns={[
        {accessorKey:"name",header:"Device",enableHiding:false},
        {id:"owner",header:"Account",accessorFn:row=>owners?.[row.user_id]||`#${row.user_id}`},
        {accessorKey:"app_version",header:"Version / platform",cell:({row})=>`${row.original.app_version} · ${row.original.platform}`},
        {accessorKey:"selected_market_name",header:"Selected market",cell:({row})=>row.original.selected_market_name||"Not selected"},
        {accessorKey:"last_connection_at",header:"Last seen",cell:({row})=><LocalTime value={row.original.last_connection_at}/>},
        {accessorKey:"last_sync_at",header:"Last successful sync",cell:({row})=><LocalTime value={row.original.last_sync_at}/>},
        {id:"status",header:"Connection",accessorFn:row=>row.revoked?"Revoked":new Date(row.expires_at).getTime()<=Date.now()||Boolean(row.renewal_expires_at&&new Date(row.renewal_expires_at).getTime()<=Date.now())?"Expired":"Authorized",cell:({getValue})=><Status>{String(getValue())}</Status>},
      ]} renderDetails={device=><DeviceCard device={device} userId={userId} admin readOnly={readOnly} owner={owners?.[device.user_id]}/>}/> : devices.data?.devices.slice(0, shown).map((device) => (
        <DeviceCard key={device.id} device={device} userId={userId} admin={false} readOnly={readOnly} />
      ))}
      {!admin && (devices.data?.devices.length || 0) > shown && (
        <button
          className="secondary"
          onClick={() => setShown((value) => value + 10)}
        >
          Show more devices
        </button>
      )}
    </section>
  );
}
