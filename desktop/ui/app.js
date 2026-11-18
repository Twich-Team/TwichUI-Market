/* Rendering only. The Rust process owns authentication, scheduling, downloads and credentials. */
const invoke = window.__TAURI__?.core.invoke;
const listen = window.__TAURI__?.event.listen;
const $ = id => document.getElementById(id);
let view = null, editing = false, latestRevision = -1, nativeErrorShown = false, workshopExporting = false, archiveBusy = false, archiveContext = null;
let deliveryBusy=false, reviewedDelivery=null;
let workshopReview=null, workshopBusy=false, workshopIssue=null;
const text = (id, value) => { $(id).textContent = value; };
function message(value, error=false) { $('message').hidden=!value; text('message', value||''); $('message').classList.toggle('error',error); }
const datetime = value => value ? new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}) : 'Unknown';
const at = value => value == null ? null : new Date(value).toISOString();
function marketName(id) { return view?.bootstrap?.markets.find(market=>market.id===id)?.label || (view?.offline_market && view.offline_market.id===id?view.offline_market.label:null) || 'Choose a market'; }
function render(next) {
  if (!next) return;
  // Native events can arrive across threads. Ignore older scheduler revisions only
  // when they belong to the same native process; bootstrap changes remain additive.
  if (next.sync.revision < latestRevision) return;
  latestRevision=next.sync.revision; view=next;
  text('version',`v${view.version}`);
  $('settings-open').disabled=view.quitting;
  const connected=view.connected || view.cache?.has_completed_cache;
  $('welcome').hidden=connected||view.approving;
  $('approval-panel').hidden=!view.approving;
  $('connected-panel').hidden=!connected||view.approving;
  $('approval-open').disabled=!view.approval;
  text('approval-expiry',view.approval ? `Approval expires ${datetime(view.approval.expires_at)}.` : 'Opening a secure connection…');
  const s=view.sync.sync;
  const phase=s.phase;
  const status={ready:['Up to date','Your market is ready.','Prices stay available while you’re offline.'],synchronizing:['Synchronizing','Bringing your cache up to date.','You can close this window. The companion will keep working in the tray.'],cancelling:['Cancelling','Finishing the current request.','Your completed cache stays available.'],paused:['Paused','Your cache is still here.','Automatic updates are paused. You can sync whenever you need to.'],offline:['Cannot reach server','Your cache is still here.','The companion will try again when the next check is due.'],server_unavailable:['Server unavailable','Your cache is still here.','The server needs a little time. The companion will try again.'],sign_in_required:['Sign in again','Reconnect your Market account.','This connection expired or was revoked. Cached prices are preserved.'],choose_market:['Choose a market','Pick an available market.','Open Settings to choose your market or follow your website preference.'],not_connected:['Not connected','Your cache is still here.','Sign in to reconnect and receive new prices.'],recoverable_error:['Needs attention','The last sync could not finish.','Your completed cache is preserved. Try again or save diagnostics in Settings.'],stopped:['Closing','Closing the companion.','Saving progress and closing native connections.']}[phase] || ['Getting ready','Checking your connection.','Your completed cache stays available.'];
  if(phase==='ready'&&!view.cache?.has_completed_cache){status[0]='Ready to sync';status[1]='Bring your market to this PC.';status[2]='Sync now to create your first offline cache.';}
  if(view.refreshing){status[0]='Checking connection';status[1]='Checking your Market account.';status[2]='Your completed cache stays available.';}
  if(!view.cache?.has_completed_cache){
    if(['paused','offline','server_unavailable','not_connected'].includes(phase))status[1]='No offline prices downloaded yet.';
    if(['synchronizing','cancelling','sign_in_required','recoverable_error','stopped'].includes(phase)||view.refreshing)status[2]='Your first completed download will make prices available offline.';
  }
  text('status-label',status[0]);text('status-title',status[1]);text('status-description',status[2]);
  $('status-dot').className=`status-dot ${s.running?'busy':['sign_in_required','recoverable_error','offline','server_unavailable'].includes(phase)?'warning':phase==='paused'?'paused':''}`;
  text('status-tag',s.automatic_sync?'AUTOMATIC':'MANUAL');
  $('sync-progress').hidden=!s.running;$('progress-label').hidden=!s.running;
  text('progress-label',s.pages_completed ? `${s.pages_completed} batch${s.pages_completed===1?'':'es'} safely saved` : 'Checking your account and market…');
  $('sync').disabled=!view.connected || view.refreshing || s.running || s.selected_market==null || phase==='sign_in_required';
  $('sync').hidden=!view.connected||phase==='sign_in_required';$('sign-in-again').hidden=view.connected&&phase!=='sign_in_required';
  $('pause').hidden=s.running;$('cancel').hidden=!s.running;$('cancel').disabled=phase==='cancelling';
  text('pause',s.automatic_sync?'Pause':'Resume');
  text('account-name',view.account?.username || (view.connected?'Checking account…':'Not connected'));
  text('market-name',marketName(view.settings.selected_market || s.selected_market || view.offline_market?.id));
  text('preference-note',view.settings.selected_market ? 'Local choice · applies only to this PC' : view.bootstrap?.preference_fallback ? 'Your saved website market is unavailable. Using an available market.' : 'Following your website market preference');
  text('last-sync',s.last_sync_ms==null?'Not yet':datetime(at(s.last_sync_ms)));
  text('last-check',datetime(at(s.last_server_check_ms)));text('upstream-update',datetime(at(s.upstream_update_ms)));
  text('next-sync',s.next_sync_ms==null ? (s.running?'After this sync':s.automatic_sync?'Waiting for connection':'Paused') : datetime(at(s.next_sync_ms)));
  text('cache-count',view.cache?.has_completed_cache ? `${view.cache.item_count.toLocaleString()} item variants${view.cache.downloading?' · download pending':''}`:'No completed download');
  text('source-note',s.last_sync_ms ? (s.received_new_generation?'New upstream market data received.':'Desktop check complete. Upstream data may update less often.') : 'Collection checks and new upstream data are separate events.');
  $('synthetic-warning').hidden=!view.cache?.synthetic;$('legacy-warning').hidden=view.mode!=='legacy';
  $('export').disabled=!view.cache?.has_completed_cache;
  $('workshop-export').disabled=workshopExporting||!view.connected||view.refreshing||s.running;
  $('workshop-pricing').disabled=workshopExporting||archiveBusy;
  const historyContext=`${view.settings.server}|${view.bootstrap?.account?.id}|${view.settings.selected_market||s.selected_market}`;
  if(archiveContext!==historyContext){archiveContext=historyContext;reviewedDelivery=null;workshopReview=null;workshopIssue=null;delete $('delivery-installation').dataset.initialized;$('delivery-installation').value='';$('delivery-confirm').checked=false;text('archive-status','No completed archive selected.');text('scope-status','Choose exact variants after downloading retained history.');$('scope-variants').value='';$('scope-compatible').checked=false;}
  for(const id of ['archive-sync','scope-preview','scope-export'])$(id).disabled=archiveBusy||workshopExporting;
  const dc=view.delivery?.configuration,ds=view.delivery?.status;
  if(dc&&!$('delivery-installation').dataset.initialized){$('delivery-installation').value=dc.installation;$('workshop-pricing').value=dc.scope.algorithm;if(dc.version===1){$('delivery-days').value=String(dc.history_days);$('scope-variants').value=dc.selection.variants.map(v=>`${v.item_id} ${v.variant_key}`).join('\n');}$('delivery-installation').dataset.initialized='true';}
  for(const id of ['delivery-review','delivery-enable','delivery-disable','delivery-rollback'])$(id).disabled=deliveryBusy||archiveBusy||s.running;
  text('delivery-status',(dc?`${dc.enabled?'Automatic delivery enabled':'Delivery disabled'} · ${dc.version===2?`Broad summaries · ${ds?.summary_records??'unknown'} records · ${ds?.download_requests??'unknown'} requests · ${ds?.download_bytes??'unknown'} transferred bytes`:`${dc.selection.variants.length} selected · ${dc.history_days} UTC days`} · ${ds?.result||'Waiting for next sync'}. Validated: ${ds?.validated_generation||'none'}. Published: ${ds?.published_generation||'none'}. Last file write: ${datetime(ds?.last_successful_write)}. ${ds?.error||''} Loaded game generation: unknown; inspect Workshop in WoW.`:view.delivery?.notice||'Automatic delivery is off.')+(workshopIssue?` Setup detail: ${workshopIssue.code} · ${workshopIssue.stage} · ${workshopIssue.details}`:''));
  const automatic=dc?.version===2&&dc.enabled;
  const waiting=automatic&&ds?.result==='Waiting for World of Warcraft to close.';
  const preparationMessage='Market summaries are being prepared; synchronization will retry';
  const preparing=automatic&&ds?.result==='Preparing market data.'&&!view.error&&(!view.sync.error||view.sync.error===preparationMessage);
  const issue=Boolean(workshopIssue&&workshopIssue.code!=='cancelled')||automatic&&Boolean(ds?.error)&&!waiting&&!preparing;
  text('workshop-installation',dc?.version===2?'World of Warcraft Forever — Found':'Not connected');
  text('workshop-market',marketName(view.settings.selected_market||s.selected_market));
  text('workshop-state',workshopBusy?'Connecting Workshop':automatic&&s.running||preparing&&s.automatic_sync?'Updating':waiting?'Waiting for WoW to close':issue?'Needs attention':automatic&&!s.automatic_sync?'Synchronization paused':automatic&&ds?.published_generation?'Up to date':automatic?'Waiting for next sync':'Not connected');
  text('workshop-updated',datetime(ds?.last_successful_write));
  text('workshop-note',workshopIssue?workshopMessage(workshopIssue):waiting?'Updates will be installed safely after World of Warcraft closes.':automatic&&!s.automatic_sync?'Resume synchronization to keep Workshop updated automatically.':preparing?'The server is preparing market data. The companion will retry automatically.':automatic?'Uses your existing sync schedule. Updated files become available on your next game login or reload.':'Connect once. The companion finds your Forever installation and uses your existing sync schedule.');
  $('workshop-confirmation').hidden=!workshopReview;
  $('workshop-connect').hidden=Boolean(workshopReview)||automatic&&!issue;
  $('workshop-connect').disabled=workshopBusy||s.running||!view.connected||view.refreshing;
  text('workshop-connect',automatic?'Retry':'Connect Workshop');
  $('workshop-authorize').disabled=workshopBusy||!workshopReview;

  $('disconnect').disabled=view.approving||view.refreshing;
  if(view.error||view.sync.error&&!(preparing&&view.sync.error===preparationMessage)) {const error=view.error||view.sync.error;message(error.startsWith('Workshop delivery:')?'Workshop needs attention. Your previous market data is safe. See developer diagnostics for details.':error,true);nativeErrorShown=true;}
  else if(nativeErrorShown) {message('');nativeErrorShown=false;}
  else if(view.quitting) message('Closing safely…');
}
function workshopFailure(error){
  try{const value=JSON.parse(String(error?.message||error));if(value&&typeof value.message==='string'&&typeof value.code==='string'&&typeof value.stage==='string')return value;}catch{}
  // Compatibility with older native errors; never render arbitrary native text.
  const reason=String(error?.message||error);
  if(reason.includes('cancelled'))return {code:'cancelled',stage:'folder_picker',message:'Folder selection cancelled.',details:'native dialog cancelled'};
  if(reason.includes('Workshop needs an update'))return {code:'workshop_addon',stage:'workshop_addon',message:'Workshop needs an update. Install the compatible TwichUI addon, then retry.',details:'incompatible addon'};
  return {code:'internal',stage:'setup',message:'Workshop setup could not finish because of an unexpected error. Retry or save developer diagnostics. Your files were preserved.',details:'unexpected native setup failure'};
}
function workshopMessage(error){return error.message;}
async function connectWorkshop(confirm=false){
  if(workshopBusy)return;const context=archiveContext;let focusTarget=null;workshopBusy=true;workshopIssue=null;render(view);
  try{
    if(!invoke)throw new Error('Use the installed Windows companion.');
    const result=await invoke(confirm?'confirm_workshop':'prepare_workshop',confirm?{reviewId:workshopReview?.review_id}:{});
    if(context!==archiveContext)return;
    if(confirm||result?.connected){workshopReview=null;}
    else{workshopReview=result;text('workshop-confirmed-folder',`${result.installation} · ${result.market}`);}
    render(await invoke('app_state'));
    focusTarget=workshopReview?'workshop-authorize':'workshop-state';
  }catch(error){if(context===archiveContext){workshopIssue=workshopFailure(error);workshopReview=null;}}
  finally{
    workshopBusy=false;
    if(context!==archiveContext&&view?.connected){workshopReview=null;workshopIssue={code:'context_changed',stage:'setup_context',message:'Your account or market changed during setup. Connect Workshop again.',details:'setup context changed'};}
    render(view);if(context===archiveContext&&focusTarget)$(focusTarget).focus();
  }
}
$('workshop-connect').onclick=()=>connectWorkshop(false);
$('workshop-authorize').onclick=()=>connectWorkshop(true);
$('workshop-cancel').onclick=async()=>{workshopReview=null;render(view);if(invoke)await invoke('cancel_workshop').catch(()=>{});$('workshop-connect').focus();};
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&workshopReview&&!editing){event.preventDefault();$('workshop-cancel').click();}});
async function action(command, args={}, success) {
  try {
    if(!invoke)throw new Error('Use the installed Windows companion for this action.');
    const result=await invoke(command,args);
    render(await invoke('app_state'));
    if(success)message(typeof success==='function'?success(result):success);
    return {ok:true,value:result};
  } catch(error) {message(String(error?.message||error),true);return null;}
}
function openSettings() {
  if(!view)return;
  editing=true;$('dashboard').hidden=true;$('settings-panel').hidden=false;
  const s=view.settings;
  const mapping={'automatic-sync':s.automatic_sync,'sync-startup':s.sync_on_startup,'launch-login':view.autostart_enabled,'start-tray':s.start_in_tray,'minimize-tray':s.minimize_to_tray,'close-tray':s.close_to_tray,'error-notifications':s.error_notifications};
  for(const [id,value] of Object.entries(mapping))$(id).checked=value;
  $('server').value=s.server;$('sync-interval').value=String(s.interval_minutes);
  const choice=$('market-choice');choice.replaceChildren(new Option('Use my website choice',''));
  for(const market of view.bootstrap?.markets||[]) {
    if(!market.available_for_sync && market.id!==s.selected_market)continue;
    const option=new Option(market.label+(market.available_for_sync?'':' · unavailable'),String(market.id));option.disabled=!market.available_for_sync;choice.append(option);
  }
  choice.value=s.selected_market==null?'':String(s.selected_market);
  text('market-choice-note',view.bootstrap?.suggested_market_id ? `Website choice: ${marketName(view.bootstrap.suggested_market_id)}. Collection settings are unchanged.` : 'This applies only to this companion. Connect to see available markets.');
  $('reset-settings').hidden=view.settings_valid;
  $('settings-back').focus();
}
function closeSettings() {editing=false;$('settings-panel').hidden=true;$('dashboard').hidden=false;$('settings-open').focus();}
$('settings-open').onclick=openSettings;$('market-change').onclick=openSettings;
$('settings-back').onclick=closeSettings;$('settings-cancel').onclick=closeSettings;
$('sign-in').onclick=()=>action('sign_in',{deviceName:$('device-name').value.trim()||'Windows PC'});
$('reconnect').onclick=()=>action('sign_in',{deviceName:view.bootstrap?.device?.name||'Windows PC'});
$('sign-in-again').onclick=$('reconnect').onclick;
$('approval-open').onclick=()=>action('open_approval');$('approval-cancel').onclick=()=>action('cancel_approval');
$('sync').onclick=()=>action('sync_now');$('cancel').onclick=()=>action('cancel_sync');
$('pause').onclick=()=>action(view.sync.sync.automatic_sync?'pause_sync':'resume_sync');
$('refresh').onclick=()=>action('refresh_connection');$('disconnect').onclick=()=>action('disconnect');
$('export').onclick=()=>action('export_market',{},'Export saved to your companion folder.');$('exports-open').onclick=()=>action('open_exports');
$('website').onclick=()=>action('open_website',{page:'account'});
$('diagnostics').onclick=()=>action('save_diagnostics',{},'Redacted diagnostics saved to your companion folder.');
$('settings-form').onsubmit=async event=>{
  event.preventDefault();
  const selected=$('market-choice').value;
  const settings={...view.settings,server:$('server').value.trim(),automatic_sync:$('automatic-sync').checked,interval_minutes:Number($('sync-interval').value),
    sync_on_startup:$('sync-startup').checked,launch_at_login:$('launch-login').checked,start_in_tray:$('start-tray').checked,minimize_to_tray:$('minimize-tray').checked,
    close_to_tray:$('close-tray').checked,error_notifications:$('error-notifications').checked,selected_market:selected?Number(selected):null};
  const result=await action('save_settings',{settings,resetInvalid:false},'Settings saved.');
  if(result!==null)closeSettings();
};
$('reset-settings').onclick=async()=>{const settings={schema_version:1,server:'https://market.twich.gg/',launch_at_login:false,start_in_tray:false,minimize_to_tray:false,close_to_tray:true,
  automatic_sync:true,interval_minutes:30,sync_on_startup:true,error_notifications:true,selected_market:null,onboarding_completed:false};
  await action('save_settings',{settings,resetInvalid:true},'Defaults restored. Your previous settings file was kept.');openSettings();};
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&editing)closeSettings();});
(async()=>{
  if(!invoke){$('preview-notice').hidden=false;$('welcome').hidden=false;return;}
  if(listen){await listen('companion-state',event=>render(event.payload));await listen('open-settings',openSettings);await listen('companion-error',event=>message(event.payload,true));}
  render(await invoke('app_state'));
})().catch(error=>message(String(error),true));

