import { lazy, Suspense, useMemo, useRef, useState } from 'react';
import { DeferredChart } from './deferred-chart';
import './backup-redesign.css';
import { backupQueryParams, type BackupFilters } from './backup-data';
import { type PaginationState, type RowSelectionState, type SortingState, functionalUpdate } from '@tanstack/react-table';
import { DataTable } from './data-table';
import { Loading } from './loading';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './api';
import { LocalTime, Status } from './admin-table';
import { ConfirmationDialog } from './confirmation-dialog';
import { formatBytes } from './size';

interface PolicyValues {
  enabled:boolean; interval_seconds:number; daily:number; weekly:number; monthly:number;
  max_bytes:number|null; minimum_recovery_points:number; warning_free_bytes:number;
}
interface Policy extends PolicyValues {revision:number}
export interface Backup {
  id:string; filename:string; type:string; origin:string; created_at:string|null; bytes:number|null;
  sha256:string|null; verification:string; restoration_verified_at:string|null; protected:boolean;
  active_use?:boolean;reserved?:boolean;current_recovery?:boolean;required_by:string[]; eligible:boolean; reason:string;storage_id?:string;storage_name?:string;
}
export interface BackupOverview {
  protected_count?:number;protected_bytes?:number;storage_error?:string;storage?:{restore_available?:boolean};
  measured_at?:string; policy:Policy; inventory_stale?:boolean; service_status:string; last_success:string|null; last_restoration_verified_at:string|null;
  inventory_by_storage?:Record<string,{count:number;bytes:number|null}>;matched_total?:number;
  reliability?:{since:string;days:{day:string;succeeded:number;failed:number}[];attempts:{at:string;status:string;origin:string;backup_id:string|null;bytes:number|null}[];truncated:boolean;schedule_history_available:boolean;notice:string};
  total:number; total_bytes:number; items:Backup[]; artifact_count:number; artifacts:{name:string;type:string}[];
  filesystem:{capacity_bytes:number|null;available_bytes:number|null;reserve_bytes:number;filesystem_id:string;measurement:string};
  storage_pressure:boolean; next_scheduled_at:string|null; estimate_bytes:number;
  job:{status?:string;error?:string;kind?:string;result?:{results:{id:string;status:string;error?:string}[]}};
  preview:{candidates:{id:string;filename:string;bytes:number}[];reclaimable_bytes:number;budget_exceeded:boolean;scope:string};
  receipts:{id:string;at:string;actor:string;action:string;detail:unknown}[];
}
const BackupCalendar = lazy(() => import('./backup-calendar').then(module=>({default:module.BackupCalendar})));
const GIB=1024**3;
const verification=(row:Backup)=>row.restoration_verified_at?'Restore rehearsal recorded':row.verification==='archive_integrity_verified'?'Archive integrity checked':row.verification==='legacy_metadata_only'?'Legacy metadata only':'Verification unavailable';

export function useBackupOverview(offset=0,filters?:BackupFilters,limit=100,enabled=true) {
  const params=backupQueryParams(offset,filters,limit);
  const filtered=params.size>2;
  return useQuery({enabled,queryKey:filtered?['private','backup-management',offset,params.toString()]:['private','backup-management',offset,limit],queryFn:({signal})=>api<BackupOverview>(`/admin/backups?${params}`,'GET',undefined,signal),staleTime:30000,refetchInterval:q=>filtered?false:(['queued','running'].includes(q.state.data?.job.status||'')||(q.state.data?.inventory_stale&&q.state.data.service_status==='operation_busy'))?5000:60000,retry:false});
}

