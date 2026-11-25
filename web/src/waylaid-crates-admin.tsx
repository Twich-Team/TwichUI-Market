import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "./api";
import { LocalTime, Status } from "./admin-table";
import { Loading } from "./loading";
import { onPrivateCacheClear } from "./query";
import { CrateAttribution } from "./waylaid-attribution";
import { parseFavor, tierLabel, type CrateCatalogue } from "./waylaid-crates-data";
import "./waylaid-crates.css";

interface CrateReward {
  tier: string;
  favor: number | null;
  revision: number;
  updated_at: string | null;
  updated_by: string | null;
}

interface CatalogueRefresh {
  state: string;
  error: string | null;
  next_attempt_at: string | null;
}

interface CrateAdminData {
  catalogue: CrateCatalogue;
  rewards: CrateReward[];
  refresh: CatalogueRefresh;
}

const adminPath = "/admin/waylaid-crates";
const adminKey = ["private", "waylaid-crates-admin"];

export function WaylaidCratesAdmin({ readOnly }: { readOnly: boolean }) {
  const client = useQueryClient();
  const request = useRef<AbortController | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState("");
  const [refreshError, setRefreshError] = useState("");
  const result = useQuery({
    queryKey: adminKey,
    queryFn: ({ signal }) => api<CrateAdminData>(adminPath, "GET", undefined, signal),
    refetchInterval: query => ["queued", "running", "retry"].includes(query.state.data?.refresh.state ?? "") ? 5_000 : 60_000,
    retry: false,
  });
  useEffect(() => {
    const controller = new AbortController();
    request.current = controller;
    const stop = onPrivateCacheClear(() => controller.abort());
    return () => { stop(); controller.abort(); };
  }, []);

  async function queueRefresh() {
    const signal = request.current?.signal;
    if (readOnly || refreshing || !signal) return;
    setRefreshing(true);
    setRefreshError("");
    setMessage("");
    try {
      const refresh = await api<CatalogueRefresh>(adminPath + "/refresh", "POST", undefined, signal);
      if (signal.aborted) return;
      await client.cancelQueries({ queryKey: adminKey });
      if (signal.aborted) return;
      client.setQueryData<CrateAdminData>(adminKey, old => old && { ...old, refresh });
      setMessage(["queued", "running", "retry"].includes(refresh.state)
        ? "Catalogue refresh queued. The worker will process it in the background."
        : "Catalogue refresh request accepted. See the current refresh state below.");
      await result.refetch();
    } catch (error) {
      if (!signal.aborted) setRefreshError((error as Error).message);
    } finally {
      if (!signal.aborted) setRefreshing(false);
    }
  }

  async function saveReward(reward: CrateReward, favor: number | null, revision: number) {
    const signal = request.current?.signal;
    if (!signal || readOnly) throw new Error("Reward editing is unavailable.");
    const saved = await api<CrateReward>(`${adminPath}/rewards/${encodeURIComponent(reward.tier)}`, "PUT", { favor, revision }, signal);
    if (signal.aborted) return;
    await client.cancelQueries({ queryKey: adminKey });
    if (signal.aborted) return;
    client.setQueryData<CrateAdminData>(adminKey, old => old && {
      ...old, rewards: old.rewards.map(row => row.tier === saved.tier && row.revision <= saved.revision ? saved : row),
    });
    void client.invalidateQueries({ queryKey: ["private", "waylaid-crates"] });
  }

  const data = result.data;
  const active = data && ["queued", "running", "retry"].includes(data.refresh.state);
  const stale = data && result.isError;
  return <div className="waylaid-page">
    <div className="waylaid-heading">
      <div><h1>Waylaid Crates</h1><p>Manage Merchant’s Favor rewards and the local ForeverDB crate catalogue.</p></div>
      <button className="secondary" disabled={result.isFetching} onClick={() => void result.refetch()}>Refresh status</button>
    </div>
    {result.isPending && <Loading label="Loading Waylaid Crates settings…" skeleton/>}
    {result.error && <p className="notice error" role="alert">Waylaid Crates settings could not be refreshed.
      {data && " Showing the last loaded settings."} <button onClick={() => void result.refetch()}>Retry settings</button>
    </p>}
    {data && <>
      <section className="panel waylaid-admin-panel" aria-labelledby="waylaid-catalogue-title">
        <div className="panel-heading">
          <div><h2 id="waylaid-catalogue-title">Crate catalogue</h2><CrateAttribution catalogue={data.catalogue}/></div>
          <button className="primary" disabled={readOnly || !!active || refreshing || !!stale} onClick={() => void queueRefresh()}>
            {refreshing ? "Queueing refresh…" : "Queue catalogue refresh"}
          </button>
        </div>
        <dl className="waylaid-catalogue-facts">
          <div><dt>Local catalogue</dt><dd><Status tone={data.catalogue.stale ? "warning" : data.catalogue.refreshed_at ? "success" : "neutral"}>
            {data.catalogue.refreshed_at ? (data.catalogue.stale ? "Stale" : "Current") : "Unavailable"}
          </Status></dd></div>
          <div><dt>Last successful refresh</dt><dd><LocalTime value={data.catalogue.refreshed_at}/></dd></div>
          <div><dt>Supported crates</dt><dd>{data.catalogue.supported_count.toLocaleString()} of {data.catalogue.crate_count.toLocaleString()}</dd></div>
          <div><dt>Refresh state</dt><dd><Status tone={data.refresh.error ? "warning" : "neutral"}>
            {data.refresh.state ? tierLabel(data.refresh.state) : "Unknown"}
          </Status></dd></div>
          {data.refresh.next_attempt_at && <div><dt>Next refresh attempt</dt><dd><LocalTime value={data.refresh.next_attempt_at}/></dd></div>}
        </dl>
        {data.refresh.error && <p className="notice warning" role="status">{data.refresh.error}</p>}
        {refreshError && <p className="notice error" role="alert">{refreshError}</p>}
        {message && <p className="notice success" role="status">{message}</p>}
      </section>
      <section className="panel waylaid-admin-panel" aria-labelledby="waylaid-rewards-title">
        <div className="panel-heading"><div>
          <h2 id="waylaid-rewards-title">Merchant’s Favor rewards</h2>
          <p className="small muted">Set a positive whole number for each Common crate tier. Leave a tier blank to mark it as unconfigured. Favor for other crate qualities is unavailable.</p>
        </div></div>
        {data.rewards.map(reward => <RewardEditor key={reward.tier} reward={reward} disabled={readOnly || !!stale}
          save={saveReward} reload={async () => { await result.refetch({ throwOnError: true }); }}/>)}
      </section>
    </>}
  </div>;
}

