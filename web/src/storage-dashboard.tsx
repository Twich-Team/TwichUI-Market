import { useState, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './api';
import { navigate, useLocation } from './navigation';
import { LocalTime, Status } from './admin-table';
import { BackupManagement, useBackupOverview } from './backup-management';
import { BackupStorage, useBackupStorage, MigrationProgress } from './backup-storage';
import { DatabaseGrowth } from './storage-growth';
import { StorageOperationsPanel } from './storage-operations';
import { MaintenanceDashboard, useMaintenanceHealth } from './maintenance-dashboard';
import type { Storage } from './settings';
import { formatBytes } from './size';
import { capacityParts, physicalBackupBytes, isFresh, storageUrl, storageView, type StorageView } from './storage-dashboard-data';
import './storage-dashboard-shell.css';

export function useStorageSummary(enabled=true) {
  return useQuery({queryKey:['private','storage-summary'],queryFn:({signal})=>api<Storage>('/admin/storage','GET',undefined,signal),enabled,retry:false,staleTime:60000,refetchInterval:60000});
}
const tabs:[StorageView,string,string][]=[['overview','Overview','◈'],['backups','Backups','▤'],['storage','Storage','▰'],['maintenance','Maintenance','⚙']];
export function StorageDashboard({readOnly=false}:{readOnly?:boolean}) {
  const url=useLocation(),view=storageView(url.split('?')[1]||''),client=useQueryClient();
  const summary=useStorageSummary(), destinations=useBackupStorage(view==='backups');
  return <div className="storage-dashboard">
    <div className="storage-title"><div><span className="eyebrow">THE RECOVERY LEDGER</span><h1>Storage &amp; Backups</h1><p>Keep your history safe. See what needs your attention.</p></div>{view==='overview'&&<div className="backup-actions"><button aria-label="Refresh storage dashboard" onClick={()=>{for(const key of ['storage-summary','backup-management','backup-storage','maintenance-health'])void client.invalidateQueries({queryKey:['private',key]});}}>↻ Refresh</button></div>}</div>
    <nav className="storage-subnav" aria-label="Storage & Backups pages">{tabs.map(([key,label,icon])=><a key={key} href={storageUrl(key)} aria-current={view===key?'page':undefined} onClick={event=>{if(!event.metaKey&&!event.ctrlKey&&!event.shiftKey&&event.button===0){event.preventDefault();navigate(storageUrl(key));}}}><span aria-hidden="true">{icon}</span>{label}</a>)}</nav>
    <div className="storage-page" key={view}>
      {view==='overview'&&<StorageOverview summary={summary.data} summaryError={summary.error?.message}/>}
      {view==='backups'&&<BackupManagement readOnly={readOnly} destinations={destinations.data?.destinations}/>}
      {view==='storage'&&<><BackupStorage readOnly={readOnly} databaseStorage={summary.data}/><section className="panel padded"><h3>PostgreSQL storage</h3><CapacityRow title="Database filesystem" total={summary.data?.operations?.capacity.filesystem.total_bytes} available={summary.data?.operations?.capacity.filesystem.available_bytes}/><p className="small muted">The database stays on its current server when backups move to a NAS.</p></section></>}
      {view==='maintenance'&&<MaintenanceDashboard summary={summary.data} readOnly={readOnly}/>}
    </div>
  </div>;
}
function Metric({icon,label,value,children}:{icon:string;label:string;value:ReactNode;children:ReactNode}) {
  return <article className="storage-metric"><div><span>{label}</span><span className="storage-metric-icon" aria-hidden="true">{icon}</span></div><strong>{value}</strong><small>{children}</small></article>;
}
export function CapacityRow({title,total,available,free,note}:{title:string;total?:number|null;available?:number|null;free?:number|null;note?:string}) {
  const hasFree=typeof free==='number';
  const parts=capacityParts(total,hasFree?free:available),usage=hasFree?'used':'used or unavailable';
  return <div className="capacity-row"><div className="capacity-heading"><strong>{title}</strong><span>{parts?`${parts.percent.toFixed(1)}% ${usage}`:'Capacity unavailable'}</span></div>{parts?<><div className="capacity-stack" role="img" aria-label={`${title}: ${formatBytes(parts.used)} ${usage}, ${formatBytes(parts.available)} available of ${formatBytes(parts.total)}`}><span style={{width:parts.percent+'%'}} title={`${usage}: ${parts.used.toLocaleString()} bytes`}/><span className="capacity-free" style={{width:(100-parts.percent)+'%'}} title={`Available: ${parts.available.toLocaleString()} bytes`}/></div><div className="capacity-values"><span>{formatBytes(parts.used)} {usage}</span><span>{formatBytes(available)} available / {formatBytes(parts.total)}</span></div></>:<p className="small muted">No reliable filesystem reading is available.</p>}{note&&<p className="small muted">{note}</p>}</div>;
}
function StorageOverview({summary,summaryError}:{summary?:Storage;summaryError?:string}) {
  const backups=useBackupOverview(),storage=useBackupStorage(),maintenance=useMaintenanceHealth();
  const b=backups.data,s=storage.data,m=maintenance.data;
  const lastBackup=b?.last_success?Date.parse(b.last_success):NaN;
  const backupAge=Number.isFinite(lastBackup)&&lastBackup<=Date.now()+60000?Math.max(0,(Date.now()-lastBackup)/3600000):null;
  const backupTime=backupAge===null?'Not recorded':backupAge<1?'Less than 1h ago':backupAge<24?`${Math.floor(backupAge)} hours ago`:`${Math.floor(backupAge/24)} days ago`;
  const active=s?.destinations.find(d=>d.id===s.active_id),health=active?s?.health[active.id]:undefined;
  const fresh=Boolean(b&&!backups.error&&!b.inventory_stale&&isFresh(b.measured_at));
  const recovery=m?.automation.recovery;
  const dbSample=summary?.growth.samples.at(-1)?.sampled_at;
  const backupBytes=physicalBackupBytes(b?.inventory_by_storage);
  const verified=Boolean(!maintenance.error&&m&&isFresh(m.measured_at)&&recovery?.required_evidence_recent&&recovery.expires_at&&Date.parse(recovery.expires_at)>Date.now());
  const running=['queued','running'].includes(s?.migration.status||'');
  const backupCapacity=health&&typeof health.capacity_bytes==='number'&&typeof health.available_bytes==='number'?{total:health.capacity_bytes,available:health.available_bytes,free:health.free_bytes}:{total:b?.filesystem.capacity_bytes,available:b?.filesystem.available_bytes,free:undefined};
  const issues:[string,StorageView][]=[];
  if(backups.error)issues.push(['Backup service unavailable. Recovery point status is unknown.','backups']);
  if(b?.storage_error||b?.inventory_stale)issues.push([b.storage_error||'Backup inventory is stale. Refresh after the active operation.','storage']);
  if(b?.storage_pressure)issues.push(['Backup storage is below its configured free-space warning.','storage']);
  if(b?.job.status==='failed')issues.push(['The latest backup operation failed. Review its result.','backups']);
  if(health?.healthy===false)issues.push(['The active backup destination needs attention.','storage']);
  if(['failed','interrupted','paused'].includes(s?.migration.status||''))issues.push([`Storage migration ${s?.migration.status}. Originals remain tracked.`, 'storage']);
  if(m?.automation.paused_reason&&['paused','failed','interrupted','disabled','unauthorized'].includes(m.status))issues.push([m.automation.paused_reason,'maintenance']);
  if(m&&recovery&&!verified)issues.push(['Restore verification needs attention. Check recovery evidence before cleanup.','maintenance']);
  return <>
    <div className="storage-freshness">{b?.measured_at?<>Backup inventory measured <LocalTime value={b.measured_at}/>{!fresh&&' · Stale or unavailable'}</>:'Waiting for backup inventory…'}</div>
    <div className="storage-metrics">
      <Metric icon="◉" label="Database size" value={formatBytes(summary?.database_bytes)}>{summary?.growth.bytes_per_day!=null?`${summary.growth.bytes_per_day>=0?'+':''}${formatBytes(summary.growth.bytes_per_day)} / day`:'Waiting for growth measurements'}{dbSample&&!isFresh(dbSample,Date.now(),7200000)&&' · measurement is old'}</Metric>
      <Metric icon="▤" label="Backup storage" value={b?formatBytes(backupBytes):'Unavailable'}>{b?`${b.total} recovery points${!fresh?' · last known inventory':''}`:'Recovery point count unavailable'}</Metric>
      <Metric icon="↶" label="Latest successful backup" value={b?.last_success?<time dateTime={b.last_success} title={new Date(b.last_success).toLocaleString()}>{backupTime}</time>:backups.isPending?'Checking…':'Not recorded'}>{b?.next_scheduled_at?<>Next <LocalTime value={b.next_scheduled_at}/></>:b?.policy.enabled?'Next backup time unavailable':'Automatic backups disabled or unavailable'}</Metric>
      <Metric icon="◇" label="Restore verification" value={maintenance.isPending?'Checking…':verified?'Verified':recovery?'Needs attention':'Unknown'}>{recovery?.verified_at?<>Last restored <LocalTime value={recovery.verified_at}/></>:'No current recovery evidence available'}</Metric>
    </div>
    {(issues.length>0||running||['queued','running'].includes(b?.job.status||''))&&<section className="storage-attention" aria-label="Attention and activity"><div className="storage-attention-title">◐ Attention &amp; activity</div>{issues.slice(0,4).map(([message,target],index)=><button key={index} onClick={()=>navigate(storageUrl(target))}>{message}<span aria-hidden="true"> →</span></button>)}{issues.length>4&&<button onClick={()=>navigate(storageUrl('maintenance'))}>Review {issues.length-4} more health signals →</button>}{running&&<><MigrationProgress migration={s!.migration} destinations={s!.destinations}/><button onClick={()=>navigate(storageUrl('storage'))}>Open migration →</button></>}{['queued','running'].includes(b?.job.status||'')&&<button onClick={()=>navigate(storageUrl('backups'))}>Backup operation {b?.job.status} — open progress →</button>}</section>}
    <div className="storage-overview-grid"><div>{summary?<DatabaseGrowth samples={summary.growth.samples} current={summary.database_bytes}/>:<section className="panel padded"><h3>Database growth</h3><p role={summaryError?'alert':'status'}>{summaryError||'Loading actual database measurements…'}</p></section>}</div>
      <section className="panel padded system-health"><div className="panel-heading"><h3>System health</h3><span className="small muted">Live safeguards</span></div>
        <HealthRow label="Automatic backups" value={fresh?(b?.policy.enabled?'Scheduled':'Disabled'):'Unknown'} tone={fresh&&b?.policy.enabled?'success':'neutral'} target="backups"/>
        <HealthRow label="Backup destination" value={active?.name||'Unknown'} target="storage"/>
        <HealthRow label="Storage connectivity" value={storage.error?'Unavailable':health?isFresh(health.tested_at)?health.healthy?'Connected':'Needs attention':'Last check is old':'Not tested'} tone={!storage.error&&health&&isFresh(health.tested_at)?health.healthy?'success':'warning':'neutral'} target="storage"/>
        <HealthRow label="Latest operation" value={b?.job.status||'Not recorded'} tone={fresh&&b?.job.status==='succeeded'?'success':b?.job.status==='failed'?'error':'neutral'} target="backups"/>
        <HealthRow label="Restore verification" value={verified?'Current':'Unknown or expired'} tone={verified?'success':'neutral'} target="backups"/>
        <HealthRow label="Historical cleanup" value={maintenance.error?'Unavailable':m?.status.replaceAll('_',' ')||'Unknown'} tone={m?.automation.paused_reason?'warning':'neutral'} target="maintenance"/>
        <HealthRow label="Database maintenance" value={maintenance.error?'Unavailable':m?.aggregation.status.replaceAll('_',' ')||'Unknown'} target="maintenance"/>
      </section></div>
    <section className="panel padded overview-capacity"><div className="panel-heading"><h3>Storage capacity</h3><button className="text-button" onClick={()=>navigate(storageUrl('storage'))}>Manage storage →</button></div><div className="storage-capacity-grid"><CapacityRow title="PostgreSQL filesystem" total={summary?.operations?.capacity.filesystem.total_bytes} available={summary?.operations?.capacity.filesystem.available_bytes}/><CapacityRow title={active?.name||'Backup destination'} total={backupCapacity.total} available={backupCapacity.available} free={backupCapacity.free} note={active?.type==='smb'?'NAS totals include other files; Market archives are counted separately.':'Filesystem totals may overlap the database filesystem; do not add them together.'}/></div></section>
  </>;
}
function HealthRow({label,value,tone='neutral',target}:{label:string;value:string;tone?:'success'|'warning'|'error'|'neutral';target:StorageView}) {
  return <button className="storage-health-row" onClick={()=>navigate(storageUrl(target))}><span>{label}</span><Status tone={tone}>{value}</Status></button>;
}
