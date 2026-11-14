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
) {
  return useQuery({
    queryKey: deviceKey(userId, admin),
    queryFn: ({ signal }) =>
      api<DeviceList>(
        admin ? "/companion/admin/devices" : "/companion/devices",
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
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const expired =
    new Date(device.expires_at).getTime() <= Date.now() ||
    Boolean(
      device.renewal_expires_at &&
        new Date(device.renewal_expires_at).getTime() <= Date.now(),
    );
  async function act(operation: "rename" | "revoke") {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (operation === "rename")
        await api(`/companion/devices/${device.id}`, "PATCH", {
          name: draft.trim(),
        });
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
      setMessage(
        operation === "rename"
          ? "Device renamed."
          : "Access revoked. Offline data on that PC is preserved.",
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
              : "Connected"}
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
          {!admin && (
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
  const devices = useCompanionDevices(userId, admin),
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
            history and the PC’s offline cache.
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
          No companion connected yet. Open Get Desktop Companion to set up this
          PC.
        </p>
      )}
      {devices.data?.devices.slice(0, shown).map((device) => (
        <DeviceCard
          key={device.id}
          device={device}
          userId={userId}
          admin={admin}
          readOnly={admin && readOnly}
          owner={owners?.[device.user_id]}
        />
      ))}
      {(devices.data?.devices.length || 0) > shown && (
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
