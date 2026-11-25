import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "./api";
import { LocalTime, Status } from "./admin-table";
import { ItemIcon } from "./item-components";
import { ItemName } from "./item-name";
import { Loading } from "./loading";
import { supportedId } from "./navigation";
import { onPrivateCacheClear } from "./query";
import { tierLabel } from "./waylaid-crates-data";
import { rewardSourceLabel, writQueryKey, type RewardSource, type WritCatalogue, type WritItem } from "./crafting-writs-data";
import { WritAttribution, WritItemAttribution } from "./crafting-writs-details";
import "./waylaid-crates.css";
import "./crafting-writs.css";

interface RewardSetting {
  key: string;
  reputation: number | null;
  revision: number;
  updated_at: string | null;
  updated_by: string | null;
}

interface WritReward extends RewardSetting {
  item: WritItem;
  tier: string | null;
  quest_id: number;
  provider_reputation: number | null;
  effective_reputation: number | null;
  reward_source: RewardSource;
}

interface CatalogueRefresh {
  state: string;
  error: string | null;
  next_attempt_at: string | null;
  last_finished_at?: string | null;
  operation: "catalogue" | "metadata_backfill";
}

interface WritAdminData {
  catalogue: WritCatalogue;
  tiers: RewardSetting[];
  writs: WritReward[];
  refresh: CatalogueRefresh;
}

const adminPath = "/admin/crafting-writs";
const adminKey = ["private", "crafting-writs-admin"];
const activeRefresh = ["queued", "running", "retry"];

