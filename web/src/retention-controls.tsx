import { LocalTime } from "./admin-table";
import { Loading } from "./loading";
import { formatBytes as size } from "./size";
import { useState } from "react";
import { useLoad } from "./research";
import { api } from "./api";
import { DataTable } from "./data-table";
interface Automation {
  installed:boolean; enabled:boolean; authorized:boolean; next_run_at:string|null; last_success_at:string|null; paused_reason:string|null; rows_by_stage:Record<string,number>; last_run:{status:string;reason:string|null;batches:number;rows_processed:number}|null; recovery_notice:string; proposal:{execution_hash:string;policy_revision:number};
}
interface Policy {
  automation?:Automation;
  revision:number; policy_hash:string;
  policy_configured: boolean;
  scheduled: boolean;
  completed_batches: number;
  raw_days: number;
  intraday_days: number;
  daily_days: number;
  operational_days: number;
  security_days: number;
  application_authorized: boolean;
  backup_restore_ready: boolean;
  notice: string;
}
interface Stage {
  stage: string;
  eligible_rows: number;
  estimated_logical_bytes: number | null;
  oldest_affected_at?:string|null; newest_affected_at?:string|null; protected_rows_estimate?:number|null;
}
interface Preview {
  cutoffs?:Record<string,string>;
  protected?:string; history_sync_impact?:string;
  stages: Stage[];
  confirmation: string;
  next_stage: string | null;
  next_batch_rows: number;
  estimate_notice: string;
  estimated_logical_bytes: number;
}
const fields = [
  ["raw_days", "Raw auction listings"],
  ["intraday_days", "Intraday statistics and observations"],
  ["daily_days", "Daily market history"],
  ["operational_days", "Collection logs"],
  ["security_days", "Security logs"],
] as const;