let updateView=null;
function renderUpdate(value){
  if(!value)return;updateView=value;
  const available=value.available_version||(value.status==='available'?value.version:null);
  $('update-available-notice').hidden=!available;
  text('update-available-title',available?`Companion ${available} is available`:'');
  text('update-message',value.message);text('update-notes',value.notes||'');$('update-notes').hidden=!value.notes;
  const busy=['checking','installing'].includes(value.status);
  $('update-check').disabled=busy||value.restart_required;
  $('update-install').hidden=value.status!=='available';$('update-install').disabled=busy;
  $('update-restart').hidden=!value.restart_required;
  if(value.status!=='available')$('update-confirm').hidden=true;
}
async function updateAction(command,args={}){
  try{if(!invoke)throw new Error('Use the installed companion to check for updates.');renderUpdate(await invoke(command,args));}
  catch(error){text('update-message',String(error?.message||error));}
}
function openUpdates(){openSettings();$('update-message').scrollIntoView({block:'center'});$('update-check').focus();}
$('update-available-review').onclick=openUpdates;
if(listen)listen('open-updates',openUpdates);
$('update-check').onclick=()=>updateAction('check_update');
$('update-install').onclick=()=>{$('update-confirm').hidden=false;$('update-confirm-install').focus();};
$('update-confirm-cancel').onclick=()=>{$('update-confirm').hidden=true;$('update-install').focus();};
$('update-confirm-install').onclick=()=>{if(updateView?.status==='available')updateAction('install_update',{version:updateView.version});};
$('update-restart').onclick=()=>updateAction('restart_companion');
if(listen)listen('companion-update',event=>renderUpdate(event.payload));
if(invoke)invoke('update_state').then(renderUpdate).catch(()=>{});

