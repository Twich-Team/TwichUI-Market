// Real installed Windows WebView2 + Rust IPC + disposable API. No IPC is mocked.
const {chromium,request,expect}=require('@playwright/test');
const {createHash}=require('node:crypto');const fs=require('node:fs');const path=require('node:path');const {execFile,spawn}=require('node:child_process');const {promisify}=require('node:util');
(async()=>{
  if(process.env.GITHUB_ACTIONS!=='true'||process.platform!=='win32')throw new Error('Installed acceptance requires the disposable Windows runner');
  const endpoint=`http://127.0.0.1:${process.env.MARKET_TEST_CDP_PORT}`;
  await expect.poll(async()=>{try{return(await fetch(`${endpoint}/json/version`)).ok}catch{return false}},{timeout:30000}).toBe(true);
  let browser=await chromium.connectOverCDP(endpoint);
  const api=await request.newContext({baseURL:process.env.MARKET_TEST_SERVER,extraHTTPHeaders:{Origin:process.env.MARKET_TEST_SERVER}});
  const shots=path.resolve('artifacts/companion-v2');fs.mkdirSync(shots,{recursive:true});
  const sourceCommit=(await promisify(execFile)('git',['rev-parse','HEAD'])).stdout.trim();
  const installedExecutableHash=createHash('sha256').update(fs.readFileSync(process.env.MARKET_TEST_INSTALLED_EXE)).digest('hex');
  let websiteBrowser;
  try{
    let page=browser.contexts()[0].pages()[0];
    const powershell=async script=>JSON.parse((await promisify(execFile)('powershell.exe',['-NoProfile','-NonInteractive','-Command',script],{timeout:20000})).stdout.trim());
    const startup=()=>powershell('@{user=[Microsoft.Win32.Registry]::GetValue("HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run","TwichUI Market Companion",$null);machine=[Microsoft.Win32.Registry]::GetValue("HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows\\CurrentVersion\\Run","TwichUI Market Companion",$null)} | ConvertTo-Json -Compress');
    const nativeControl=async action=>JSON.parse((await promisify(execFile)('powershell.exe',['-NoProfile','-NonInteractive','-File',path.resolve('scripts/windows/native-controls.ps1'),'-Action',action],{timeout:45000})).stdout.trim());
    const invoke=(command,args={})=>page.evaluate(({command,args})=>window.__TAURI__.core.invoke(command,args),{command,args});
    await expect(page.locator('#welcome')).toBeVisible();
    await expect(page.locator('#sign-in')).toBeVisible();await expect(page.locator('#token')).toHaveCount(0);
    await page.screenshot({path:path.join(shots,'native-welcome.png')});
    await page.locator('#settings-open').click();await page.locator('.advanced summary').click();await page.locator('#server').fill(process.env.MARKET_TEST_SERVER);
    await page.locator('#close-tray').uncheck();await page.locator('#settings-save').click();await expect(page.locator('#settings-panel')).toBeHidden();
    await page.locator('#device-name').fill('Installed Windows fixture');await page.locator('#sign-in').click();
    await expect(page.locator('#approval-panel')).toBeVisible();
    await expect.poll(async()=>(await invoke('app_state')).approval?.request_id,{timeout:15000}).toBeTruthy();
    const approval=(await invoke('app_state')).approval;const url=new URL(approval.authorization_url);
    expect(url.origin).toBe(process.env.MARKET_TEST_SERVER);expect(url.pathname).toBe('/companion/authorize');
    const login=await api.post('/api/v1/auth/login',{data:{username:'native_fixture',password:'synthetic browser fixture password'}});expect(login.ok()).toBe(true);
    const csrf=(await login.json()).csrf_token;const headers={'x-csrf-token':csrf};
    // Run the production website bundle in actual Edge, following the same
    // approval URL opened by the native default-browser action. No consent API shortcut.
    websiteBrowser=await chromium.launch({channel:'msedge',headless:false});
    const website=await websiteBrowser.newPage({viewport:{width:1240,height:900}});
    await website.goto(approval.authorization_url);
    await website.getByLabel('Username').fill('native_fixture');
    await website.getByLabel('Password',{exact:true}).fill('synthetic browser fixture password');
    expect(await website.locator('form').evaluate(form=>form.checkValidity())).toBe(true);
    const websiteLogin=website.waitForResponse(response=>response.url().endsWith('/api/v1/auth/login')&&response.request().method()==='POST');
    await website.getByRole('button',{name:'Sign in',exact:true}).click();expect((await websiteLogin).ok()).toBe(true);
    await expect(website.getByRole('heading',{name:'Installed Windows fixture',exact:true})).toBeVisible();
    await expect(website.getByRole('button',{name:'Approve this device',exact:true})).toBeVisible();
    await website.screenshot({path:path.join(shots,'website-approval.png'),fullPage:true});
    const firstSyncStart=performance.now();
    await website.getByRole('button',{name:'Approve this device',exact:true}).click();
    await expect.poll(()=>new URL(website.url()).pathname).toBe('/companion/callback');
    expect(new URL(website.url()).hostname).toBe('127.0.0.1');
    await expect(page.locator('#connected-panel')).toBeVisible({timeout:20000});
    await expect(page.locator('#sync-progress')).toBeVisible({timeout:15000});await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(shots,'native-sync-progress.png'),fullPage:true});
    await expect(page.locator('#cache-count')).toContainText('2 item variants',{timeout:30000});
    await expect.poll(async()=>(await invoke('app_state')).sync.sync.last_sync_ms,{timeout:15000}).toBeTruthy();
    await expect(page.locator('#market-name')).toHaveText('US — Normal — Horde');await expect(page.locator('#synthetic-warning')).toBeVisible();
    const initialSyncMs=performance.now()-firstSyncStart;
    await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(shots,'native-dashboard.png'),fullPage:true});
    await website.goto(process.env.MARKET_TEST_SERVER+'/companion');
    await expect(website.locator('.companion-recent').getByRole('heading',{name:'Installed Windows fixture',exact:true})).toBeVisible();
    await website.screenshot({path:path.join(shots,'website-wizard.png'),fullPage:true});
    await website.goto(process.env.MARKET_TEST_SERVER+'/account');
    await expect(website.getByRole('heading',{name:'Installed Windows fixture',exact:true})).toBeVisible();
    await website.screenshot({path:path.join(shots,'website-devices.png'),fullPage:true});
    const profile=(await api.get('/api/v1/companion/devices')).json();const device=(await profile).devices[0];expect(device.last_sync_at).toBeTruthy();expect(device.selected_market_id).toBe(1);
    await page.locator('#settings-open').click();await page.screenshot({path:path.join(shots,'native-settings.png'),fullPage:true});
    const updaterKeyHash=createHash('sha256').update(fs.readFileSync('desktop/src-tauri/updater-public-key.txt','utf8').trim()).digest('hex');
    await page.locator('#update-check').click();await expect(page.locator('#update-message')).toContainText('Connect to TwichUI Market');
    const updateState=await invoke('update_state');expect(updateState.status).toBe('unavailable');expect(updateState.verification_key_sha256).toBe(updaterKeyHash);
    const startupBefore=await startup();expect(startupBefore.user??null).toBe(null);
    await page.locator('#launch-login').check();await page.locator('#settings-save').click();
    expect((await startup()).user).toBe(`"${process.env.MARKET_TEST_INSTALLED_EXE}" --background`);
    expect((await startup()).machine).toBe(startupBefore.machine);
    await page.locator('#settings-open').click();await page.locator('#launch-login').uncheck();await page.locator('#settings-save').click();
    expect((await startup()).user??null).toBe(null);
    await page.locator('#settings-open').click();await page.locator('#launch-login').check();
    await page.locator('#start-tray').check();await page.locator('#minimize-tray').check();await page.locator('#close-tray').check();
    await page.locator('#sync-startup').uncheck();
    await page.locator('#sync-interval').selectOption('60');await page.locator('#automatic-sync').uncheck();await page.locator('#settings-save').click();
    expect((await invoke('app_state')).settings.interval_minutes).toBe(60);expect((await invoke('app_state')).sync.sync.automatic_sync).toBe(false);
    // The WebView remains hidden for this entire actual Rust-owned network/cache operation.
    await invoke('hide_to_tray');expect((await invoke('app_state')).window_visible).toBe(false);
    const before=(await invoke('app_state')).sync.sync.last_sync_ms;const incrementalStart=performance.now();expect(await invoke('sync_now')).toBe(true);
    await expect.poll(async()=>(await invoke('app_state')).sync.sync.last_sync_ms,{timeout:20000}).toBeGreaterThan(before);
    const incrementalSyncMs=performance.now()-incrementalStart;
    expect((await invoke('app_state')).window_visible).toBe(false);
    const networkBefore=await(await api.get('/__fixture__/native-network')).json();
    const resources=await nativeControl('Metrics');
    const networkAfter=await(await api.get('/__fixture__/native-network')).json();
    expect(networkAfter).toEqual(networkBefore);
    const restoreStart=performance.now();
    await promisify(execFile)(process.env.MARKET_TEST_INSTALLED_EXE,[],{timeout:15000});
    await expect.poll(async()=>(await invoke('app_state')).window_visible).toBe(true);
    const restoreMs=performance.now()-restoreStart;
    fs.writeFileSync(path.join(shots,'performance.json'),JSON.stringify({fixture:true,source_commit:sourceCommit,initial_sync_ms:initialSyncMs,incremental_noop_sync_ms:incrementalSyncMs,sync_fixture:{variants:2,page_limit:1,injected_delay_ms_per_page:500},second_launch_restore_ms:restoreMs,idle_market_api_requests:{before:networkBefore,after:networkAfter},resources,desktop_frontend_bytes:fs.readdirSync('desktop/ui').reduce((total,file)=>total+fs.statSync(path.join('desktop/ui',file)).size,0)},null,2));
    // A normal second launch restores the original process and retains its cache/settings.
    expect((await invoke('app_state')).cache.item_count).toBe(2);expect((await invoke('app_state')).settings.interval_minutes).toBe(60);
    // Tray assertions remain strict when explicitly invoked. The owner's focused
    // runner attempt established menu rendering but no usable UIA menu children.
    // Default CI proves the independent workflows and records tray as unverified.
    let trayVerified=false;
    if(process.env.MARKET_TEST_TRAY_ACCEPTANCE==='true'){
      const tray=await nativeControl('Capture');expect(tray.actual_tray).toBe(true);
      await nativeControl('Settings');await expect(page.locator('#settings-panel')).toBeVisible();
      await page.locator('#settings-cancel').click();
      await nativeControl('Minimize');await expect.poll(async()=>(await invoke('app_state')).window_visible).toBe(false);
      await nativeControl('Open');await expect.poll(async()=>(await invoke('app_state')).window_visible).toBe(true);
      await nativeControl('Close');await expect.poll(async()=>(await invoke('app_state')).window_visible).toBe(false);
      await nativeControl('Open');await expect.poll(async()=>(await invoke('app_state')).window_visible).toBe(true);
      const traySyncBefore=(await invoke('app_state')).sync.sync.last_sync_ms;
      await nativeControl('Sync');await expect.poll(async()=>(await invoke('app_state')).sync.sync.last_sync_ms,{timeout:20000}).toBeGreaterThan(traySyncBefore);
      await nativeControl('Pause');await expect.poll(async()=>(await invoke('app_state')).sync.sync.automatic_sync).toBe(true);
      await nativeControl('Pause');await expect.poll(async()=>(await invoke('app_state')).sync.sync.automatic_sync).toBe(false);
      await expect.poll(async()=>(await invoke('app_state')).sync.sync.running,{timeout:60000}).toBe(false);
      await nativeControl('Quit');trayVerified=true;
    }else{
      // Actual OS minimize/close events, restored through the normal second launch.
      // This is not evidence of tray restoration or tray-menu action execution.
      for(const action of ['Minimize','Close']){
        await nativeControl(action);await expect.poll(async()=>(await invoke('app_state')).window_visible).toBe(false);
        await promisify(execFile)(process.env.MARKET_TEST_INSTALLED_EXE,[],{timeout:15000});
        await expect.poll(async()=>(await invoke('app_state')).window_visible).toBe(true);
      }
      await invoke('quit').catch(()=>{});
    }
    // Real process restart independently checks vault, settings, cache and hidden startup.
    await expect.poll(async()=>{try{return(await fetch(`${endpoint}/json/version`)).ok}catch{return false}}).toBe(false);
    await browser.close().catch(()=>{});
    const restarted=spawn(process.env.MARKET_TEST_INSTALLED_EXE,[],{detached:true,stdio:'ignore'});restarted.unref();process.env.MARKET_TEST_PRIMARY_PID=String(restarted.pid);
    await expect.poll(async()=>{try{return(await fetch(`${endpoint}/json/version`)).ok}catch{return false}},{timeout:30000}).toBe(true);
    browser=await chromium.connectOverCDP(endpoint);page=browser.contexts()[0].pages()[0];
    await expect(page.locator('#version')).toHaveText(/^v2\./,{timeout:20000}); // Wait for the restarted WebView's real document and native state.
    await expect.poll(async()=>(await invoke('app_state')).connected,{timeout:20000}).toBe(true);
    expect((await invoke('app_state')).window_visible).toBe(false);
    expect((await invoke('app_state')).cache.item_count).toBe(2);
    expect((await invoke('app_state')).settings.interval_minutes).toBe(60);
    expect((await invoke('app_state')).autostart_enabled).toBe(true);
    await promisify(execFile)(process.env.MARKET_TEST_INSTALLED_EXE,[],{timeout:15000});
    await expect.poll(async()=>(await invoke('app_state')).window_visible).toBe(true);
    await page.locator('.more > summary').click();await page.locator('#export').click();await expect(page.locator('#message')).toContainText('Export saved');
    const folder=path.join(process.env.MARKET_TEST_APP_DATA,'exports');const exports=fs.readdirSync(folder).filter(file=>file.endsWith('.json')&&!file.startsWith('diagnostics'));
    expect(exports.length).toBeGreaterThan(0);const data=JSON.parse(fs.readFileSync(path.join(folder,exports[exports.length-1]),'utf8'));
    expect(data.format).toBe('twichui-market-addon-data');expect(data.synthetic).toBe(true);expect(data.items).toHaveLength(2);expect(data.items[0].value.recent_price).toBe('100');
    // The retained signed beta.5/beta.6 SDK is independently tested with its original
    // feature set; the new source candidate must pass automatic-summary coverage.
    if(/^2\.0\.0-beta\.(?:[7-9]|[1-9][0-9]+)$/.test((await invoke('app_state')).version))await require('./companion-workshop-native.cjs')({page,invoke,api,shots,sourceCommit});
    // Actual installed WebView -> Rust command -> authenticated archive server ->
    // transactional SQLite -> schema-3 publisher, confined to test AppData.
    if(!await page.locator('.more').evaluate(el=>el.open))await page.locator('.more > summary').click();await page.locator('#history-panel summary').click();await page.locator('#archive-sync').click();
    await expect(page.locator('#scope-status')).toContainText('Archive complete',{timeout:30000});
    const variant=createHash('sha256').update(JSON.stringify({id:12363})).digest('hex');
    await page.locator('#scope-variants').fill('12363 '+variant);await page.locator('#scope-preview').click();
    await expect(page.locator('#scope-status')).toContainText('1 exact variants',{timeout:30000});
    await page.locator('#scope-export').click();await expect(page.locator('#message')).toContainText('Confirm the installed');
    await page.locator('#scope-compatible').check();await page.locator('#scope-export').click();
    await expect(page.locator('#scope-status')).toContainText('Exported to',{timeout:30000});
    const selected={variants:[{item_id:12363,variant_key:variant}],history_from_day:await page.locator('#scope-from').inputValue(),history_through_day:await page.locator('#scope-through').inputValue()};
    const scoped=await invoke('archive_workshop',{algorithm:'twichui-pricing-v1',diskBudgetMib:4096,selected,publish:true,compatible:true});
    expect(scoped.schema3_workshop_runtime_available).toBe(true);expect(scoped.sizes.records).toBe(1);
    expect(path.relative(process.env.MARKET_TEST_APP_DATA,scoped.path).startsWith('workshop-testing'+path.sep)).toBe(true);
    const lua=fs.readFileSync(scoped.path);expect(lua.length).toBe(scoped.sizes.lua_bytes);expect(lua.toString().startsWith('TwichUIMarketData = { transport_version = 1')).toBe(true);
    expect(fs.readFileSync(path.join(path.dirname(scoped.path),'TwichUI_MarketData.toc'),'utf8')).not.toMatch(/^\s*##\s*SavedVariables(?:PerCharacter)?\s*:/mi);
    expect(fs.existsSync(path.join(process.env.MARKET_TEST_APP_DATA,'history-archive-v1.sqlite'))).toBe(true);
    fs.writeFileSync(path.join(shots,'installed-archive-smoke.json'),JSON.stringify({fixture:true,source_commit:sourceCommit,header:scoped.header,sizes:scoped.sizes,generation_id:scoped.generation_id,native_archive_command:true,manual_schema3_staging:true,no_game_installation:true},null,2));
    // Installed native worker delivers only to this disposable synthetic game tree.
    const game=path.join(process.env.MARKET_TEST_APP_DATA,'synthetic-Forever');
    const consumer=path.join(game,'Interface','AddOns','TwichUI_Workshop');fs.mkdirSync(consumer,{recursive:true});
    fs.writeFileSync(path.join(game,'Wow.exe'),'synthetic fixture, not a game');
    fs.writeFileSync(path.join(consumer,'MarketDelivery.json'),JSON.stringify({format:'twichui-market-consumer',capability_version:1,contract_version:1,transport_version:1,schema_versions:[3],canonical_bytes:2097152,lua_bytes:3145728}));
    await page.locator('#delivery-installation').fill(game);await page.locator('#delivery-review').click();
    await expect(page.locator('#delivery-destination')).toContainText('TwichUI_MarketData');
    await page.locator('#delivery-confirm').check();await page.locator('#delivery-enable').click();
    await expect(page.locator('#message')).toContainText('Delivery enabled');
    await invoke('sync_now');
    await expect.poll(async()=>(await invoke('app_state')).delivery.status?.published_generation,{timeout:60000}).toMatch(/^[a-f0-9]{64}$/);
    const delivered=path.join(game,'Interface','AddOns','TwichUI_MarketData','Data.lua');
    const automatic=(await invoke('app_state')).delivery;expect(automatic.status.loaded_game_generation).toBeNull();
    const deliveredHash=createHash('sha256').update(fs.readFileSync(delivered)).digest('hex');const mtime=fs.statSync(delivered).mtimeMs;
    await expect.poll(async()=>(await invoke('app_state')).sync.sync.running,{timeout:60000}).toBe(false);await invoke('sync_now');
    await expect.poll(async()=>(await invoke('app_state')).delivery.status?.result,{timeout:60000}).toContain('unchanged');
    expect(fs.statSync(delivered).mtimeMs).toBe(mtime);expect(createHash('sha256').update(fs.readFileSync(delivered)).digest('hex')).toBe(deliveredHash);
    await page.screenshot({path:path.join(shots,'installed-m2-delivery.png'),fullPage:true});
    await expect.poll(async()=>(await invoke('app_state')).sync.sync.running,{timeout:60000}).toBe(false);
    // Observe the genuine UI click and native result without changing either the
    // input path or the original assertion/deadline. Keep failed-run evidence.
    await page.evaluate(()=>{
      window.__disableDeliveryTrace=[];
      for(const type of ['pointerdown','pointerup','click'])document.addEventListener(type,event=>{
        if(event.target.closest?.('#delivery-disable'))window.__disableDeliveryTrace.push({type,trusted:event.isTrusted,
          disabled:document.getElementById('delivery-disable').disabled,deliveryBusy,archiveBusy,running:view?.sync?.sync?.running});
      },true);
    });
    let disableVerified=false;
    try{
      await page.locator('#delivery-disable').click();
      await expect.poll(async()=>(await invoke('app_state')).delivery.configuration.enabled).toBe(false);
      disableVerified=true;
    }finally{
      const ui=await page.evaluate(()=>({events:window.__disableDeliveryTrace,message:document.getElementById('message').textContent,
        error:document.getElementById('message').classList.contains('error'),deliveryBusy,archiveBusy,
        disabled:document.getElementById('delivery-disable').disabled,running:view?.sync?.sync?.running}));
      const native=await invoke('app_state');
      const receipt={fixture:true,source_commit:sourceCommit,verified:disableVerified,ui,
        native:{enabled:native.delivery?.configuration?.enabled,running:native.sync.sync.running,phase:native.sync.sync.phase}};
      fs.writeFileSync(path.join(shots,'installed-disable-delivery.json'),JSON.stringify(receipt,null,2));
      console.log('Disable delivery evidence: '+JSON.stringify(receipt));
      if(!disableVerified)await page.screenshot({path:path.join(shots,'installed-disable-delivery-failure.png'),fullPage:true});
    }
    fs.writeFileSync(path.join(shots,'installed-m2-delivery.json'),JSON.stringify({fixture:true,source_commit:sourceCommit,status:automatic.status,no_op_mtime_preserved:true,delivery_disabled:true,real_game:false},null,2));
    await page.locator('#disconnect').click();await expect.poll(async()=>(await invoke('app_state')).mode,{timeout:20000}).toBe('disconnected');
    expect((await invoke('app_state')).cache.item_count).toBe(2);
    const revoked=(await(await api.get('/api/v1/companion/devices')).json()).devices.find(row=>row.id===device.id);expect(revoked.revoked).toBe(true);
    fs.writeFileSync(path.join(shots,'installed-smoke.json'),JSON.stringify({fixture:true,source_commit:sourceCommit,installed_executable_sha256:installedExecutableHash,acceptance_scope:'Installed non-tray workflows; tray actions are a separate explicit gate',version:(await invoke('app_state')).version,native_browser_approval_api:true,native_browser_approval_ui:true,
      native_thread_hidden_sync:true,single_instance_restore:true,preferences_saved:true,credential_and_cache_restart:true,hidden_startup:true,current_user_autostart_enable_disable:true,actual_tray_menu:trayVerified,tray_settings_sync_pause_open_quit:trayVerified,native_minimize_close_to_tray:true,export_valid:true,history_archive_sync:true,scoped_manual_export:true,server_revocation:true,offline_cache_preserved:true,updater_disabled:false,updater_public_key_sha256:updaterKeyHash,update_checks_blocked_for_custom_server:true,
      website_approval_ui_verified:true,tray_rendering_evidence:{run_id:43647891422,real_menu_rendering_verified:true,actions_verified:false},tray_acceptance:trayVerified?'verified':'unverified',
      tray_limitation:trayVerified?null:'Focused runner attempt opened the real notification menu; UIA exposed no menu items. Owner manual acceptance required.',
      full_tray_autostart_upgrade_acceptance_complete:false},null,2));
    if(trayVerified)await nativeControl('Quit');else await invoke('quit').catch(()=>{});
    await expect.poll(async()=>{try{return(await fetch(`${endpoint}/json/version`)).ok}catch{return false}}).toBe(false);
    console.log(`Tray acceptance: ${trayVerified?'verified':'UNVERIFIED — owner manual checklist required'}`);
    console.log('Installed v2: actual Edge website approval, real Rust hidden-window sync, preference save, single-instance restore, export, revocation and offline cache passed.');
  }finally{await websiteBrowser?.close();await api.dispose();await browser.close().catch(()=>{});}
})().catch(error=>{console.error(error);process.exitCode=1});
