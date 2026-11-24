export interface BackupFilters {
  search: string;
  storage: string;
  protection: string;
  verified: string;
  backupType: string;
  sort: string;
}

export function backupQueryParams(offset: number, filters?: BackupFilters, limit = 100) {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  if (filters?.search) params.set('search', filters.search);
  if (filters?.storage && filters.storage !== 'all') params.set('storage_id', filters.storage);
  if (filters?.protection && filters.protection !== 'all') params.set('protection', filters.protection);
  if (filters?.verified && filters.verified !== 'all') params.set('verification', filters.verified);
  if (filters?.backupType && filters.backupType !== 'all') params.set('backup_type', filters.backupType);
  if (filters?.sort && filters.sort !== 'created_desc') params.set('sort', filters.sort);
  return params;
}

interface ReliabilityCounts {
  successes: number;
  failures: number;
}

export function utcBackupDay(value: string | Date) {
  const timestamp = typeof value === 'string' ? Date.parse(value) : value.getTime();
  return Number.isFinite(timestamp) ? new Date(timestamp).toISOString().slice(0, 10) : '';
}

export function reliabilityCounts(
  items: { created_at: string | null; verification: string }[],
  receipts: { at: string; action: string }[],
  recorded?: { day: string; succeeded: number; failed: number }[],
) {
  if (recorded) return new Map(recorded.map(day => [day.day, { successes: day.succeeded, failures: day.failed }]));
  const counts = new Map<string, ReliabilityCounts>();
  for (const row of items) {
    if (!row.created_at || row.verification !== 'archive_integrity_verified') continue;
    const day = utcBackupDay(row.created_at);
    if (!day) continue;
    const count = counts.get(day) ?? { successes: 0, failures: 0 };
    counts.set(day, { ...count, successes: count.successes + 1 });
  }
  for (const receipt of receipts) {
    if (!['backup.failed', 'backup.creation.failed'].includes(receipt.action)) continue;
    const day = utcBackupDay(receipt.at);
    if (!day) continue;
    const count = counts.get(day) ?? { successes: 0, failures: 0 };
    counts.set(day, { ...count, failures: count.failures + 1 });
  }
  return counts;
}

export type BackupOutcome = 'mixed' | 'success' | 'failed' | 'unknown';

export function backupOutcome(day: string, today: string, counts: Map<string, ReliabilityCounts>): BackupOutcome {
  const count = day <= today ? counts.get(day) : undefined;
  if (count?.successes && count.failures) return 'mixed';
  if (count?.successes) return 'success';
  return count?.failures ? 'failed' : 'unknown';
}

interface BackupProtection {
  protected: boolean;
  keep_flag?: boolean;
  recovery_pin?: boolean;
  type: string;
  origin: string;
  reason: string;
  required_by: string[];
  active_use?: boolean;
  verification: string;
}

export function backupKeepFlag(row: BackupProtection) {
  // Older managers only report the effective protection state.
  const set = row.keep_flag ?? row.protected;
  const label = set ? 'Remove keep flag' : 'Set keep flag';
  const blocked = row.type === 'legacy' || row.verification !== 'archive_integrity_verified'
    ? 'Changing the keep flag requires a verified, managed archive.'
    : row.required_by.length ? 'A recovery reservation blocks changes to this flag.' : '';
  const restrictions: string[] = [];
  if (row.origin !== 'scheduled') {
    restrictions.push('Automatic cleanup applies only to scheduled backups. This archive stays outside rotation.');
  } else {
    restrictions.push('Scheduled backups can rotate only after a successful replacement, outside the retained tiers and above the minimum recovery count.');
  }
  if (row.recovery_pin || row.active_use || row.required_by.length) {
    restrictions.push('Recovery protection is managed separately and remains in effect.');
  } else if (row.reason === 'Minimum recovery-point safeguard') {
    restrictions.push('This archive is currently within the minimum recovery count.');
  }
  return { set, label, blocked, restrictions: restrictions.join(' ') };
}
