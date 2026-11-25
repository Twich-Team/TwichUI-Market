import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from './api';
import { LocalTime, Status } from './admin-table';
import { formatBytes } from './size';
import { ConfirmationDialog } from './confirmation-dialog';
import './storage-dashboard.css';
import { useBackupOverview } from './backup-management';
import { StorageForecast } from './storage-forecast';
import type { FilesystemSample } from './storage-forecast-data';
import type { StorageOperations } from './storage-operations';

export type Destination={id:string;revision:number;type:'local'|'smb'|'mounted';name:string;host?:string;port?:number;username?:string;domain?:string;share?:string;directory:string;require_encryption?:boolean;password_saved?:boolean};
export type Health={healthy:boolean;tested_at:string;last_success_at?:string;error?:string;capacity_bytes:number|null;available_bytes:number|null;free_bytes?:number|null;read?:boolean;write?:boolean;create_directory?:boolean;rename?:boolean;delete?:boolean;cleanup_pending?:boolean};
export type Migration={id?:string;status?:string;copied?:number;bytes_copied?:number;error?:string;started_at?:string;requested_at?:string;finished_at?:string;plan?:{source_id?:string;destination_id?:string;count:number;bytes:number;protected_count?:number;reserved_count?:number};originals_preserved?:boolean};
export type StorageState={original_cleanup?:{status:string;removed?:number;retained?:number;error?:string;results?:{filename:string;status:string;error?:string}[]};pending_cleanup_count?:number;active_id:string;destinations:Destination[];health:Record<string,Health>;migration:Migration;restore?:{status?:string;error?:string};restore_available?:boolean;share_notice:string;mounted_notice:string;automatic_recovery?:{verified_at?:string;expires_at?:string};automatic_restore_enabled?:boolean};
type Plan={source_id:string;destination_id:string;count:number;bytes:number;required_bytes?:number;reusable_bytes?:number;protected_count?:number;reserved_count?:number;available_bytes:number|null;enough_space:boolean;originals_preserved:boolean;token:string};
const fresh=():Partial<Destination>=>({type:'smb',name:'My NAS',host:'',port:445,username:'',domain:'',share:'',directory:'',require_encryption:true});

export function useBackupStorage(enabled=true){
  return useQuery({enabled,queryKey:['private','backup-storage'],queryFn:({signal})=>api<StorageState>('/admin/backups/storage','GET',undefined,signal),retry:false,staleTime:30000,refetchInterval:query=>[query.state.data?.migration?.status,query.state.data?.restore?.status,query.state.data?.original_cleanup?.status].some(status=>['queued','running'].includes(status||''))?5000:60000});
}

