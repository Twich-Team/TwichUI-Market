import {formatBytes} from './size';
import {LocalTime} from './admin-table';

export interface StorageOperations {
  capacity:{database_allocated_bytes:number|null;database_limit_bytes:number;filesystem:{total_bytes:number|null;available_bytes:number|null;reserve_bytes:number};paused_reason:string|null};
  warnings:string[];
  oldest_observation_at:string|null;
  oldest_daily_day:string|null;
  estimated_live_heap_bytes:number|null;
  estimated_reusable_heap_bytes:number|null;
  wal_allocated_bytes:number|null;
  estimate_notice:string;
  vacuum:{relname:string;n_live_tup:number;n_dead_tup:number;last_autovacuum:string|null}[];
}

export function StorageOperationsPanel({value}:{value?:StorageOperations}) {
  if(!value)return <p className="notice">Database filesystem measurements are unavailable.</p>;
  const capacity=value.capacity;
  return <section className="panel padded" aria-label="Storage safeguards">
    <h3>Storage safeguards</h3>
    {value.warnings.length>0&&<div className="notice" role="status"><strong>Needs attention</strong><ul>{value.warnings.map(warning=><li key={warning}>{warning}</li>)}</ul></div>}
    <dl className="stats">
      <div><dt>Database allocation</dt><dd>{formatBytes(capacity.database_allocated_bytes)}</dd></div>
      <div><dt>Collector allocation cap</dt><dd>{formatBytes(capacity.database_limit_bytes)}</dd></div>
      <div><dt>PostgreSQL filesystem available</dt><dd>{formatBytes(capacity.filesystem.available_bytes)}</dd></div>
      <div><dt>Filesystem safety reserve</dt><dd>{formatBytes(capacity.filesystem.reserve_bytes)}</dd></div>
      <div><dt>PostgreSQL filesystem total</dt><dd>{formatBytes(capacity.filesystem.total_bytes)}</dd></div>
      <div><dt>Storage guard</dt><dd>{capacity.paused_reason||'Within capacity limits'}</dd></div>
      <div><dt>Estimated live heap</dt><dd>{formatBytes(value.estimated_live_heap_bytes)}</dd></div>
      <div><dt>Estimated dead heap for reuse</dt><dd>{formatBytes(value.estimated_reusable_heap_bytes)}</dd></div>
      <div><dt>WAL allocation</dt><dd>{formatBytes(value.wal_allocated_bytes)}</dd></div>
      <div><dt>Oldest observation</dt><dd><LocalTime value={value.oldest_observation_at}/></dd></div>
      <div><dt>Oldest daily reference (UTC)</dt><dd>{value.oldest_daily_day||'Unavailable'}</dd></div>
    </dl>
    <p className="small muted">{value.estimate_notice}</p>
    <details><summary>Vacuum activity</summary><ul>{value.vacuum.map(row=><li key={row.relname}>{row.relname}: {row.n_dead_tup.toLocaleString()} estimated dead rows; last automatic vacuum <LocalTime value={row.last_autovacuum}/></li>)}</ul></details>
  </section>;
}
