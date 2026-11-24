import { describe, it, expect } from 'vitest';
import { backupKeepFlag, backupOutcome, backupQueryParams, reliabilityCounts, utcBackupDay, type BackupFilters } from './backup-data';

const filters: BackupFilters = { search: '', storage: 'all', protection: 'all', verified: 'all', backupType: 'all', sort: 'created_desc' };
const inventory = [
  { created_at: '2026-11-19T23:59:00-02:00', verification: 'archive_integrity_verified' },
  { created_at: '2026-11-22T10:00:00Z', verification: 'legacy_metadata_only' },
];

describe('backup inventory and reliability', () => {
  it('preserves the overview request and applies filters and sorting server-side', () => {
    expect(backupQueryParams(0, filters).toString()).toBe('offset=0&limit=100');
    const params = backupQueryParams(10, { ...filters, search: 'NAS & vault', storage: 'nas', protection: 'protected', backupType: 'manual', verified: 'restored', sort: 'bytes_asc' }, 10);
    expect(Object.fromEntries(params)).toEqual({ offset: '10', limit: '10', search: 'NAS & vault', storage_id: 'nas', protection: 'protected', verification: 'restored', backup_type: 'manual', sort: 'bytes_asc' });
  });

  it('uses UTC day boundaries including leap day', () => {
    expect(utcBackupDay('2024-02-28T23:55:00-02:00')).toBe('2024-02-29');
    expect(utcBackupDay('2024-03-01T00:05:00+02:00')).toBe('2024-02-29');
  });

  it('trusts recorded outcomes before archive counts and omits future evidence', () => {
    const days = reliabilityCounts(inventory, [], [
      { day: '2026-11-20', succeeded: 1, failed: 1 }, { day: '2026-11-21', succeeded: 0, failed: 1 },
    ]);
    expect(backupOutcome('2026-11-20', '2026-11-20', days)).toBe('mixed');
    expect(backupOutcome('2026-11-21', '2026-11-20', days)).toBe('unknown');
    expect(backupOutcome('2026-11-21', '2026-11-21', days)).toBe('failed');
  });

  it('distinguishes fallback archive evidence, recorded failures and missing days', () => {
    const days = reliabilityCounts(inventory, [
      { at: '2026-11-21T09:00:00Z', action: 'backup.failed' }, { at: '2026-11-23T09:00:00Z', action: 'protection.updated' },
    ]);
    expect(backupOutcome('2026-11-20', '2026-11-24', days)).toBe('success');
    expect(backupOutcome('2026-11-21', '2026-11-24', days)).toBe('failed');
    expect(backupOutcome('2026-11-22', '2026-11-24', days)).toBe('unknown');
    expect(backupOutcome('2026-11-23', '2026-11-24', days)).toBe('unknown');
    expect(backupOutcome('2026-11-24', '2026-11-24', days)).toBe('unknown');
  });
});

describe('backup keep flag', () => {
  const manual = { type: 'manual', origin: 'manual', protected: true, verification: 'archive_integrity_verified', required_by: [], reason: '' };

  it.each(['manual', 'release', 'restore-verification'])('explains why a %s copy stays outside rotation', origin => {
    const flag = backupKeepFlag({ ...manual, origin, type: origin });
    expect(flag.label).toBe('Remove keep flag');
    expect(flag.restrictions).toContain('stays outside rotation');
  });

  it('distinguishes explicit flags, minimum retention and independent recovery pins', () => {
    const flag = backupKeepFlag({ ...manual, origin: 'scheduled', type: 'scheduled', reason: 'Minimum recovery-point safeguard' });
    expect(flag.restrictions).toContain('currently within the minimum recovery count');
    const pinned = backupKeepFlag({ ...manual, keep_flag: false, recovery_pin: true, required_by: ['restore'] });
    expect(pinned.label).toBe('Set keep flag');
    expect(pinned.restrictions).toContain('remains in effect');
    expect(pinned.blocked).toContain('reservation');
  });
});
