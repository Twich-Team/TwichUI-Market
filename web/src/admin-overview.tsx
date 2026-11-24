import { LocalTime, Status } from './admin-table';
import { formatBytes } from './size';
import type { Storage } from './settings';
import type { BackupOverview } from './backup-management';
import type { MetadataOverview } from './metadata-admin';
import type { Market } from './types';
import { Loading } from './loading';
import { SourceAge } from './admin-histories';

interface Devices { authorized: number; recently_connected: number }

export function AdministrationOverview({storage,backups,coverage,devices,markets,open,loading,errors}: {
  storage?: Storage;
  backups?: BackupOverview;
  coverage?: MetadataOverview;
  devices?: Devices;
  markets: Market[];
  open: (tab: string) => void;
  loading: boolean;
  errors: boolean;
}) {
  const active = markets.filter(market => market.enabled);
  const failed = active.filter(market => market.failures > 0 || market.last_error);
  const old = active.filter(market => market.freshness === 'stale' && !failed.includes(market));
  const missingTime = active.filter(market => market.freshness === 'unknown' && !failed.includes(market));
  const latestCheck = active.map(market => market.last_success).filter(Boolean).sort().at(-1);
  const link = (tab: string, label: string) => <button className="text-button overview-link" onClick={()=>open(tab)}>{label} <span aria-hidden="true">↗</span></button>;
  const issues = [
    ...failed.map(market => ({ key: `failed-${market.id}`, title: `${market.label} collection failed`,
      detail: market.last_error || `${market.failures} consecutive failed checks. Prices may be old.`, tab: 'collection', action: 'Review collection checks' })),
    ...(old.length ? [{ key: 'old', title: 'Some prices may be old', detail: `${old.length} active market${old.length===1?' has':'s have'} old or incomplete source data.`, tab: 'collection', action: 'Review source updates' }] : []),
    ...(missingTime.length ? [{ key: 'source', title: 'Price age is unknown', detail: `${missingTime.length} active market${missingTime.length===1?' has':'s have'} no reliable source timestamp.`, tab: 'collection', action: 'Review source updates' }] : []),
    ...(backups?.storage_error || backups?.job.status === 'failed' || backups?.storage_pressure
      ? [{ key: 'backups', title: 'Backup operations need review', detail: backups.storage_error || backups.job.error || 'Available space is below the backup warning limit.', tab: 'storage', action: 'Review backup health' }] : []),
    ...(backups && !backups.last_restoration_verified_at
      ? [{ key: 'restore', title: 'Recovery has not been verified', detail: 'No successful restore rehearsal is recorded.', tab: 'storage', action: 'Review recovery points' }] : []),
    ...(coverage?.failed_or_blocked
      ? [{ key: 'metadata', title: 'Some items still have no name', detail: `${coverage.failed_or_blocked.toLocaleString()} items have recorded source failures or access restrictions.`, tab: 'sources', action: 'Review data sources' }] : []),
  ];
  return <section className="administration-overview" aria-label="Operational overview">
    <section className="panel padded" aria-labelledby="attention-heading">
      <h2 id="attention-heading">Needs attention</h2>
      {loading && <Loading label="Checking installation health…" inline/>}
      {errors && <p className="notice">Some health checks are unavailable. Open the relevant page to review or retry its measurements.</p>}
      {issues.length > 0 ? <ul className="admin-health-list">{issues.map(issue=><li key={issue.key}>
        <div><strong>{issue.title}</strong><p>{issue.detail}</p></div>
        {link(issue.tab, issue.action)}
      </li>)}</ul> : !loading && !errors && <p><Status tone="success">No issues reported</Status></p>}
    </section>
    <section className="panel padded" aria-label="Whole installation">
      <h2>Whole installation</h2>
      <ul className="admin-health-list">
        <li><div><strong>Collection</strong><p>{active.length ? `${active.length} active market${active.length===1?'':'s'}` : 'No markets collecting'}{active.length===1 && <><br/>Source updated <SourceAge market={active[0]}/></>}<br/>Last successful check <LocalTime value={latestCheck}/></p></div>{link('collection','Collection checks')}</li>
        <li><div><strong>Backups</strong><p>{backups ? `${backups.total.toLocaleString()} recovery points · ${backups.policy.enabled?'Scheduled':'Automatic backups disabled'}` : loading?'Checking backup inventory…':'Backup inventory unavailable'}</p></div>{link('storage','Storage & backups')}</li>
        <li><div><strong>Capacity</strong><p>{storage ? `${formatBytes(storage.database_bytes)} allocated to the database` : loading?'Checking database allocation…':'Database allocation unavailable'}</p></div>{link('storage','Review capacity')}</li>
        <li><div><strong>Access</strong><p>{devices ? `${devices.authorized} authorized devices · ${devices.recently_connected} contacted Market in the last 15 minutes` : loading?'Checking device access…':'Device summary unavailable'}</p></div>{link('devices','Manage device access')}</li>
      </ul>
    </section>
  </section>;
}