function RewardEditor({ reward, disabled, save, reload }: {
  reward: CrateReward;
  disabled: boolean;
  save: (reward: CrateReward, favor: number | null, revision: number) => Promise<void>;
  reload: () => Promise<void>;
}) {
  const [draft, setDraft] = useState<{ text: string; revision: number }>();
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const title = tierLabel(reward.tier);
  const text = draft?.text ?? String(reward.favor ?? "");
  const favor = parseFavor(text);

  async function submit() {
    if (disabled || busy || conflict || !draft) return;
    if (favor === undefined) {
      setError("Enter a positive whole number or leave this field blank.");
      return;
    }
    setBusy(true);
    setMessage("");
    setError("");
    try {
      await save(reward, favor, draft.revision);
      setDraft(undefined);
      setMessage(favor === null ? `${title} is now unconfigured.` : `${title} reward saved.`);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        setConflict(true);
        setError("This reward changed while you were editing. Load the latest value before editing again.");
      } else {
        setError((caught as Error).message);
      }
    } finally {
      setBusy(false);
    }
  }

  async function loadLatest() {
    setBusy(true);
    try {
      await reload();
      setDraft(undefined);
      setConflict(false);
      setError("");
      setMessage(`Latest ${title} reward loaded.`);
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return <form className="waylaid-reward" onSubmit={event => { event.preventDefault(); void submit(); }}>
    <div>
      <h3>{title}</h3>
      <p className="small muted">{reward.favor === null ? "Unconfigured" : `${reward.favor.toLocaleString()} Favor per crate`}</p>
      {reward.updated_at && <p className="small muted">Updated <LocalTime value={reward.updated_at}/>{reward.updated_by && ` by ${reward.updated_by}`}</p>}
    </div>
    <label>Favor per crate <span className="sr-only">for {title}</span>
      <input type="text" inputMode="numeric" value={text} placeholder="Unconfigured" maxLength={10}
        disabled={disabled || busy || conflict} aria-invalid={favor === undefined || undefined}
        onChange={event => {
          setDraft({ text: event.target.value, revision: draft?.revision ?? reward.revision });
          setMessage("");
          setError("");
        }}/>
    </label>
    {conflict
      ? <button type="button" className="secondary" disabled={busy} onClick={() => void loadLatest()}>Load latest {title} reward</button>
      : <button className="secondary" disabled={disabled || busy || !draft || favor === reward.favor}>Save {title} reward</button>}
    {error && <p className="notice error" role="alert">{error}</p>}
    {message && <p className="small" role="status">{message}</p>}
  </form>;
}
