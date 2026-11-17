import { ConfirmationDialog } from "./confirmation-dialog";
import { useState } from "react";
import { api, type User } from "./api";

export function MemberArchive({ member, disabled, run }: { member: User; disabled: boolean; run: (job: () => Promise<void>) => void }) {
  const [confirm, setConfirm] = useState(false), [name, setName] = useState("");
  if (member.archived_at) return <button className="secondary" disabled={disabled} onClick={() => run(async () => { await api(`/admin/users/${member.id}/restore`, "POST"); })}>Restore listing</button>;
  return <div>
    <button className="secondary" disabled={disabled} onClick={() => setConfirm(true)}>Archive account</button>
    {confirm && <ConfirmationDialog title={`Archive ${member.username}?`} onClose={() => setConfirm(false)}>
      <p>Archive <strong>{member.username}</strong>? This disables sign-in, revokes all sessions and devices, and hides the account from ordinary lists. Audit evidence, preferences and owned records are retained. This is reversible; permanent deletion is unavailable.</p>
      <label>Type {member.username} to confirm<input value={name} onChange={e => setName(e.target.value)} autoComplete="off" /></label>
      <button className="primary" disabled={disabled || name !== member.username} onClick={() => run(async () => { await api(`/admin/users/${member.id}/archive`, "POST", { confirmation: name }); setConfirm(false); setName(""); })}>Confirm archive</button>
      <button className="text-button" disabled={disabled} onClick={() => setConfirm(false)}>Cancel</button>
    </ConfirmationDialog>}
  </div>;
}
