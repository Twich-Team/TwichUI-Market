// Real installed Windows WebView2 + Rust IPC + disposable API. No IPC is mocked.
const {chromium,request,expect}=require('@playwright/test');
const fs=require('node:fs');const path=require('node:path');const {execFile,spawn}=require('node:child_process');const {promisify}=require('node:util');
(async()=>{
  if(process.env.GITHUB_ACTIONS!=='true'||process.platform!=='win32')throw new Error('Installed acceptance requires the disposable Windows runner');
  const endpoint=`http://127.0.0.1:${process.env.MARKET_TEST_CDP_PORT}`;
  await expect.poll(async()=>{try{return(await fetch(`${endpoint}/json/version`)).ok}catch{return false}},{timeout:30000}).toBe(true);
  let browser=await chromium.connectOverCDP(endpoint);
  const api=await request.newContext({baseURL:process.env.MARKET_TEST_SERVER,extraHTTPHeaders:{Origin:process.env.MARKET_TEST_SERVER}});
  const shots=path.resolve('artifacts/companion-v2');fs.mkdirSync(shots,{recursive:true});
  let websiteBrowser;
  try{
    let page=browser.contexts()[0].pages()[0];
    const powershell=async script=>JSON.parse((await promisify(execFile)('powershell.exe',['-NoProfile','-NonInteractive','-Command',script],{timeout:20000})).stdout.trim());
    const startup=()=>powershell('@{user=(Get-ItemPropertyValue -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" -Name "TwichUI Market Companion" -ErrorAction SilentlyContinue);machine=(Get-ItemPropertyValue -Path "HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" -Name "TwichUI Market Companion" -ErrorAction SilentlyContinue)} | ConvertTo-Json -Compress');
    const nativeControl=async action=>JSON.parse((await promisify(execFile)('powershell.exe',['-NoProfile','-NonInteractive','-File',path.resolve('scripts/windows/native-controls.ps1'),'-Action',action],{timeout:20000})).stdout.trim());
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
    await website.getByRole('button',{name:'Approve this device',exact:true}).click();
    await expect.poll(()=>new URL(website.url()).pathname).toBe('/companion/callback');
    expect(new URL(website.url()).hostname).toBe('127.0.0.1');
    await expect(page.locator('#connected-panel')).toBeVisible({timeout:20000});
    await expect(page.locator('#sync-progress')).toBeVisible({timeout:15000});await page.screenshot({path:path.join(shots,'native-sync-progress.png')});
    await expect(page.locator('#cache-count')).toContainText('2 item variants',{timeout:30000});
    await expect.poll(async()=>(await invoke('app_state')).sync.sync.last_sync_ms,{timeout:15000}).toBeTruthy();
    await expect(page.locator('#market-name')).toHaveText('US — Normal — Horde');await expect(page.locator('#synthetic-warning')).toBeVisible();
    await page.screenshot({path:path.join(shots,'native-dashboard.png')});
    await website.goto(process.env.MARKET_TEST_SERVER+'/companion');
    await expect(website.getByText('Installed Windows fixture is connected.',{exact:true})).toBeVisible();
    await website.screenshot({path:path.join(shots,'website-wizard.png'),fullPage:true});
    await website.goto(process.env.MARKET_TEST_SERVER+'/account');
    await expect(website.getByRole('heading',{name:'Installed Windows fixture',exact:true})).toBeVisible();
    await website.screenshot({path:path.join(shots,'website-devices.png'),fullPage:true});
    const profile=(await api.get('/api/v1/companion/devices')).json();const device=(await profile).devices[0];expect(device.last_sync_at).toBeTruthy();expect(device.selected_market_id).toBe(1);
    await page.locator('#settings-open').click();await page.screenshot({path:path.join(shots,'native-settings.png'),fullPage:true});
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
    const before=(await invoke('app_state')).sync.sync.last_sync_ms;expect(await invoke('sync_now')).toBe(true);
    await expect.poll(async()=>(await invoke('app_state')).sync.sync.last_sync_ms,{timeout:20000}).toBeGreaterThan(before);
    expect((await invoke('app_state')).window_visible).toBe(false);
    await promisify(execFile)(process.env.MARKET_TEST_INSTALLED_EXE,[],{timeout:15000});
    await expect.poll(async()=>(await invoke('app_state')).window_visible).toBe(true);
    // A normal second launch restores the original process and retains its cache/settings.
    expect((await invoke('app_state')).cache.item_count).toBe(2);expect((await invoke('app_state')).settings.interval_minutes).toBe(60);
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
    await expect.poll(async()=>(await invoke('app_state')).sync.sync.running).toBe(false);
    // Restart the installed process normally. Credential Manager, settings and
    // completed SQLite cache must survive; opted-in tray startup stays hidden.
    await nativeControl('Quit');
    await expect.poll(async()=>{try{return(await fetch(`${endpoint}/json/version`)).ok}catch{return false}}).toBe(false);
    await browser.close().catch(()=>{});
    const restarted=spawn(process.env.MARKET_TEST_INSTALLED_EXE,[],{detached:true,stdio:'ignore'});restarted.unref();
    await expect.poll(async()=>{try{return(await fetch(`${endpoint}/json/version`)).ok}catch{return false}},{timeout:30000}).toBe(true);
    browser=await chromium.connectOverCDP(endpoint);page=browser.contexts()[0].pages()[0];
    await expect.poll(async()=>(await invoke('app_state')).connected,{timeout:20000}).toBe(true);
    expect((await invoke('app_state')).window_visible).toBe(false);
    expect((await invoke('app_state')).cache.item_count).toBe(2);
    expect((await invoke('app_state')).settings.interval_minutes).toBe(60);
    expect((await invoke('app_state')).autostart_enabled).toBe(true);
    await promisify(execFile)(process.env.MARKET_TEST_INSTALLED_EXE,[],{timeout:15000});
    await expect.poll(async()=>(await invoke('app_state')).window_visible).toBe(true);
    await page.locator('.more summary').click();await page.locator('#export').click();await expect(page.locator('#message')).toContainText('Export saved');
    const folder=path.join(process.env.MARKET_TEST_APP_DATA,'exports');const exports=fs.readdirSync(folder).filter(file=>file.endsWith('.json')&&!file.startsWith('diagnostics'));
    expect(exports.length).toBeGreaterThan(0);const data=JSON.parse(fs.readFileSync(path.join(folder,exports[exports.length-1]),'utf8'));
    expect(data.format).toBe('twichui-market-addon-data');expect(data.synthetic).toBe(true);expect(data.items).toHaveLength(2);expect(data.items[0].value.recent_price).toBe('100');
    await page.locator('#disconnect').click();await expect.poll(async()=>(await invoke('app_state')).mode,{timeout:20000}).toBe('disconnected');
    expect((await invoke('app_state')).cache.item_count).toBe(2);
    const revoked=(await(await api.get('/api/v1/companion/devices')).json()).devices.find(row=>row.id===device.id);expect(revoked.revoked).toBe(true);
    fs.writeFileSync(path.join(shots,'installed-smoke.json'),JSON.stringify({fixture:true,version:(await invoke('app_state')).version,native_browser_approval_api:true,native_browser_approval_ui:true,
      native_thread_hidden_sync:true,single_instance_restore:true,preferences_saved:true,credential_and_cache_restart:true,hidden_startup:true,current_user_autostart_enable_disable:true,actual_tray_menu:true,tray_settings_sync_pause_open_quit:true,native_minimize_close_to_tray:true,export_valid:true,server_revocation:true,offline_cache_preserved:true,
      website_approval_ui_verified:true,full_tray_autostart_upgrade_acceptance_complete:false},null,2));
    await nativeControl('Quit');
    console.log('Installed v2: actual Edge website approval, real Rust hidden-window sync, preference save, single-instance restore, export, revocation and offline cache passed.');
  }finally{await websiteBrowser?.close();await api.dispose();await browser.close().catch(()=>{});}
})().catch(error=>{console.error(error);process.exitCode=1});