export function BackupCreateButton({readOnly=false,label='Create Backup'}:{readOnly?:boolean;label?:string}) {
  const client=useQueryClient();
  const query=useBackupOverview(), [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const data=query.data;
  async function create(){setBusy(true);setError('');try{await api('/admin/backups/create','POST',{});setOpen(false);await client.invalidateQueries({queryKey:['private','backup-management']});}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  return <><button className="primary" disabled={readOnly||busy||!data||['queued','running'].includes(data.job.status||'')} onClick={()=>setOpen(true)}>{label}</button>{open&&data&&<ConfirmationDialog title="Create manual backup" onClose={()=>{if(!busy)setOpen(false);}}><p>Create a consistent, protected PostgreSQL recovery point with a SHA-256 manifest. It is excluded from scheduled rotation.</p><p>Required allowance: {formatBytes(data.estimate_bytes)} plus {formatBytes(data.filesystem.reserve_bytes)} safety reserve.</p>{error&&<p role="alert" className="notice error">{error}</p>}<button disabled={busy} onClick={()=>setOpen(false)}>Cancel</button><button className="primary" disabled={busy||readOnly} onClick={()=>void create()}>Queue protected backup</button></ConfirmationDialog>}</>;
}

export function BackupManagement({readOnly=false,destinations=[]}:{readOnly?:boolean;destinations?:{id:string;name:string}[]}) {
  const [error,setError]=useState(''), [notice,setNotice]=useState(''), [busy,setBusy]=useState(false);
  const [selected,setSelected]=useState<Backup|null>(null), [intent,setIntent]=useState<'delete'|'details'|'protect'|null>(null), [confirmation,setConfirmation]=useState('');
  const [policyOpen,setPolicyOpen]=useState(false);
  const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize: 10 });
  const [sorting,setSorting] = useState<SortingState>([{ id: 'created', desc: true }]);
  const [search,setSearch]=useState(''),[storage,setStorage]=useState('all'),[protection,setProtection]=useState('all'),[verified,setVerified]=useState('all'),[backupType,setBackupType]=useState('all');
  const [searchTerm,setSearchTerm]=useState('');
  const [protectedAck,setProtectedAck]=useState(false),[recoveryAck,setRecoveryAck]=useState(false),[bulk,setBulk]=useState<Backup[]>([]),[bulkReview,setBulkReview]=useState(false);
  const client=useQueryClient();
  const overview=useBackupOverview();
  const sort = `${sorting[0]?.id === 'bytes' ? 'bytes' : 'created'}_${(sorting[0]?.desc ?? true) ? 'desc' : 'asc'}`;
  const query=useBackupOverview(pagination.pageIndex * pagination.pageSize,{search:searchTerm,storage,protection,verified,backupType,sort},pagination.pageSize);
  const data=overview.data||query.data;
  const destinationChoices = new Map([
    ...(data?.items||[]).map(row=>[row.storage_id||'local',row.storage_name||'Local backups'] as const),
    ...destinations.map(row=>[row.id,row.name] as const),
  ]);
  const selectedRows: RowSelectionState = Object.fromEntries(bulk.map(row => [row.id, true]));
  const canSelect = (row: Backup) => row.verification === 'archive_integrity_verified' && !(row.active_use ?? Boolean(row.required_by.length));
  function resetPage() { setPagination(previous => ({ ...previous, pageIndex: 0 })); }
  function showInventory(date: string) {
    setSearch(date); setSearchTerm(date); setStorage('all'); setProtection('all'); setVerified('all'); setBackupType('all');
    resetPage();
    document.getElementById('backup-inventory')?.focus({ preventScroll: true });
    document.getElementById('backup-inventory')?.scrollIntoView({ block: 'start' });
  }
  async function act(path:string,body:unknown) {
    setBusy(true);setError('');setNotice('');
    try {
      const result=await api<{status?:string;unlinked_bytes?:number;archive_removed?:boolean;manifest_removed?:boolean;results?:{id:string;status:string;error?:string}[]}>(`/admin/backups${path}`,'POST',body);
      setNotice(result.status==='queued'&&path.includes('delete')?'Deletion queued. Each backup is verified before removal; progress and results appear below.':result.results?result.results.map(r=>`${bulk.find(b=>b.id===r.id)?.filename||r.id}: ${r.status}${r.error?` — ${r.error}`:''}`).join('; '):result.status==='partial_failure'?`Partial deletion: archive ${result.archive_removed?'removed':'retained'}, manifest ${result.manifest_removed?'removed':'retained'}. Receipt saved; review operations before retrying.`:result.unlinked_bytes!==undefined?`Archive and manifest removed. ${formatBytes(result.unlinked_bytes)} unlinked; filesystem availability may differ.`:path==='/create'?'Manual backup queued. Progress is shown below.':'Backup settings updated.');
      setIntent(null);setSelected(null);setBulkReview(false);if(path==='/policy')setPolicyOpen(false);setBulk([]);resetPage();await client.invalidateQueries({queryKey:['private','backup-management']});
    } catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  const detailsTrigger = useRef<HTMLElement | undefined>(undefined);
  function choose(row: Backup, action: typeof intent, trigger?: HTMLElement) {
    if (!intent) detailsTrigger.current = trigger;
    setSelected(row); setIntent(action); setConfirmation(''); setProtectedAck(false); setRecoveryAck(false); setError('');
  }
  const fs=data?.filesystem;
  function filterChange(setter:(s:string)=>void,value:string) { setter(value); resetPage(); }
  return <section className="backup-management recovery-page" aria-label="Backup Management">
    <div className="backup-heading"><div><h2>Recovery points</h2><p className="muted">Find, verify and protect backup archives.</p></div><div className="backup-actions"><button onClick={()=>void client.invalidateQueries({queryKey:['private','backup-management']})} disabled={busy}>Refresh backups</button><button onClick={()=>setPolicyOpen(true)} disabled={!data}>Backup Policy</button><BackupCreateButton readOnly={readOnly||busy} label="Create manual backup"/></div></div>
    {!data&&overview.isPending&&<Loading label="Loading backup inventory and recorded outcomes…"/>}
    {!data&&overview.error&&<p className="notice" role="alert">{overview.error.message}. Storage measurements and backup history are unavailable. Use Refresh backups to retry.</p>}
    {data?.storage_error&&<p role="alert" className="notice error">{data.storage_error}</p>}
    {error&&<p className="notice error" role="alert">{error}</p>}{notice&&<p className="notice" role="status">{notice}</p>}
    {data&&fs&&<>
      <div className="backup-cards recovery-summary">
        <article><span>Recovery points</span><strong>{data.total.toLocaleString()}</strong><small>{formatBytes(data.total_bytes)} of archive storage</small></article>
        <article><span>Protected copies</span><strong>{data.protected_count??'Unknown'}</strong><small>{formatBytes(data.protected_bytes??null)} protected</small></article>
        <article><span>Latest successful backup</span><strong><LocalTime value={data.last_success}/></strong><small>{data.inventory_stale?'Inventory is stale':'Recorded backup outcome'}</small></article>
        <article><span>Latest restore verification</span><strong><LocalTime value={data.last_restoration_verified_at}/></strong><small>Successful isolated restoration</small></article>
      </div>
      <div className="recovery-visuals">
        <BackupHistory items={data.items} attempts={data.reliability?.attempts||[]} stale={Boolean(data.inventory_stale)} onSelect={(row,trigger)=>choose(row,'details',trigger)}/>
        <Suspense fallback={<Loading label="Loading backup calendar…"/>}>
          <BackupCalendar data={data} refreshing={overview.isFetching} error={overview.error?.message} onSelect={(row,trigger)=>choose(row,'details',trigger)} onShowInventory={showInventory}/>
        </Suspense>
      </div>
      <div className="recovery-policy-summary"><div><strong>{data.policy.enabled?`Automatic backups every ${data.policy.interval_seconds/3600} hours`:'Automatic backups disabled'}</strong><span>{data.policy.daily} daily · {data.policy.weekly} weekly · {data.policy.monthly} monthly · minimum {data.policy.minimum_recovery_points} recovery points</span></div></div>
      {(data.storage_pressure||data.preview.budget_exceeded)&&<p className="notice" role="status"><strong>Storage pressure.</strong> New backups pause if the full replacement and reserve cannot fit. No recovery point is deleted to make room automatically. Estimated replacement allowance: {formatBytes(data.estimate_bytes)}.</p>}
      {data.inventory_stale&&<p className="notice" role="status">{data.service_status==='storage_unavailable'?'Backup storage is unavailable. The last successful inventory is preserved; reconnect through Backup Storage and refresh.':'A backup operation is in progress. Inventory and storage show the last completed measurement; actions recheck availability after completion.'}</p>}
      {['queued','running','failed','interrupted'].includes(data.job.status||'')&&<section className="notice recovery-job" aria-label="Latest backup operation"><strong>{data.job.kind||'Backup'} operation · {data.job.status}</strong>{['queued','running'].includes(data.job.status||'')&&<><progress aria-label="Backup operation progress"/><span className="small muted">The backup manager continues this operation when you leave the page.</span></>}{data.job.error&&<p role="alert">{data.job.error}</p>}</section>}{data.job.kind==='deletion'&&<p role="status">Backup deletion: {data.job.status}. {data.job.result?.results.map(r=>`${r.status}${r.error?`: ${r.error}`:''}`).join('; ')}</p>}
      <section className="panel padded recovery-inventory" aria-labelledby="backup-inventory">
        <div className="backup-inventory-heading"><h3 id="backup-inventory" tabIndex={-1}>Backup inventory</h3>
          <button disabled={readOnly||busy||!bulk.length} onClick={()=>{setBulkReview(true);setConfirmation('');setProtectedAck(false);setRecoveryAck(false);}}>Delete selected ({bulk.length})</button>
          {bulk.length > 0 && <button disabled={busy} onClick={() => setBulk([])}>Clear selection</button>}
          <p className="muted">Times in your local timezone{data.inventory_stale?' · Last known inventory':''}. Select up to 50 archives for review.</p>
        </div>
        <form className="recovery-search" onSubmit={event=>{event.preventDefault();filterChange(setSearchTerm,search.trim());}}>
          <label>Search recovery points<input type="search" placeholder="Date, filename or destination" value={search} maxLength={190} onChange={e=>{setSearch(e.target.value);if(!e.target.value)filterChange(setSearchTerm,'');}}/></label>
          <button type="submit">Search</button>
          {searchTerm && <button type="button" onClick={()=>{setSearch('');filterChange(setSearchTerm,'');}}>Clear search</button>}
        </form>
        <details className="recovery-filter-menu"><summary>Inventory filters</summary>
          <div className="recovery-filters">
            <label>Destination<select value={storage} onChange={e=>filterChange(setStorage,e.target.value)}><option value="all">All destinations</option>{Array.from(destinationChoices).map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>
            <label>Protection<select value={protection} onChange={e=>filterChange(setProtection,e.target.value)}><option value="all">All protection</option><option value="protected">Protected</option><option value="unprotected">Unprotected</option></select></label>
            <label>Verification<select value={verified} onChange={e=>filterChange(setVerified,e.target.value)}><option value="all">All verification</option><option value="restored">Restore verified</option><option value="integrity">Integrity checked</option><option value="unknown">Unverified / legacy</option></select></label>
            <label>Backup type<select value={backupType} onChange={e=>filterChange(setBackupType,e.target.value)}><option value="all">All types</option>{['manual','scheduled','release','restore-verification','legacy','unknown'].map(type=><option key={type} value={type}>{type.replaceAll('-',' ')}</option>)}</select></label>
          </div>
        </details>
        <DataTable<Backup> compact label="Managed backup archives" data={query.data?.items||[]}
          getRowId={row=>row.id}
          loading={query.isFetching} error={query.error ? `${query.error.message}. Storage measurements and archive eligibility are unavailable until the operations service responds.` : undefined}
          emptyMessage={data.total===0?'No managed archives are available.':'No recovery points match these filters.'}
          server={{
            rowCount: query.data?.matched_total ?? query.data?.total ?? 0, pagination, sorting,
            onPaginationChange: setPagination,
            onSortingChange: updater => { setSorting(previous => functionalUpdate(updater, previous)); resetPage(); },
          }}
          selection={{
            state: selectedRows, canSelect: row => canSelect(row) && (bulk.length < 50 || Boolean(selectedRows[row.id])), label: row => `Select ${row.filename}`,
            selectPageLabel: 'Select eligible backups on this page', disabled: readOnly||busy||query.isFetching||Boolean(query.error),
            onChange: updater => setBulk(previous => {
              const next = functionalUpdate(updater, Object.fromEntries(previous.map(row => [row.id,true])));
              const records = new Map(previous.map(row=>[row.id,row]));
              for (const row of query.data?.items ?? []) if (canSelect(row)) records.set(row.id,row);
              return [...records.values()].filter(row=>next[row.id]).slice(0,50);
            }),
          }}
          columns={[
            {id:'created', accessorKey:'created_at', header:'Backup date and time', enableHiding:false, cell:({row})=><><LocalTime value={row.original.created_at}/><span className="backup-file-label">{row.original.filename}</span></>},
            {accessorKey:'type', header:'Type', enableSorting:false, cell:({row})=>row.original.type.replaceAll('-',' ')},
            {accessorKey:'bytes', header:'Size', meta:{numeric:true}, cell:({row})=>formatBytes(row.original.bytes)},
            {accessorKey:'storage_name', header:'Destination', enableSorting:false, cell:({row})=>row.original.storage_name||'Local backups'},
            {accessorKey:'verification', header:'Verification', enableSorting:false, cell:({row:{original:row}})=><Status tone={row.restoration_verified_at?'success':row.verification==='archive_integrity_verified'?'neutral':'warning'}>{verification(row)}</Status>},
            {accessorKey:'protected', header:'Protection', enableSorting:false, cell:({row:{original:row}})=><><Status tone={row.protected?'success':'neutral'}>{row.protected?'Protected':'Unprotected'}</Status>{(row.active_use??Boolean(row.required_by.length))&&<span className="backup-file-label">In active use</span>}</>},
            {id:'actions', header:'Actions', enableHiding:false, enableSorting:false, cell:({row:{original:row}})=><div className="backup-row-actions">
              <button onClick={event=>choose(row,'details',event.currentTarget)}>Details</button>
              <button disabled={readOnly||busy||row.type==='legacy'||row.verification!=='archive_integrity_verified'||Boolean(row.required_by.length)} onClick={event=>choose(row,'protect',event.currentTarget)}>{row.protected?'Unprotect':'Protect'}</button>
              <button disabled={readOnly||busy||!canSelect(row)} onClick={event=>choose(row,'delete',event.currentTarget)}>Delete</button>
            </div>},
          ]}
        />
      </section>
      {policyOpen&&<ConfirmationDialog title="Backup Policy" onClose={()=>{if(!busy)setPolicyOpen(false);}}>{error&&<p className="notice error" role="alert">{error}</p>}<PolicyEditor key={data.policy.revision} policy={data.policy} disabled={busy||readOnly} save={body=>void act('/policy',body)}/><button onClick={()=>setPolicyOpen(false)}>Close backup policy</button></ConfirmationDialog>}
      <details className="backup-disclosure"><summary>Retention preview & emergency cleanup</summary><p>{data.preview.scope}</p><p><strong>{data.preview.candidates.length} scheduled archives</strong> outside the current tiers · {formatBytes(data.preview.reclaimable_bytes)} estimated reclaimable.</p>{data.preview.candidates.length>0&&<ul>{data.preview.candidates.map(row=><li key={row.id}>{row.filename} · {formatBytes(row.bytes)}</li>)}</ul>}<p className="small muted">This is a dry run. Automatic removal follows a successfully completed, integrity-checked scheduled replacement. For emergency cleanup, explicitly select an eligible archive’s Delete action and confirm its name. Each request rechecks recovery safeguards. Legacy archives require a separate operator procedure.</p></details>
      <details className="backup-disclosure"><summary>Service details & audit receipts</summary><dl><dt>Latest backup operation</dt><dd>{data.job.kind||'Backup'} · {data.job.status||'Unknown'}</dd><dt>Inventory measured</dt><dd><LocalTime value={data.measured_at}/></dd><dt>Next scheduled backup</dt><dd><LocalTime value={data.next_scheduled_at}/></dd><dt>Replacement allowance</dt><dd>{formatBytes(data.estimate_bytes)} · measured archives plus margin; first backup uses 1 GiB</dd><dt>Filesystem measurement</dt><dd>{fs.measurement} · device {fs.filesystem_id}</dd><dt>Unmanaged artifacts</dt><dd>{data.artifact_count} incomplete files or orphan manifests; excluded from automatic deletion</dd></dl>{data.artifacts.length>0&&<ul>{data.artifacts.map((artifact,i)=><li key={i}>{artifact.name} · {artifact.type.replaceAll('_',' ')}</li>)}</ul>}<ol className="backup-receipts">{data.receipts.map(row=><li key={row.id}><LocalTime value={row.at}/> · {row.action} · {row.actor}</li>)}</ol><p className="small muted">Local archives contain private account data. Use an owner-managed encrypted off-host copy for disaster recovery.</p></details>
    </>}
    {selected&&intent&&<div className={intent==='details'?'recovery-drawer':undefined}><ConfirmationDialog returnFocus={detailsTrigger.current} closeLabel={intent==='details'?'Close details':'Close'} title={intent==='delete'?'Delete backup archive':intent==='protect'?(selected.protected?'Unprotect recovery archive':'Protect recovery archive'):'Backup details'} onClose={()=>{if(!busy){setSelected(null);setIntent(null);}}}>
      <p className="backup-filename"><strong>{selected.filename}</strong></p>
      {intent==='details'?<><dl><dt>Backup identifier</dt><dd className="backup-hash">{selected.id}</dd><dt>Storage destination</dt><dd>{selected.storage_name||'Local backups'}</dd><dt>Backup type</dt><dd>{selected.type}</dd><dt>Created</dt><dd><LocalTime value={selected.created_at}/></dd><dt>Origin</dt><dd>{selected.origin}</dd><dt>Compressed size</dt><dd>{formatBytes(selected.bytes)}</dd><dt>Verification</dt><dd>{verification(selected)}</dd><dt>Restore rehearsal</dt><dd><LocalTime value={selected.restoration_verified_at}/></dd><dt>SHA-256</dt><dd className="backup-hash">{selected.sha256||'Unavailable'}</dd><dt>Protection and deletion</dt><dd>{selected.protected?'Protected. ':'Unprotected. '}{selected.reason}</dd><dt>Recovery dependencies</dt><dd>{selected.required_by.length?selected.required_by.join(', '):'None recorded'}</dd></dl><p className="small">Archive integrity checks decode the dump and record SHA-256. Only a successful isolated restoration records a restore rehearsal.</p>{selected.verification==='archive_integrity_verified'&&<div className="backup-actions"><a className="button" href={`/api/v1/admin/backups/${selected.id}/download`}>Download archive</a>{data?.storage?.restore_available&&<button disabled={readOnly||busy} onClick={()=>void act('/restore-test',{id:selected.id})}>Verify isolated restore</button>}<a className="button" href={`/api/v1/admin/backups/${selected.id}/manifest`} target="_blank" rel="noreferrer">Open restore manifest</a></div>}<div className="backup-actions"><button disabled={readOnly||busy||selected.type==='legacy'||selected.verification!=='archive_integrity_verified'||Boolean(selected.required_by.length)} onClick={()=>choose(selected,'protect')}>{selected.protected?'Unprotect':'Protect'}</button><button disabled={readOnly||busy||selected.verification!=='archive_integrity_verified'||(selected.active_use??Boolean(selected.required_by.length))} onClick={()=>choose(selected,'delete')}>{selected.protected?'Delete protected backup':'Delete backup'}</button></div></>:<>
        <p>{intent==='delete'?`Removes this archive and its matching manifest. Up to ${formatBytes(selected.bytes)} may be reclaimed. The deletion receipt is retained.`:selected.protected?'Allows this archive to become eligible for deletion if recovery safeguards permit. Manual and release archives are excluded from automatic rotation.':'Excludes this archive from automatic rotation. Explicitly acknowledged administrator deletion remains available.'}</p>
        <p className="notice">Live PostgreSQL data and auction history stay intact.</p>
        {intent==='delete'&&<><p className="notice">Deletion can remove the newest or last known-good backup. Check another recovery copy before proceeding. Protected backups require a separate acknowledgement; Backups in active use cannot be deleted. Deleting the current recovery copy after its lease expires pauses cleanup until another copy is verified.</p>{(selected.protected||selected.reserved)&&<label className="backup-check"><input type="checkbox" checked={protectedAck} onChange={e=>setProtectedAck(e.target.checked)}/>I explicitly authorize deleting this protected backup{selected.reserved?' and its inactive recovery reservations':''}.</label>}<label className="backup-check"><input type="checkbox" checked={recoveryAck} onChange={e=>setRecoveryAck(e.target.checked)}/>I acknowledge the risk of removing the newest or last known-good backup.</label></>}
        <label>Type {selected.filename} to confirm<input value={confirmation} onChange={e=>setConfirmation(e.target.value)} autoComplete="off"/></label>
        {error&&<p className="notice error" role="alert">{error}</p>}
        <button disabled={busy} onClick={()=>{setSelected(null);setIntent(null);}}>Cancel</button><button className="primary" disabled={readOnly||busy||confirmation!==selected.filename||(intent==='delete'&&(!recoveryAck||((selected.protected||selected.reserved)&&!protectedAck)))} onClick={()=>void act(`/${selected.id}/${intent}`,intent==='delete'?{confirmation,...(protectedAck?{confirm_protected:true}:{}),...(protectedAck&&selected.reserved?{confirm_reserved:true}:{}),...(recoveryAck?{confirm_recovery_loss:true}:{})}:{protected:!selected.protected})}>{intent==='delete'?'Confirm archive deletion':selected.protected?'Confirm unprotect':'Confirm protection'}</button>
      </>}
    </ConfirmationDialog></div>}
    {bulkReview&&<ConfirmationDialog title="Delete selected backups" onClose={()=>{if(!busy)setBulkReview(false);}}><p>Permanently delete these {bulk.length} recovery copies and their manifests. The result is reported separately for each backup. Active recovery references remain protected.</p><ul>{bulk.map(row=><li key={row.id}>{row.filename} · {formatBytes(row.bytes)} · {row.protected?'Protected':'Unprotected'} · {row.storage_name||'Local backups'}</li>)}</ul>{bulk.some(r=>r.protected||r.reserved)&&<label className="backup-check"><input type="checkbox" checked={protectedAck} onChange={e=>setProtectedAck(e.target.checked)}/>I explicitly authorize deleting the selected protected backups{bulk.some(r=>r.reserved)?' and their inactive recovery reservations':''}.</label>}<label className="backup-check"><input type="checkbox" checked={recoveryAck} onChange={e=>setRecoveryAck(e.target.checked)}/>I acknowledge this may remove the newest or last known-good backup.</label><label>Type DELETE SELECTED BACKUPS<input value={confirmation} onChange={e=>setConfirmation(e.target.value)}/></label><button disabled={busy} onClick={()=>setBulkReview(false)}>Cancel</button><button className="primary" disabled={readOnly||busy||confirmation!=='DELETE SELECTED BACKUPS'||!recoveryAck||(bulk.some(r=>r.protected||r.reserved)&&!protectedAck)} onClick={()=>void act('/delete-selected',{items:bulk.map(row=>({id:row.id,confirmation:row.filename,confirm_protected:protectedAck,confirm_reserved:protectedAck&&Boolean(row.reserved),confirm_recovery_loss:recoveryAck}))})}>Confirm selected backup deletion</button></ConfirmationDialog>}
  </section>;
}

function PolicyEditor({policy,disabled,save}:{policy:Policy;disabled:boolean;save:(body:unknown)=>void}) {
  const [draft,setDraft]=useState(policy),[review,setReview]=useState(false);
  function number(key:keyof PolicyValues,value:string,scale=1){setDraft({...draft,[key]:value===''&&key==='max_bytes'?null:Math.round(Number(value)*scale)});}
  const changed=JSON.stringify(draft)!==JSON.stringify(policy);
  const valid=Number.isInteger(draft.daily)&&draft.daily>=1&&draft.daily<=365&&draft.interval_seconds>=3600&&draft.interval_seconds<=31*86400&&draft.weekly>=0&&draft.weekly<=104&&draft.monthly>=0&&draft.monthly<=120&&draft.minimum_recovery_points>=1&&draft.minimum_recovery_points<=30&&draft.warning_free_bytes>=2*GIB&&(draft.max_bytes===null||draft.max_bytes>=1024**2);
  return <section className="backup-policy" aria-label="Backup retention policy"><div className="backup-inventory-heading"><h3>Backup retention</h3><Status tone={policy.enabled?'success':'neutral'}>{policy.enabled?'Schedule enabled':'Schedule disabled'}</Status></div><p className="small muted">Applies to new scheduled archives. Keeps the newest archive in each retained UTC day, week or month; tiers overlap. Protected, manual, release and legacy backups stay outside automatic rotation.</p><div className="backup-policy-grid">
    <label className="backup-check"><input type="checkbox" checked={draft.enabled} disabled={disabled} onChange={e=>setDraft({...draft,enabled:e.target.checked})}/>Enable scheduled backups</label>
    <label>Backup interval (hours)<input type="number" min={1} max={744} step={1} value={draft.interval_seconds/3600} disabled={disabled} onChange={e=>number('interval_seconds',e.target.value,3600)}/></label>
    <label>Daily backups to keep<input type="number" min={1} max={365} value={draft.daily} disabled={disabled} onChange={e=>number('daily',e.target.value)}/></label>
    <label>Weekly backups to keep (0 disables)<input type="number" min={0} max={104} value={draft.weekly} disabled={disabled} onChange={e=>number('weekly',e.target.value)}/></label>
    <label>Monthly backups to keep (0 disables)<input type="number" min={0} max={120} value={draft.monthly} disabled={disabled} onChange={e=>number('monthly',e.target.value)}/></label>
    <label>Minimum recovery points<input type="number" min={1} max={30} value={draft.minimum_recovery_points} disabled={disabled} onChange={e=>number('minimum_recovery_points',e.target.value)}/></label>
  </div><details><summary>Storage limits</summary><div className="backup-policy-grid"><label>Maximum managed archive storage (GiB, optional)<input type="number" min={0.001} step="any" value={draft.max_bytes===null?'':draft.max_bytes/GIB} disabled={disabled} onChange={e=>number('max_bytes',e.target.value,GIB)}/></label><label>Warn below available space (GiB)<input type="number" min={2} step="any" value={draft.warning_free_bytes/GIB} disabled={disabled} onChange={e=>number('warning_free_bytes',e.target.value,GIB)}/></label></div><p className="small muted">The fixed 2 GiB safety reserve cannot be lowered. The budget must accommodate both existing archives and a complete new replacement before rotation.</p></details><button disabled={disabled||!changed||!valid} onClick={()=>setReview(true)}>Review backup policy</button>
    {review&&<ConfirmationDialog title="Save backup retention policy" onClose={()=>setReview(false)}><p>Daily: keep {draft.daily}. Weekly: {draft.weekly||'disabled'}. Monthly: {draft.monthly||'disabled'}. Minimum recovery points: {draft.minimum_recovery_points}.</p><p>{draft.enabled?`Enable scheduled backups every ${draft.interval_seconds/3600} hours. The next backup is due one full interval after saving.`:'Scheduled backups will be disabled.'}</p><p>Saving does not delete existing files. Eligible scheduled archives rotate only after a new successful, integrity-checked scheduled backup. Historical data retention remains separate.</p><button onClick={()=>setReview(false)}>Cancel</button><button className="primary" disabled={disabled||!valid} onClick={()=>{const {revision,...values}=draft;save({revision,values});setReview(false);}}>Confirm backup policy</button></ConfirmationDialog>}
  </section>;
}

function BackupHistory({items,attempts,stale,onSelect}:{items:Backup[];attempts:NonNullable<BackupOverview['reliability']>['attempts'];stale:boolean;onSelect:(row:Backup,trigger?:HTMLElement)=>void}) {
 const points=useMemo(()=>items.filter(r=>r.created_at&&r.bytes!==null).sort((a,b)=>Date.parse(a.created_at!)-Date.parse(b.created_at!)),[items]);
 const option=useMemo(()=>({animation:false,grid:{left:65,right:12,top:18,bottom:45},textStyle:{color:'#c8b99f'},tooltip:{trigger:'item',renderMode:'richText',formatter:(params:unknown)=>{const p=params as {dataIndex:number};const row=points[p.dataIndex];return row?`${new Date(row.created_at!).toLocaleString()}\n${formatBytes(row.bytes)} · ${row.type}\n${row.storage_name||'Local backups'}\nSelect to view recovery point`:'';}},xAxis:{type:'category',data:points.map(r=>r.id),axisLabel:{hideOverlap:true,formatter:(_:string,index:number)=>new Date(points[index].created_at!).toLocaleDateString(undefined,{month:'short',day:'numeric'})},axisLine:{lineStyle:{color:'#695036'}}},yAxis:{type:'value',axisLabel:{formatter:(v:number)=>formatBytes(v,1)},splitLine:{lineStyle:{color:'#4d3c2a'}}},series:[{type:'bar',name:'Backup size',barMaxWidth:28,data:points.map(r=>({value:r.bytes,itemStyle:{color:r.storage_id&&r.storage_id!=='local'?'#779a8c':'#c5a263',borderRadius:[3,3,0,0],borderColor:r.origin==='scheduled'?'transparent':'#f2dfb7',borderWidth:r.origin==='scheduled'?0:1}}))}]}),[points]);
 return <section className="panel padded recovery-history" aria-label="Backup size history"><div className="panel-heading"><h3>Backup size history</h3><span className="small muted">{stale?'Stale inventory':'Recorded recovery points'}</span></div>{points.length?<><DeferredChart option={option} label="Individual backup sizes over time; gold local and teal network storage" onSelect={index=>{if(points[index])onSelect(points[index]);}}/><div className="recovery-calendar-legend"><span><i style={{background:'#c5a263'}}/>Local</span><span><i style={{background:'#779a8c'}}/>Network</span></div><details><summary className="small">Select a recovery point without the chart</summary><div className="recovery-chart-points">{points.map(row=><button key={row.id} onClick={event=>onSelect(row,event.currentTarget)}>{new Date(row.created_at!).toLocaleString()} · {formatBytes(row.bytes)}</button>)}</div></details></>:<p className="backup-empty">No timestamped backup size measurements are available.</p>}{attempts.some(r=>r.status==='failed')&&<details><summary className="small">{attempts.filter(r=>r.status==='failed').length} failed attempts in retained execution history</summary><ul className="small">{attempts.filter(r=>r.status==='failed').map((r,index)=><li key={`${r.at}-${index}`}><LocalTime value={r.at}/> · {r.origin||'Unknown trigger'} · Failed (no recovery point)</li>)}</ul></details>}<p className="small muted">Up to 100 latest recovery points, one bar per archive. Outlined bars are manual or release copies. Removed archives and attempts without size measurements are not shown.</p></section>;
}
