import { LocalTime } from './admin-table';
import { formatBytes } from './size';
import type { Storage } from './settings';
import type { MetadataOverview } from './metadata-admin';
import type { Market } from './types';
interface Devices {authorized:number;revoked:number;expired:number;recently_connected:number;authorized_names:string[];live_status:string}
export function AdministrationOverview({storage,coverage,devices,markets,open}:{storage:Storage;coverage:MetadataOverview;devices:Devices;markets:Market[];open:(tab:string)=>void}) {
  const active=markets.filter(m=>m.enabled), failures=active.filter(m=>m.failures>0), uncertain=active.filter(m=>m.freshness!=='current');
  const latest=active.map(m=>m.last_success).filter(Boolean).sort().at(-1);
  const link=(tab:string,label:string)=><button className="text-button overview-link" onClick={()=>open(tab)}>{label} ↗</button>;
  return <section aria-label="Operational overview">
    <div className="stats">
      <article><label>COLLECTION HEALTH</label><strong>{failures.length ? `${failures.length} need attention` : `${active.length} scheduled ${active.length===1?'market':'markets'}`}</strong><small>{active.length?`${uncertain.length} stale or unknown source timestamps`:'No markets collecting'}</small>{link('collection','Collection checks')}</article>
      <article><label>DATA FRESHNESS</label><strong>{active.length ? `${active.filter(m=>m.freshness==='current').length} current` : 'No active market'}</strong><small>Last successful collection check: <LocalTime value={latest}/></small>{link('markets','Markets & schedules')}</article>
      <article><label>DATABASE ALLOCATION</label><strong>{formatBytes(storage.database_bytes)}</strong><small>{storage.growth.delta_bytes===null?'Waiting for measurements':`${storage.growth.delta_bytes>0?'+':''}${formatBytes(storage.growth.delta_bytes)} across ${(storage.growth.elapsed_seconds/86400).toFixed(1)} recorded days`}</small>{link('storage','Database Growth')}</article>
      <article><label>BACKUP HEALTH</label><strong>{storage.backup.status.replaceAll('_',' ')}</strong><small>Last dump: <LocalTime value={storage.backup.last_success}/><br/>Restore verified: <LocalTime value={storage.backup.last_restoration_verified_at}/></small>{link('storage','Storage & backups')}</article>
      <article><label>DEVICE ACCESS</label><strong>{devices.authorized} authorized devices</strong><small>{devices.recently_connected} recently connected (15 min) · {devices.revoked} revoked · {devices.expired} expired<br/>{devices.authorized_names.join(', ')}<br/><span title={devices.live_status}>Online status unavailable</span></small>{link('devices','Manage device access')}</article>
      <article><label>ITEM NAMES</label><strong>{coverage.name_percent===null?'No observations':`${coverage.name_percent}% coverage`}</strong><small>{coverage.resolved_names.toLocaleString()} named / {coverage.observed.toLocaleString()} observed IDs · {coverage.missing_names.toLocaleString()} unnamed</small>{link('metadata','Name recovery')}</article>
      <article><label>STORED ITEM METADATA</label><strong>{coverage.attributes_available.toLocaleString()} with attributes</strong><small>{coverage.icons_available.toLocaleString()} icons · {coverage.observed-coverage.attributes_available} missing attributes. Presence does not imply complete facts.</small>{link('metadata','Metadata coverage')}</article>
      <article><label>RECOVERY WORK</label><strong>{coverage.scoped_pending_items.toLocaleString()} pending items</strong><small>{coverage.failed_or_blocked} unnamed with errors/blocked access · {coverage.unknown_not_tried} unknown, not tried. Recoverability is unconfirmed.</small>{link('metadata','Review recovery work')}</article>
    </div>
    {(failures.length>0||uncertain.length>0||storage.backup.error||!storage.backup.last_restoration_verified_at||coverage.failed_or_blocked>0)&&<section className="panel padded" aria-label="Operational attention"><h3>Needs attention</h3>
      {failures.map(m=><p key={m.id}>{m.label}: {m.last_error||`${m.failures} collection failures`}</p>)}
      {!!uncertain.length&&<p>{uncertain.length} active markets have stale or unknown source freshness. A successful check may return unchanged data.</p>}
      {(storage.backup.error||!storage.backup.last_restoration_verified_at)&&<p>{storage.backup.error||'No verified restore rehearsal is recorded.'} {link('storage','Review backup health')}</p>}
      {!!coverage.failed_or_blocked&&<p>{coverage.failed_or_blocked} unnamed items have recorded provider failures or access restrictions. {link('sources','Review data sources')}</p>}
    </section>}
    <p className="small muted">{coverage.coverage_identity} This is a current stored-data measurement. Historical coverage is not reconstructed.</p>
  </section>;
}
