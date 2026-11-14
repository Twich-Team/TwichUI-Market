// Real installed Windows WebView2 + Rust IPC + disposable API. No IPC is mocked.
const {chromium,request,expect}=require('@playwright/test');
const fs=require('node:fs');const path=require('node:path');const {execFile}=require('node:child_process');const {promisify}=require('node:util');
(async()=>{
  if(process.env.GITHUB_ACTIONS!=='true'||process.platform!=='win32')throw new Error('Installed acceptance requires the disposable Windows runner');
  const endpoint=`http://127.0.0.1:${process.env.MARKET_TEST_CDP_PORT}`;
  await expect.poll(async()=>{try{return(await fetch(`${endpoint}/json/version`)).ok}catch{return false}},{timeout:30000}).toBe(true);
  const browser=await chromium.connectOverCDP(endpoint);
  const api=await request.newContext({baseURL:process.env.MARKET_TEST_SERVER,extraHTTPHeaders:{Origin:process.env.MARKET_TEST_SERVER}});
  const shots=path.resolve('artifacts/companion-v2');fs.mkdirSync(shots,{recursive:true});
  try{
    const page=browser.contexts()[0].pages()[0];
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
    const login=await api.post('/api/v1/auth/login',{data:{username:'native-fixture',password:'synthetic browser fixture password'}});expect(login.ok()).toBe(true);
    const csrf=(await login.json()).csrf_token;const headers={'x-csrf-token':csrf};
    const details=await api.get(`/api/v1/companion/authorizations/${approval.request_id}`);expect(details.ok()).toBe(true);
    const consent=await details.json();expect(consent.device_name).toBe('Installed Windows fixture');
    const decision=await api.post(`/api/v1/companion/authorizations/${approval.request_id}/decision`,{headers,data:{decision:'approve',consent_token:consent.consent_token}});expect(decision.ok()).toBe(true);
    const callback=new URL((await decision.json()).redirect_uri);expect(callback.hostname).toBe('127.0.0.1');expect(callback.pathname).toBe('/companion/callback');
    // A top-level browser navigation carries neither the API Origin override nor
    // API cookies. Keep the strict native callback policy intact.
    const returned=await fetch(callback.toString(),{redirect:'error'});expect(returned.ok).toBe(true);expect(returned.headers.get('cache-control')).toBe('no-store');
    await expect(page.locator('#connected-panel')).toBeVisible({timeout:20000});
    await expect(page.locator('#sync-progress')).toBeVisible({timeout:15000});await page.screenshot({path:path.join(shots,'native-sync-progress.png')});
    await expect(page.locator('#cache-count')).toContainText('2 item variants',{timeout:30000});
    await expect.poll(async()=>(await invoke('app_state')).sync.sync.last_sync_ms,{timeout:15000}).toBeTruthy();
    await expect(page.locator('#market-name')).toHaveText('US — Normal — Horde');await expect(page.locator('#synthetic-warning')).toBeVisible();
    await page.screenshot({path:path.join(shots,'native-dashboard.png')});
    const profile=(await api.get('/api/v1/companion/devices')).json();const device=(await profile).devices[0];expect(device.last_sync_at).toBeTruthy();expect(device.selected_market_id).toBe(1);
    await page.locator('#settings-open').click();await page.screenshot({path:path.join(shots,'native-settings.png'),fullPage:true});
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
    await page.locator('.more summary').click();await page.locator('#export').click();await expect(page.locator('#message')).toContainText('Export saved');
    const folder=path.join(process.env.MARKET_TEST_APP_DATA,'exports');const exports=fs.readdirSync(folder).filter(file=>file.endsWith('.json')&&!file.startsWith('diagnostics'));
    expect(exports.length).toBeGreaterThan(0);const data=JSON.parse(fs.readFileSync(path.join(folder,exports[exports.length-1]),'utf8'));
    expect(data.format).toBe('twichui-market-addon-data');expect(data.synthetic).toBe(true);expect(data.items).toHaveLength(2);expect(data.items[0].value.recent_price).toBe('100');
    await page.locator('#disconnect').click();await expect.poll(async()=>(await invoke('app_state')).mode,{timeout:20000}).toBe('disconnected');
    expect((await invoke('app_state')).cache.item_count).toBe(2);
    const revoked=(await(await api.get('/api/v1/companion/devices')).json()).devices.find(row=>row.id===device.id);expect(revoked.revoked).toBe(true);
    fs.writeFileSync(path.join(shots,'installed-smoke.json'),JSON.stringify({fixture:true,version:(await invoke('app_state')).version,native_browser_approval_api:true,
      native_thread_hidden_sync:true,single_instance_restore:true,preferences_saved:true,export_valid:true,server_revocation:true,offline_cache_preserved:true,
      website_approval_ui_verified:false,full_tray_autostart_upgrade_acceptance_complete:false},null,2));
    console.log('Installed v2: browser approval API, real Rust hidden-window sync, preference save, single-instance restore, export, revocation and offline cache passed.');
  }finally{await api.dispose();await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