export function CraftingWritsAdmin({ readOnly }: { readOnly: boolean }) {
  const client = useQueryClient();
  const request = useRef<AbortController | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState("");
  const [refreshError, setRefreshError] = useState("");
  const result = useQuery({
    queryKey: adminKey,
    queryFn: ({ signal }) => api<WritAdminData>(adminPath, "GET", undefined, signal),
    refetchInterval: query => activeRefresh.includes(query.state.data?.refresh.state ?? "") ? 5_000 : 60_000,
    retry: false,
  });
  useEffect(() => {
    const controller = new AbortController();
    request.current = controller;
    const stop = onPrivateCacheClear(() => controller.abort());
    return () => { stop(); controller.abort(); };
  }, []);

  const data = result.data;
  const enabled = !readOnly && !result.isError;
  const pendingRefresh = data && activeRefresh.includes(data.refresh.state);
  const backfill = data?.refresh.operation === "metadata_backfill";

  async function queueRefresh() {
    const signal = request.current?.signal;
    if (!enabled || refreshing || !signal) return;
    setRefreshing(true);
    setRefreshMessage("");
    setRefreshError("");
    try {
      const refresh = await api<CatalogueRefresh>(adminPath + "/refresh", "POST", undefined, signal);
      if (signal.aborted) return;
      await client.cancelQueries({ queryKey: adminKey });
      if (signal.aborted) return;
      client.setQueryData<WritAdminData>(adminKey, previous => previous && { ...previous, refresh });
      setRefreshMessage(backfill ? "Item metadata refresh queued." : "Catalogue refresh queued.");
      await result.refetch();
    } catch (error) {
      if (!signal.aborted) setRefreshError((error as Error).message);
    } finally {
      if (!signal.aborted) setRefreshing(false);
    }
  }

  async function saveReward(scope: "tier" | "writ", key: string, reputation: number | null, revision: number) {
    const signal = request.current?.signal;
    if (!enabled || !signal) throw new Error("Reward editing is unavailable.");
    const saved = await api<RewardSetting>(`${adminPath}/rewards/${scope}/${encodeURIComponent(key)}`, "PUT", { reputation, revision }, signal);
    if (signal.aborted) return;
    client.setQueryData<WritAdminData>(adminKey, previous => previous && ({
      ...previous,
      ...(scope === "tier"
        ? { tiers: previous.tiers.map(row => row.key === key && row.revision < saved.revision ? saved : row) }
        : { writs: previous.writs.map(row => row.key === key && row.revision < saved.revision ? { ...row, ...saved } : row) }),
    }));
    void client.invalidateQueries({ queryKey: writQueryKey });
    await client.invalidateQueries({ queryKey: adminKey });
  }

  const reload = async () => { await result.refetch({ throwOnError: true }); };
  return <div className="waylaid-page writ-page">
    <div className="waylaid-heading">
      <div><h1>Crafting Writs</h1><p>Manage base reputation rewards and review the local writ catalogue.</p></div>
      <button className="secondary" disabled={result.isFetching} onClick={() => void result.refetch()}>Refresh status</button>
    </div>
    {result.isPending && <Loading label="Loading Crafting Writs settings…" skeleton/>}
    {result.error && <p className="notice error" role="alert">
      Crafting Writs settings could not be refreshed.{data && " Showing the last loaded settings."}
      {" "}<button onClick={() => void result.refetch()}>Retry settings</button>
    </p>}
    {data && <>
      <section className="panel waylaid-admin-panel" aria-labelledby="writ-catalogue-title">
        <div className="panel-heading">
          <div><h2 id="writ-catalogue-title">Writ catalogue</h2><WritAttribution catalogue={data.catalogue} items={data.writs.map(row => row.item)}/></div>
          <button className="primary" disabled={!enabled || pendingRefresh || refreshing} onClick={() => void queueRefresh()}>
            {refreshing ? "Queueing refresh…" : backfill ? "Refresh item metadata" : "Queue catalogue refresh"}
          </button>
        </div>
        <dl className="waylaid-catalogue-facts">
          <div><dt>Local catalogue</dt><dd><Status tone={data.catalogue.stale ? "warning" : data.catalogue.writ_count ? "success" : "neutral"}>
            {data.catalogue.stale ? "Stale" : data.catalogue.writ_count ? "Available" : "Unavailable"}
          </Status></dd></div>
          <div><dt>Last successful catalogue refresh</dt><dd>{data.catalogue.refreshed_at
            ? <LocalTime value={data.catalogue.refreshed_at}/> : "Unconfirmed"}</dd></div>
          <div><dt>Supported writs</dt><dd>{data.catalogue.supported_count.toLocaleString()} of {data.catalogue.writ_count.toLocaleString()}</dd></div>
          <div><dt>Writs without a verified route</dt><dd>{data.catalogue.incomplete_count.toLocaleString()}</dd></div>
          <div><dt>Writs with partial coverage</dt><dd>{data.catalogue.partial_count.toLocaleString()}</dd></div>
          <div><dt>{backfill ? "Item metadata refresh state" : "Catalogue refresh state"}</dt><dd>
            <Status tone={data.refresh.error ? "warning" : "neutral"}>{tierLabel(data.refresh.state || "unknown")}</Status>
          </dd></div>
          {backfill && data.refresh.last_finished_at && <div><dt>Last item metadata refresh</dt><dd><LocalTime value={data.refresh.last_finished_at}/></dd></div>}
          {data.refresh.next_attempt_at && <div><dt>Next refresh attempt</dt><dd><LocalTime value={data.refresh.next_attempt_at}/></dd></div>}
        </dl>
        {data.refresh.error && <p className="notice warning" role="status">{data.refresh.error}</p>}
        {refreshError && <p className="notice error" role="alert">{refreshError}</p>}
        {refreshMessage && <p className="notice success" role="status">{refreshMessage}</p>}
      </section>
      <section className="panel waylaid-admin-panel" aria-labelledby="writ-tier-title">
        <div className="panel-heading"><div>
          <h2 id="writ-tier-title">Reputation by tier</h2>
          <p className="small muted">Enter a positive whole number. Leave a tier blank to use any verified provider reward.</p>
        </div></div>
        {data.tiers.map(reward => <RewardEditor key={reward.key} setting={reward} title={tierLabel(reward.key)} disabled={!enabled}
          save={(value, revision) => saveReward("tier", reward.key, value, revision)} reload={reload}/>)}
        {!data.tiers.length && <p className="empty">No verified writ tiers are available.</p>}
      </section>
      <section className="panel waylaid-admin-panel" aria-labelledby="writ-override-title">
        <div className="panel-heading"><div>
          <h2 id="writ-override-title">Per-writ overrides</h2>
          <p className="small muted">Leave an override blank to inherit the tier setting or verified provider reward.</p>
        </div></div>
        {data.writs.map(reward => <RewardEditor key={reward.key} setting={reward} title={reward.item.name} disabled={!enabled} override
          save={(value, revision) => saveReward("writ", reward.key, value, revision)} reload={reload}
          heading={<span className="writ-admin-identity"><ItemIcon item={reward.item}/><ItemName name={reward.item.name} quality={reward.item.quality} highContrast/></span>}>
          <WritItemAttribution item={reward.item}/>
          <p className="small muted">{reward.tier && <>{tierLabel(reward.tier)} · </>}Quest #{reward.quest_id}</p>
          <p className="small muted">Effective reward {reward.effective_reputation?.toLocaleString() ?? "unknown"} · {rewardSourceLabel(reward.reward_source)}</p>
          <p className={reward.provider_reputation != null && reward.provider_reputation !== reward.effective_reputation ? "waylaid-estimate small" : "small muted"}>
            Provider reward {reward.provider_reputation?.toLocaleString() ?? "unknown"}
            {reward.provider_reputation != null && reward.provider_reputation !== reward.effective_reputation && " · differs from effective reward"}
          </p>
        </RewardEditor>)}
        {!data.writs.length && <p className="empty">No verified writs are available for overrides.</p>}
      </section>
    </>}
  </div>;
}

