import { useState } from "react";
import { useLoad } from "./research";
import { api } from "./api";
import { DataTable } from "./data-table";
interface Policy {
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
}
interface Preview {
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
const size = (v: number | null) =>
  v === null ? "Unknown" : `${(v / 1048576).toFixed(2)} MiB`;
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
      <p>
        Configure a proposal, preview its impact, then confirm a bounded batch
        after owner approval and a verified backup restoration.
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