$('workshop-export').onclick=async()=>{
  if(workshopExporting)return;
  const algorithm=$('workshop-pricing').value;workshopExporting=true;render(view);
  message('Downloading and validating Workshop test data…');
  try{await action('export_workshop',{algorithm},path=>`Workshop test addon saved outside the game installation: ${path}`);}
  finally{workshopExporting=false;render(view);}
};

function scopeInput(){
  const rows=$('scope-variants').value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  const variants=rows.map(line=>{const m=line.match(/^(\d{1,10})[\s,:]+([0-9a-fA-F]{64})$/);if(!m)throw new Error('Each line needs an item ID and its full exact variant key.');return {item_id:Number(m[1]),variant_key:m[2].toLowerCase()};});
  return {variants,history_from_day:$('scope-from').value,history_through_day:$('scope-through').value};
}
$('scope-variants').oninput=()=>{reviewedDelivery=null;$('delivery-confirm').checked=false;text('scope-count',`${$('scope-variants').value.split(/\r?\n/).filter(s=>s.trim()).length} selected · automatic pilot: up to 10 variants, 2 MiB data, 3 MiB Lua.`);};
async function historyAction(sync,publish){
  if(archiveBusy)return;
  const requestedContext=archiveContext;
  archiveBusy=true;render(view);text('scope-status',sync?'Downloading/resuming retained history. Completed data stays available during errors…':'Checking the complete requested scope…');
  try{
    const selected=sync?null:scopeInput();
    const result=await action('archive_workshop',{algorithm:$('workshop-pricing').value,diskBudgetMib:Number($('archive-budget').value),selected,publish,compatible:$('scope-compatible').checked});
    if(archiveContext!==requestedContext)return;
    if(!result?.ok){text('scope-status',sync?'Download incomplete. Committed progress and the previous completed archive are preserved.':'Request refused. The previous completed archive and export are preserved.');return;}
    if(!view?.error&&!view?.sync?.error)message('');
    const r=result.value,h=r.header;
    text('archive-status',`${h.market.region.toUpperCase()} · house ${h.market.house_id} · ${h.pricing_algorithm} · ${h.total_observations.toLocaleString()} retained observations · ${(r.archive_bytes/1048576).toFixed(2)} MiB SQLite. Checkpoint ${h.checkpoint_id}`);
    if(sync){
      const saved=r.selection;
      const through=h.generated_at.slice(0,10),from=new Date(through+'T00:00:00Z');from.setUTCDate(from.getUTCDate()-59);
      $('scope-through').value=saved?.history_through_day||through;$('scope-from').value=saved?.history_from_day||from.toISOString().slice(0,10);
      if(saved)$('scope-variants').value=saved.variants.map(v=>`${v.item_id} ${v.variant_key}`).join('\n');
      $('scope-variants').oninput();text('scope-status','Archive complete. Choose up to ten exact variants, check sizes, then review automatic delivery below.');
    }else{
      const s=r.sizes;
      text('scope-status',`${s.records} exact variants · ${selected.history_from_day} through ${selected.history_through_day} · exact data ${s.canonical_bytes.toLocaleString()} bytes · Lua ${s.lua_bytes.toLocaleString()} bytes · manifest ${s.manifest_bytes.toLocaleString()} bytes. Generation ${r.generation_id}.${r.path?' Exported to '+r.path+'.':''} Manual exports remain in companion staging. Automatic delivery requires a compatible installed Workshop and confirmed destination.`);
    }
  }catch(e){if(archiveContext===requestedContext){text('scope-status','Selection not exported. Previous completed data is preserved.');message(String(e?.message||e),true);}}
  finally{archiveBusy=false;render(view);}
}
$('archive-sync').onclick=()=>historyAction(true,false);
$('scope-preview').onclick=()=>historyAction(false,false);
$('scope-export').onclick=()=>historyAction(false,true);