function RewardEditor({ setting, title, heading, children, disabled, override, save, reload }: {
  setting: RewardSetting; title: string; heading?: ReactNode; children?: ReactNode; disabled: boolean; override?: boolean;
  save: (value: number | null, revision: number) => Promise<void>; reload: () => Promise<void>;
}) {
  const [draft, setDraft] = useState<{ text: string; revision: number }>();
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const text = draft?.text ?? String(setting.reputation ?? "");
  const reward = text.trim() ? supportedId(text.trim()) ?? undefined : null;

  async function submit() {
    if (disabled || busy || conflict || !draft) return;
    if (reward === undefined) {
      setError("Enter a positive whole number or leave this field blank.");
      return;
    }
    setBusy(true);
    setMessage("");
    setError("");
    try {
      await save(reward, draft.revision);
      setDraft(undefined);
      setMessage(reward === null ? "Saved. This reward now inherits its fallback." : "Reputation reward saved.");
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
      setMessage("Latest reward loaded.");
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return <form className="waylaid-reward" onSubmit={event => { event.preventDefault(); void submit(); }}>
    <div>
      <h3>{heading ?? title}</h3>
      {!override && <p className="small muted">{setting.reputation === null ? "Unconfigured" : `${setting.reputation.toLocaleString()} reputation per writ`}</p>}
      {children}
      {setting.updated_at && <p className="small muted">Updated <LocalTime value={setting.updated_at}/>{setting.updated_by && ` by ${setting.updated_by}`}</p>}
    </div>
    <label>{override ? "Reputation override" : "Reputation per writ"} <span className="sr-only">for {title}</span>
      <input type="text" inputMode="numeric" value={text} placeholder={override ? "Inherited" : "Unconfigured"} maxLength={10}
        disabled={disabled || busy || conflict} aria-invalid={reward === undefined || undefined}
        onChange={event => {
          setDraft({ text: event.target.value, revision: draft?.revision ?? setting.revision });
          setMessage("");
          setError("");
        }}/>
    </label>
    {conflict
      ? <button type="button" className="secondary" disabled={busy} aria-label={`Load latest reward for ${title}`}
        onClick={() => void loadLatest()}>Load latest</button>
      : <button className="secondary" aria-label={`Save reward for ${title}`}
        disabled={disabled || busy || !draft || (reward === setting.reputation && draft.revision === setting.revision)}>Save reward</button>}
    {error && <p className="notice error" role="alert">{error}</p>}
    {message && <p className="small" role="status">{message}</p>}
  </form>;
}