export function BackupStorage({readOnly=false,databaseStorage}:{readOnly?:boolean;databaseStorage?:{growth:{samples:FilesystemSample[]};operations?:StorageOperations}}){
  const query=useBackupStorage(), inventory=useBackupOverview();
  const [draft,setDraft]=useState<Partial<Destination>>(fresh),[password,setPassword]=useState(''),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const [health,setHealth]=useState<Health|null>(null),[folders,setFolders]=useState<string[]>([]),[path,setPath]=useState(''),[next,setNext]=useState<number|null>(null),[folder,setFolder]=useState(''),[browsing,setBrowsing]=useState(false);
  const [configuring,setConfiguring]=useState(false),[diagnostics,setDiagnostics]=useState(false);
  async function browseDestination(id:string){await run(async()=>{const result=await api<{directory:string;folders:string[];next_offset:number|null}>('/admin/backups/storage/browse','POST',{id,directory:'',offset:0});setPath(result.directory);setFolders(result.folders);setNext(result.next_offset);setBrowsing(true);});}
  const [plan,setPlan]=useState<Plan|null>(null),[remove,setRemove]=useState(false),[confirmation,setConfirmation]=useState(''),[protectedOriginalAck,setProtectedOriginalAck]=useState(false);
  const data=query.data;
  const field=<K extends keyof Destination>(key:K,value:Destination[K])=>setDraft(previous=>({...previous,[key]:value}));
  async function run(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();await query.refetch();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  function edit(id:string){setConfiguring(true);setDiagnostics(false);setSelected(id);setPassword('');setHealth(null);setBrowsing(false);setFolders([]);setPlan(null);setError('');setNotice('');setDraft(id?{...data!.destinations.find(d=>d.id===id)!}:fresh());}
  async function save(){await run(async()=>{const result=await api<Destination>('/admin/backups/storage/save','POST',{...draft,...(password?{password}:{}),password_saved:undefined});setDraft(result);setSelected(result.id);setPassword('');setHealth(null);setNotice('Storage settings saved. Test this destination before migration. The active destination is unchanged.');});}
  async function test(){await run(async()=>{const result=await api<Health>('/admin/backups/storage/test','POST',{id:selected});setHealth(result);setNotice(result.healthy?'Connection and backup permissions verified.': 'Connection needs attention. Review the result below.');});}
  async function browse(directory:string,offset=0){await run(async()=>{const result=await api<{directory:string;folders:string[];next_offset:number|null}>('/admin/backups/storage/browse','POST',{id:selected,directory,offset});setPath(result.directory);setFolders(offset?[...folders,...result.folders]:result.folders);setNext(result.next_offset);setBrowsing(true);});}
  const currentHealth=health||(selected?data?.health[selected]:undefined);
  const lastMigration=data?.migration;
  const saved=data?.destinations.find(d=>d.id===selected);
  const dirty=Boolean(password)||!saved||(['name','host','port','username','domain','share','directory','require_encryption'] as const).some(k=>draft[k]!==saved[k]);
  return <section className="panel padded backup-storage" aria-label="Backup Storage">
    <div className="backup-heading"><div><span className="eyebrow">DESTINATIONS & CAPACITY</span><h2>Storage locations</h2><p className="muted">Know where recovery points live. Move them with verified, recoverable migration.</p></div><div className="backup-actions"><button disabled={busy} onClick={()=>void query.refetch()}>Refresh storage</button><button className="primary" disabled={readOnly||busy} onClick={()=>edit('')}>Add storage destination</button></div></div>
    {query.isPending&&<p role="status">Loading backup destinations…</p>}
    {query.error&&<p role="alert" className="notice error">{query.error.message}. Saved destinations remain unchanged.</p>}
    {error&&<p role="alert" className="notice error">{error}</p>}{notice&&<p role="status" className="notice">{notice}</p>}
    {data&&<>
      <div className="storage-device-grid">{data.destinations.map(destination=>{
        const check=data.health[destination.id];
        const consumption=inventory.data?.inventory_by_storage?.[destination.id];
        const isActive=destination.id===data.active_id;
        const migrating=['queued','running'].includes(lastMigration?.status||'');
        const role=isActive?(migrating?'Active destination · migration source':'Active backup destination'):migrating&&lastMigration?.plan?.destination_id===destination.id?'Migration destination':lastMigration?.plan?.source_id===destination.id&&lastMigration?.originals_preserved&&Boolean(consumption?.count)?'Original recovery copies':'Configured · inactive';
        const checkFresh=Boolean(check&&!query.isError&&Date.now()-new Date(check.tested_at).getTime()>=0&&Date.now()-new Date(check.tested_at).getTime()<900000);
        return <article className="storage-device" key={destination.id}>
          <div className="storage-device-title"><span className="storage-device-symbol" aria-hidden="true">{destination.type==='smb'?'▤':'▣'}</span><div><span className="eyebrow">{destination.type==='smb'?'NETWORK STORAGE':destination.type==='mounted'?'MOUNTED FILESYSTEM':'LOCAL STORAGE'}</span><h3>{destination.name}</h3></div><Status tone={check&&!check.healthy?'warning':checkFresh?'success':'neutral'}>{check?(!check.healthy?'Needs attention':checkFresh?'Connection checked':'Check expired'):'Not tested'}</Status></div>
          <span className={`storage-role ${isActive?'active':''}`}>{role}</span>
          <p className="small muted storage-address">{destination.type==='smb'?`${destination.host} / ${destination.share}${destination.directory?` / ${destination.directory}`:''}`:'Installation’s persistent backup filesystem'}</p>
          <StorageCapacity health={check} marketBytes={!inventory.data?.inventory_stale?consumption?.bytes:undefined}/>
          <p className="storage-market-consumption"><strong>{formatBytes(consumption?.bytes)}</strong> Market recovery points {consumption?`· ${consumption.count.toLocaleString()} copies`:''}{inventory.data?.inventory_stale?' · last known inventory':''}</p>
          <p className="small muted">Last successful check: <LocalTime value={check?.last_success_at}/></p>
          <div className="backup-actions"><button disabled={busy} onClick={()=>edit(destination.id)}>Configure</button><button disabled={readOnly||busy} onClick={()=>void run(async()=>{const result=await api<Health>('/admin/backups/storage/test','POST',{id:destination.id});setNotice(result.healthy?`${destination.name}: connection and backup permissions verified.`:result.error||'Connection needs attention.');})}>Test connection</button>{destination.type==='smb'&&<button disabled={readOnly||busy} onClick={()=>{edit(destination.id);void browseDestination(destination.id);}}>Browse directories</button>}<button disabled={busy} onClick={()=>{edit(destination.id);setDiagnostics(true);}}>View diagnostics</button></div>
          {check?.error&&<p className="notice error">{check.error}</p>}
        </article>;
      })}</div>
      <p className="small muted">Filesystem totals include all files. Capacity checks are snapshots; connection checks expire after 15 minutes. View recovery point consumption on Backups.</p>
      {Boolean(data.pending_cleanup_count)&&<p className="notice">{data.pending_cleanup_count} interrupted backup files need cleanup. Completed recovery copies are preserved. <button disabled={readOnly||busy} onClick={()=>void run(async()=>{await api('/admin/backups/storage/cleanup','POST',{});setNotice('Incomplete backup cleanup completed.');})}>Retry incomplete backup cleanup</button></p>}
      <section className="backup-policy storage-migration" aria-label="Storage migration"><div className="backup-heading"><div><span className="eyebrow">VERIFIED TRANSFER</span><h3>Backup migration</h3></div></div><label>Migration destination<select aria-label="Migration destination" value={selected} disabled={readOnly||busy} onChange={e=>{const id=e.target.value;setSelected(id);setDraft(id?{...data.destinations.find(d=>d.id===id)!}:fresh());setPassword('');setPlan(null);}}><option value="">Choose a saved destination</option>{data.destinations.filter(d=>d.id!==data.active_id).map(d=><option value={d.id} key={d.id}>{d.name}</option>)}</select></label><p>Preview the copy and required space. Market verifies every copied archive before activating the destination. Original copies and protection metadata are preserved.</p><button disabled={readOnly||busy||!selected||dirty||selected===data.active_id||['queued','running'].includes(lastMigration?.status||'')} onClick={()=>void run(async()=>setPlan(await api<Plan>('/admin/backups/storage/migration-preview','POST',{id:selected})))}>Preview migration</button>
        {lastMigration?.status==='succeeded'
          ? <details><summary>Completed migration receipt</summary><MigrationProgress migration={lastMigration} destinations={data.destinations}/></details>
          : lastMigration?.status&&<MigrationProgress migration={lastMigration} destinations={data.destinations}/>}
        {lastMigration?.status==='succeeded'&&<><p>Destination activated. Original copies remain at the previous destination until you explicitly remove them. Backups required by a recovery operation remain protected.</p><button disabled={readOnly||busy} onClick={()=>{setRemove(true);setConfirmation('');setProtectedOriginalAck(false);}}>Remove verified original copies…</button></>}
      </section>
      <details className="backup-policy"><summary>Automatic restore verification & recovery details</summary><p>{data.automatic_restore_enabled?'Enabled: new recovery archives are restored on the isolated verification server. Collection uses its original database.':'Automatic isolated restoration is not enabled on this installation.'}</p><p>Last verified: <LocalTime value={data.automatic_recovery?.verified_at}/><br/>Expires: <LocalTime value={data.automatic_recovery?.expires_at}/></p><p className="small muted">A failed verification preserves the previous protected recovery point and pauses destructive cleanup. Check storage access and the latest restore result; automatic attempts retry after recovery.</p></details>
      {data.original_cleanup?.status&&<details className="backup-policy"><summary>Original copy cleanup · {data.original_cleanup.status}</summary><p role="status">{data.original_cleanup.removed??0} originals removed; {data.original_cleanup.retained??0} retained. {data.original_cleanup.error}</p>{Boolean(data.original_cleanup.results?.length)&&<ul>{data.original_cleanup.results?.map(row=><li key={row.filename}>{row.filename} · {row.status}{row.error?` · ${row.error}`:''}</li>)}</ul>}</details>}
      {data.restore?.status&&<p>Latest isolated restore: {data.restore.status}. {data.restore.error}</p>}
      <StorageForecast samples={databaseStorage?.growth.samples||[]} operations={databaseStorage?.operations}/>
    </>}
    {configuring&&data&&<ConfirmationDialog title="Configure backup storage" onClose={()=>{if(!busy){setConfiguring(false);setPassword('');setBrowsing(false);}}}><div className="backup-storage storage-configuration">
      <p className="muted">Save and test a destination, then review migration before changing where backups are written.</p>
      {error&&<p role="alert" className="notice error">{error}</p>}{notice&&<p role="status" className="notice">{notice}</p>}
      <label>Destination to configure<select aria-label="Destination to configure" disabled={busy} value={selected} onChange={e=>edit(e.target.value)}><option value="">Add a destination</option>{data.destinations.map(d=><option key={d.id} value={d.id}>{d.name}{d.id===data.active_id?' (active)':''}</option>)}</select></label>
      <div className="backup-policy-grid">
        <label>Storage type<select aria-label="Storage type" value={draft.type} disabled={busy||Boolean(draft.id)} onChange={e=>field('type',e.target.value as Destination['type'])}><option value="smb">SMB / NAS</option><option value="local">Local filesystem</option><option value="mounted">Existing mounted filesystem</option></select></label>
        <label>Friendly storage name<input value={draft.name||''} maxLength={80} disabled={readOnly||busy} onChange={e=>field('name',e.target.value)}/></label>
        {draft.type==='smb'&&<>
          <label>NAS hostname or IP<input value={draft.host||''} maxLength={253} disabled={readOnly||busy} autoComplete="off" placeholder="192.168.1.20" onChange={e=>field('host',e.target.value)}/></label>
          <label>SMB port<input aria-label="SMB port" type="number" min={445} max={65535} value={draft.port||445} disabled={readOnly||busy} onChange={e=>field('port',Number(e.target.value))}/><small>Default 445; custom high ports are supported. SMB1 is never enabled.</small></label>
          <label>NAS username<input value={draft.username||''} maxLength={160} disabled={readOnly||busy} autoComplete="off" onChange={e=>field('username',e.target.value)}/></label>
          <label>NAS password<input type="password" value={password} maxLength={1024} disabled={readOnly||busy} autoComplete="new-password" placeholder={draft.password_saved?'Saved securely; leave blank to keep':'Enter NAS password'} onChange={e=>setPassword(e.target.value)}/></label>
          <label>Domain or workgroup (optional)<input value={draft.domain||''} maxLength={100} disabled={readOnly||busy} onChange={e=>field('domain',e.target.value)}/></label>
          <label>Share name<input aria-label="Share name" value={draft.share||''} maxLength={180} disabled={readOnly||busy} placeholder="Backups" onChange={e=>field('share',e.target.value)}/><small>{data.share_notice}</small></label>
          <label>Destination directory<input value={draft.directory||''} maxLength={1024} disabled={readOnly||busy} placeholder="Share root, or choose a folder below" onChange={e=>field('directory',e.target.value)}/></label>
          <label className="backup-check"><input type="checkbox" checked={draft.require_encryption!==false} disabled={readOnly||busy} onChange={e=>field('require_encryption',e.target.checked)}/>Require SMB3 encryption</label>
        </>}
      </div>
      {draft.type==='smb'?<p className="small muted">Use a dedicated NAS account limited to the Market backup directory. Signing is always required. Disable required encryption only for a trusted LAN NAS that supports signed SMB2 but lacks SMB3 encryption. Private LAN addresses are supported; public, loopback and link-local destinations are refused.</p>:<p className="notice">{data.mounted_notice} Choose “Local backups” above to return to the existing directory. New host paths cannot be opened through administration.</p>}
      <div className="backup-actions"><button className="primary" disabled={readOnly||busy||!draft.name||(draft.type==='smb'&&(!draft.host||!draft.username||!draft.share||(!password&&!draft.password_saved)))} onClick={()=>void save()}>Save storage settings</button><button disabled={readOnly||busy||!selected||dirty} onClick={()=>void test()}>Test connection</button><button disabled={readOnly||busy||!selected||dirty||draft.type!=='smb'} onClick={()=>void browse('')}>Browse NAS folders</button></div>
      {currentHealth&&<details open={diagnostics||Boolean(health)} className="backup-policy" role="region" aria-label="Connection test result"><summary>Connection diagnostics</summary><Status tone={!currentHealth.healthy?'warning':Date.now()-new Date(currentHealth.tested_at).getTime()<900000?'success':'neutral'}>{currentHealth.healthy?'Last connection check passed':'Needs attention'}</Status><p>{currentHealth.error}</p><p>Tested: <LocalTime value={currentHealth.tested_at}/></p><dl>{(['read','write','create_directory','rename','delete'] as const).map(k=><div key={k}><dt>{({read:'Read files',write:'Write files',create_directory:'Create folders',rename:'Rename files',delete:'Delete test files'})[k]}</dt><dd>{currentHealth[k]===true?'Verified':currentHealth[k]===false?'Not verified':'Unavailable'}</dd></div>)}<dt>{draft.type==='smb'?'NAS filesystem total':'Backup filesystem total'}</dt><dd>{formatBytes(currentHealth.capacity_bytes)}</dd><dt>Available to this account</dt><dd>{formatBytes(currentHealth.available_bytes)}</dd></dl>{currentHealth.cleanup_pending&&<p className="notice">A uniquely named .market-test artifact could not be removed. Restore NAS access and test again; existing backups were preserved.</p>}</details>}
      {browsing&&<section className="backup-policy" aria-label="Choose NAS folder"><h3>Choose a backup folder</h3><nav aria-label="NAS folder breadcrumbs"><button disabled={busy} onClick={()=>void browse('')}>Share root</button>{path.split('/').filter(Boolean).map((part,i,parts)=><button disabled={busy} key={i} onClick={()=>void browse(parts.slice(0,i+1).join('/'))}>{part}</button>)}</nav>{folders.length?<ul className="nas-folders">{folders.map(name=><li key={name}><button disabled={busy} onClick={()=>void browse([path,name].filter(Boolean).join('/'))}>▸ {name}</button></li>)}</ul>:<p>No subfolders in this directory.</p>}{next!==null&&<button disabled={busy} onClick={()=>void browse(path,next)}>Load more folders</button>}<div className="backup-actions"><button disabled={busy||readOnly} onClick={()=>{field('directory',path);setBrowsing(false);setNotice('Folder selected. Save storage settings, then test the selected directory.');}}>Use this folder</button><label>New folder name<input value={folder} maxLength={180} onChange={e=>setFolder(e.target.value)} disabled={busy||readOnly}/></label><button disabled={busy||readOnly||!folder||folder.includes('/')} onClick={()=>void run(async()=>{await api('/admin/backups/storage/mkdir','POST',{id:selected,directory:[path,folder].filter(Boolean).join('/')});setFolder('');setNotice('Folder created. Browse again to view it.');})}>Create NAS folder</button></div></section>}
      <button disabled={busy} onClick={()=>{setConfiguring(false);setPassword('');setBrowsing(false);}}>Close storage settings</button>
    </div></ConfirmationDialog>}
    {plan&&<ConfirmationDialog title="Review backup migration" onClose={()=>{if(!busy)setPlan(null);}}><p><strong>{data?.destinations.find(d=>d.id===plan.source_id)?.name||'Source storage'} → {data?.destinations.find(d=>d.id===plan.destination_id)?.name||'Destination storage'}</strong></p><p>Copy {plan.count.toLocaleString()} backups ({formatBytes(plan.bytes)}) to the selected destination. Original copies will be preserved.</p>{Boolean(plan.reusable_bytes)&&<p>{formatBytes(plan.reusable_bytes||0)} already exists and will be checked before reuse. {formatBytes(plan.required_bytes??plan.bytes)} still needs to be copied.</p>}<p>Destination available: {formatBytes(plan.available_bytes)}. {plan.enough_space?'Capacity check passed, or capacity is unavailable and will be checked during writes.':'Insufficient space for the copy and safety reserve.'}</p><p>The current destination remains active if copying or checksum verification fails. Scheduled backups wait while migration is running.</p><button disabled={busy} onClick={()=>setPlan(null)}>Cancel</button><button className="primary" disabled={busy||readOnly||!plan.enough_space} onClick={()=>void run(async()=>{await api('/admin/backups/storage/migrate','POST',{id:plan.destination_id,preview:plan});setPlan(null);setNotice('Migration queued. Progress appears below.');})}>Copy, verify and activate</button></ConfirmationDialog>}
    {remove&&lastMigration?.id&&<ConfirmationDialog title="Remove verified original copies" onClose={()=>{if(!busy)setRemove(false);}}><p>This permanently removes the original copies named by this migration, after rechecking the destination checksums. Active recovery references cannot be overridden.</p><p>{lastMigration.plan?.protected_count||0} original copies are protected.</p>{Boolean(lastMigration.plan?.protected_count||lastMigration.plan?.reserved_count)&&<label className="backup-check"><input type="checkbox" checked={protectedOriginalAck} onChange={e=>setProtectedOriginalAck(e.target.checked)}/>I explicitly authorize deleting protected original copies{lastMigration.plan?.reserved_count?' and their inactive recovery reservations':''}.</label>}<label>Type REMOVE VERIFIED ORIGINALS<input value={confirmation} onChange={e=>setConfirmation(e.target.value)}/></label><button disabled={busy} onClick={()=>setRemove(false)}>Cancel</button><button disabled={readOnly||busy||confirmation!=='REMOVE VERIFIED ORIGINALS'||(Boolean(lastMigration.plan?.protected_count||lastMigration.plan?.reserved_count)&&!protectedOriginalAck)} onClick={()=>void run(async()=>{const result=await api<{status?:string;results?:{status:string}[]}>('/admin/backups/storage/remove-originals','POST',{id:lastMigration.id,confirmation,confirm_protected:protectedOriginalAck,confirm_reserved:protectedOriginalAck});setRemove(false);setNotice(result.status==='queued'?'Original copy cleanup queued. Progress and individual results appear below.':`${result.results?.filter(r=>r.status==='deleted').length||0} originals removed; results saved.`);})}>Confirm removal of original copies</button></ConfirmationDialog>}
  </section>;
}

/** Capacity comes from one provider filesystem; it never attributes shared paths twice. */
export function StorageCapacity({health,marketBytes}:{health?:Health;marketBytes?:number|null}) {
  const total=health?.capacity_bytes;
  const free=health?.free_bytes;
  const available=health?.available_bytes;
  const measurable=typeof total==='number'&&Number.isFinite(total)&&total>0&&typeof free==='number'&&Number.isFinite(free)&&free>=0&&free<=total;
  const used=measurable?total-free:null;
  const percent=measurable?used!/total*100:null;
  const breakdown=used!==null&&typeof marketBytes==='number'&&marketBytes>=0&&marketBytes<=used;
  const marketPercent=breakdown?marketBytes!/total!*100:0;
  return <div className="storage-capacity">
    <div className="storage-capacity-heading"><strong>{percent===null?'Capacity unavailable':`${percent.toFixed(1)}% used`}</strong><span>{formatBytes(total)} total</span></div>
    {percent!==null?<div className="storage-capacity-track" role="meter" aria-label="Filesystem capacity used" aria-valuenow={Math.round(percent)} aria-valuemin={0} aria-valuemax={100} aria-valuetext={`${formatBytes(used)} used; ${formatBytes(free)} free; ${formatBytes(total)} total`}><>{breakdown&&<span className="capacity-market" style={{width:`${marketPercent}%`}} title={`Market archives at this location: ${marketBytes?.toLocaleString()} bytes`}/>}<span style={{width:`${percent-marketPercent}%`}} title={`${(used!-(breakdown?marketBytes!:0)).toLocaleString()} bytes ${breakdown?'other filesystem usage':'used'}`}/></><i title={`${free?.toLocaleString()} bytes free`}/></div>:<div className="storage-capacity-track unknown" aria-hidden="true"/>}
    <div className="storage-capacity-values"><span><i className="used"/>{formatBytes(used)} used</span><span><i/>{formatBytes(available)} available to this account</span></div>
    {breakdown&&<p className="small muted"><span className="capacity-teal-key"/> Market archives at this location · remaining used space includes all other files</p>}{health&&<p className="small muted">Measured at <LocalTime value={health.tested_at}/></p>}
  </div>;
}

/** A copied backend count means copy + checksum verification finished for that archive. */
export function MigrationProgress({migration,destinations=[]}:{migration:Migration;destinations?:Destination[]}) {
  const status=migration.status||'unknown';
  const completed=status==='succeeded';
  const count=migration.plan?.count;
  const bytes=migration.plan?.bytes;
  const copied=migration.copied??0;
  const copiedBytes=migration.bytes_copied??0;
  const validBytes=typeof bytes==='number'&&bytes>0&&copiedBytes>=0&&copiedBytes<=bytes;
  const percent=validBytes?copiedBytes/bytes*100:null;
  const failed=['failed','interrupted','cancelled'].includes(status);
  const source=destinations.find(d=>d.id===migration.plan?.source_id)?.name;
  const destination=destinations.find(d=>d.id===migration.plan?.destination_id)?.name;
  return <div className={`storage-migration-progress ${failed?'needs-attention':''}`}>
    <div className="backup-heading"><strong>{source&&destination?`${source} → ${destination}`:'Backup migration'}</strong><Status tone={completed?'success':failed?'error':['queued','running'].includes(status)?'warning':'neutral'}>{({queued:'Queued',running:'Copying & verifying',succeeded:'Destination activated',failed:'Migration failed',interrupted:'Interrupted · review required',cancelled:'Cancelled'} as Record<string,string>)[status]||status}</Status></div>
    <ol className="storage-migration-stages" aria-label="Migration stages">
      <li className={migration.plan?'complete':''}><span aria-hidden="true">{migration.plan?'✓':'1'}</span>Validate destination</li>
      <li className={migration.plan?'complete':''}><span aria-hidden="true">{migration.plan?'✓':'2'}</span>Prepare inventory</li>
      <li className={completed?'complete':status==='running'?'current':''}><span aria-hidden="true">{completed?'✓':'3'}</span>Copy backups</li>
      <li className={completed?'complete':status==='running'?'current':''}><span aria-hidden="true">{completed?'✓':'4'}</span>Verify checksums</li>
      <li className={completed?'complete':''}><span aria-hidden="true">{completed?'✓':'5'}</span>Activate storage</li>
      <li><span aria-hidden="true">6</span>Review originals</li>
    </ol>
    <div className="storage-capacity-heading"><strong>{copied.toLocaleString()} / {count?.toLocaleString()??'unknown'} recovery points copied and verified</strong><span>{formatBytes(copiedBytes)} / {formatBytes(bytes)}{percent!==null?` · ${percent.toFixed(1)}%`:''}</span></div>
    <progress max={100} {...(percent!==null?{value:percent}:{})} aria-label="Copied and checksum-verified archive bytes"/>
    <p className="small muted">Progress updates after each archive has been fully copied and checksum verified. Transfer speed, current-file progress and time remaining are not reported by this worker.</p>
    <p className="small muted">Started: <LocalTime value={migration.started_at||migration.requested_at}/>{migration.finished_at&&<> · Finished: <LocalTime value={migration.finished_at}/></>}</p>
    {failed&&<p className="notice error" role="alert">{migration.error||'The operation stopped. Review storage access, test the destination and preview a new migration.'} Original recovery copies remain preserved.</p>}
    {status==='running'&&<p className="small">You can leave this page. The backup manager continues the operation independently.</p>}
  </div>;
}