function deliveryKey(){return JSON.stringify([archiveContext,$('delivery-installation').value,$('delivery-days').value,$('workshop-pricing').value,$('scope-variants').value]);}
for(const id of ['delivery-installation','delivery-days','workshop-pricing'])$(id).addEventListener('change',()=>{reviewedDelivery=null;$('delivery-confirm').checked=false;});
async function deliveryAction(operation){
  if(deliveryBusy)return;
  if(operation==='enable'&&(reviewedDelivery!==deliveryKey()||!$('delivery-confirm').checked)){message('Review this exact installation and market, then confirm the destination.',true);return;}
  if(operation==='rollback'&&!$('delivery-confirm').checked){message('Confirm restoring the previous generation with WoW closed. Delivery will be disabled.',true);return;}
  const context=archiveContext;
  let variants=null;try{if(operation==='inspect'||operation==='enable')variants=scopeInput().variants;}catch(e){message(String(e?.message||e),true);return;}
  deliveryBusy=true;render(view);
  try{
    const result=await action('configure_delivery',{installation:$('delivery-installation').value,algorithm:$('workshop-pricing').value,historyDays:Number($('delivery-days').value),operation,confirmed:$('delivery-confirm').checked,variants});
    if(!result?.ok||context!==archiveContext)return;
    const r=result.value;
    if(operation==='inspect'){
      reviewedDelivery=deliveryKey();$('delivery-confirm').checked=false;
      text('delivery-destination',`Destination: ${r.destination}. Market: ${r.market.region.toUpperCase()} · ${r.market.player_ruleset||'unknown ruleset'} · house ${r.market.house_id} · transport ruleset ${r.market.transport_ruleset_id}. Existing generation: ${r.existing_generation||'none'}. Schema ${r.schema}. ${r.sizes?`${r.sizes.records} selected · ${r.history_days} UTC days · ${r.sizes.canonical_bytes.toLocaleString()} data bytes · ${r.sizes.lua_bytes.toLocaleString()} Lua bytes.`:''} ${r.requires_adoption?'This compatible manual export has no account or installation receipt. Confirm explicitly adopting it for this account and installation; previous data will be preserved.':'Confirm below to enable.'}`);
    }else{message(operation==='enable'?'Delivery enabled for this installation. Close WoW, then use Sync now or wait for the next scheduled sync.':operation==='rollback'?'Delivery disabled and previous files restored. Log in to use them.':'Automatic delivery disabled. Existing game files are kept.');}
  }finally{deliveryBusy=false;render(view);}
}
for(const [id,op] of [['delivery-review','inspect'],['delivery-enable','enable'],['delivery-disable','disable'],['delivery-rollback','rollback']])$(id).onclick=()=>deliveryAction(op);