export function RetentionControls({ readOnly }: { readOnly: boolean }) {
  const state = useLoad(
    "retention-policy",
    () => api<Policy>("/admin/retention"),
    [],
  );
  const [preview, setPreview] = useState<Preview | null>(null),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [confirmed, setConfirmed] = useState(false);
  async function run(job: () => Promise<void>) {
    setError("");
    setMessage("");
    setBusy(true);
    try {
      await job();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel padded">
      <h3>Historical retention policy</h3>
      {busy && <Loading label="Preparing retention operation…"/>}
      <p>
        Configure a policy and preview its impact. Automatic maintenance requires separate owner authorization for the exact policy and work limits, followed by enablement. Saving or starting the service never authorizes deletion.
      </p>
      {(error || state.error) && (
        <p role="alert" className="notice error">
          {error || state.error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {state.data && (
        <>
          <form
            key={JSON.stringify(state.data)}
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              run(async () => {
                const body = Object.fromEntries(
                  fields.map(([key]) => [key, Number(form.get(key))]),
                );
                await api("/admin/retention", "PATCH", body);
                setPreview(null);
                setConfirmed(false);
                state.refresh();
                setMessage(
                  "Policy proposal saved. Application authorization was cleared.",
                );
              });
            }}
          >
            {fields.map(([key, label]) => (
              <label key={key}>
                {label}
                <select name={key} defaultValue={state.data![key]}>
                  {[
                    ...new Set([
                      7,
                      30,
                      64,
                      90,
                      180,
                      365,
                      730,
                      1825,
                      3650,
                      state.data![key],
                    ]),
                  ]
                    .filter(
                      (days) =>
                        days >=
                        (key === "intraday_days"
                          ? 64
                          : key === "daily_days"
                            ? 90
                            : key === "security_days"
                              ? 30
                              : key === "operational_days"
                                ? 7
                                : 1),
                    )
                    .sort((a, b) => a - b)
                    .map((days) => (
                      <option value={days} key={days}>
                        {days === 180
                          ? "Six months (180 days)"
                          : days === 365
                            ? "One year (365 days)"
                            : `${days} days`}
                      </option>
                    ))}
                </select>
              </label>
            ))}
            <button className="secondary" disabled={readOnly || busy}>
              Save policy proposal
            </button>
          </form>
          <dl className="stats">
            <div><dt>Policy</dt><dd>{state.data.policy_configured ? "Configured" : "Default proposal; not saved"}</dd></div>
            <div><dt>Authorization</dt><dd>{state.data.application_authorized ? "Approved for this exact policy" : "Owner approval pending"}</dd></div>
            <div><dt>Destructive batches</dt><dd>{state.data.application_authorized && state.data.backup_restore_ready ? "Ready for explicit batch confirmation" : "Disabled"}</dd></div>
            <div><dt>Maintenance</dt><dd>{state.data.automation?.enabled ? "Schedule enabled" : "Not scheduled"} · {state.data.completed_batches} completed batches</dd></div>
          </dl>
          {state.data.automation&&<section aria-label="Automatic historical maintenance">
            <h4>Automatic historical maintenance</h4>
            <dl className="stats">
              <div><dt>Service</dt><dd>{state.data.automation.installed?'Installed':'Not installed'}</dd></div>
              <div><dt>Automatic authorization</dt><dd>{state.data.automation.authorized?'Approved for exact policy, scope and limits':'Owner approval pending'}</dd></div>
              <div><dt>Last successful maintenance</dt><dd><LocalTime value={state.data.automation.last_success_at}/></dd></div>
              <div><dt>Next planned maintenance</dt><dd><LocalTime value={state.data.automation.next_run_at}/></dd></div>
              <div><dt>Current state</dt><dd>{state.data.automation.paused_reason||state.data.automation.last_run?.status||'Ready'}</dd></div>
            </dl>
            <p className="small muted">{state.data.automation.recovery_notice}</p>
            <ul>{Object.entries(state.data.automation.rows_by_stage).map(([stage,rows])=><li key={stage}>{stage.replaceAll('_',' ')}: {rows.toLocaleString()} rows processed</li>)}</ul>
            <button className="secondary" disabled={readOnly||busy||(!state.data.automation.enabled&&!state.data.automation.authorized)} onClick={()=>run(async()=>{await api('/admin/retention/automation','PATCH',{enabled:!state.data!.automation!.enabled});state.refresh();})}>{state.data.automation.enabled?'Pause automatic maintenance':'Enable authorized maintenance'}</button>
            <details><summary>Exact policy identity</summary><p>Revision {state.data.revision}</p><p className="small" style={{overflowWrap:'anywhere'}}>Policy: {state.data.policy_hash}<br/>Execution proposal: {state.data.automation.proposal.execution_hash}</p></details>
          </section>}
          <p className="notice">
            {state.data.notice} Live application{" "}
            {state.data.application_authorized
              ? "authorized for this exact policy"
              : "disabled pending owner approval"}
            . Backup and restore{" "}
            {state.data.backup_restore_ready
              ? "verified recently"
              : "verification required"}
            .
          </p>
        </>
      )}
      <button
        className="secondary"
        disabled={busy}
        onClick={() =>
          run(async () => {
            setPreview(await api<Preview>("/admin/retention/preview"));
            setConfirmed(false);
          })
        }
      >
        Preview retention impact
      </button>
      {preview && (
        <>
          <p role="status">
            Dry run · estimated logical impact{" "}
            {size(preview.estimated_logical_bytes)}. Next batch:{" "}
            {preview.next_batch_rows.toLocaleString()} rows.
          </p>
          <p className="small muted">{preview.estimate_notice}</p>
          {preview.cutoffs&&<details open><summary>Historical cutoffs (UTC)</summary><dl>{Object.entries(preview.cutoffs).map(([key,value])=><div key={key}><dt>{key.replaceAll('_',' ')}</dt><dd>{value}</dd></div>)}</dl><p>{preview.protected}</p><p>{preview.history_sync_impact}</p></details>}
          <DataTable<Stage>
            label="retention preview"
            data={preview.stages}
            getRowId={row=>row.stage}
            columns={[
              {
                accessorKey: "stage",
                header: "Stage",
                cell: ({ row }) => row.original.stage.replaceAll("_", " "),
              },
              {
                accessorKey: "eligible_rows",
                header: "Eligible rows",
                meta: { numeric: true },
                cell: ({ row }) => row.original.eligible_rows.toLocaleString(),
              },
              {accessorKey:"oldest_affected_at",header:"Oldest affected",cell:({row})=>row.original.oldest_affected_at||'None'},
              {accessorKey:"newest_affected_at",header:"Newest affected",cell:({row})=>row.original.newest_affected_at||'None'},
              {
                accessorKey: "estimated_logical_bytes",
                header: "Estimated logical impact",
                meta: { numeric: true },
                cell: ({ row }) => size(row.original.estimated_logical_bytes),
              },
            ]}
          />
          <label className="checkbox">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              disabled={readOnly || !state.data?.application_authorized}
            />
            I confirm permanent removal of the previewed batch after backup
            verification.
          </label>
          <button
            className="secondary"
            disabled={
              readOnly ||
              busy ||
              !confirmed ||
              !state.data?.application_authorized ||
              !state.data?.backup_restore_ready ||
              !preview.next_stage
            }
            onClick={() =>
              run(async () => {
                const result = await api<{ rows_removed: number }>(
                  "/admin/retention/apply",
                  "POST",
                  { confirmation: preview.confirmation, confirm: true },
                );
                setPreview(null);
                setConfirmed(false);
                setMessage(
                  `Removed ${result.rows_removed} rows. Preview again to continue.`,
                );
              })
            }
          >
            Apply confirmed batch
          </button>
        </>
      )}
    </section>
  );
}
