// Real verified 0.1 installer -> current installer; legacy UI/token exists only in this test.
const {chromium,request,expect}=require('@playwright/test');
const fs=require('node:fs');const path=require('node:path');const {execFile,spawn}=require('node:child_process');const {promisify}=require('node:util');const {createHash}=require('node:crypto');
(async()=>{
  if(process.env.GITHUB_ACTIONS!=='true'||process.platform!=='win32')throw new Error('Disposable Windows runner only');
  const endpoint=`http://127.0.0.1:${process.env.MARKET_TEST_CDP_PORT}`;
  const available=async()=>{try{return(await fetch(endpoint+'/json/version')).ok}catch{return false}};
  await expect.poll(available,{timeout:30000}).toBe(true);
  let browser=await chromium.connectOverCDP(endpoint);let page=browser.contexts()[0].pages()[0];
  const api=await request.newContext({baseURL:process.env.MARKET_TEST_SERVER,extraHTTPHeaders:{Origin:process.env.MARKET_TEST_SERVER}});
  const invoke=(command,args={})=>page.evaluate(({command,args})=>window.__TAURI__.core.invoke(command,args),{command,args});
  try{
    await expect(page.locator('#token')).toBeVisible();
    const login=await api.post('/api/v1/auth/login',{data:{username:'native_fixture',password:'synthetic browser fixture password'}});expect(login.ok()).toBe(true);
    const csrf=(await login.json()).csrf_token;
    const issued=await api.post('/api/v1/devices',{headers:{'x-csrf-token':csrf},data:{name:'Synthetic upgrade legacy PC'}});expect(issued.ok()).toBe(true);
    const credential=await issued.json();
    await page.locator('#server').fill(process.env.MARKET_TEST_SERVER);await page.locator('#token').fill(credential.token);await page.locator('#market').fill('1');
    await page.getByRole('button',{name:'Connect securely',exact:true}).click();await expect(page.locator('#connected')).toContainText('Connected to');await expect(page.locator('#token')).toHaveValue('');
    await page.locator('#sync').click();await expect(page.locator('#count')).toContainText('2 item variants',{timeout:30000});
    const old=await invoke('status',{market:1});expect(old.item_count).toBe(2);expect(old.has_completed_cache).toBe(true);
    const connectionFile=path.join(process.env.MARKET_TEST_APP_DATA,'connection.json');const connectionBefore=fs.readFileSync(connectionFile,'utf8');
    // Close the old installed application through its real native window.
    await promisify(execFile)('powershell.exe',['-NoProfile','-NonInteractive','-Command',
      '$app=Get-Process -Name "twichui-market-companion" | Where-Object {$_.Path -eq $env:MARKET_TEST_INSTALLED_EXE};if(@($app).Count -ne 1){throw "Expected one old installed process"};$null=$app.CloseMainWindow();if(-not $app.WaitForExit(10000)){throw "Old installed app did not close"}'],{timeout:15000});
    await expect.poll(available).toBe(false);await browser.close().catch(()=>{});
    // Run the new current-user installer over the actual old installation.
    const sdkInstall=process.env.MARKET_TEST_UPDATER_SDK==='true';
    if(sdkInstall){
      const expected=process.env.MARKET_TEST_EXPECTED_EXE_SHA256||createHash('sha256').update(fs.readFileSync('desktop/src-tauri/target/release/twichui-market-companion.exe')).digest('hex');
      expect(expected).toMatch(/^[a-f0-9]{64}$/);
      await promisify(execFile)('cargo',['test','--manifest-path','desktop/src-tauri/Cargo.toml','--locked','updates::tests::launch_owner_signed_installer_on_disposable_runner','--','--ignored','--exact','--nocapture'],{timeout:180000,maxBuffer:2*1024*1024});
      await expect.poll(()=>{try{return createHash('sha256').update(fs.readFileSync(process.env.MARKET_TEST_INSTALLED_EXE)).digest('hex')}catch{return null}},{timeout:90000}).toBe(expected);
    }else{
      await promisify(execFile)(process.env.MARKET_TEST_NEW_INSTALLER,['/S',`/D=${process.env.MARKET_TEST_INSTALL_DIRECTORY}`],{timeout:90000});
    }
    const upgraded=spawn(process.env.MARKET_TEST_INSTALLED_EXE,[],{detached:true,stdio:'ignore'});upgraded.unref();
    await expect.poll(available,{timeout:30000}).toBe(true);browser=await chromium.connectOverCDP(endpoint);page=browser.contexts()[0].pages()[0];
    await expect(page.locator('#legacy-warning')).toBeVisible({timeout:20000});
    await expect.poll(async()=>(await invoke('app_state')).account?.username,{timeout:20000}).toBe('native_fixture');
    const state=await invoke('app_state');expect(state.mode).toBe('legacy');expect(state.cache.item_count).toBe(2);expect(state.settings.interval_minutes).toBe(30);
    expect(new URL(state.settings.server).origin).toBe(process.env.MARKET_TEST_SERVER);
    expect(fs.readFileSync(connectionFile,'utf8')).toBe(connectionBefore);
    // The same legacy grant remains valid. Upgrading must not revoke credentials.
    const legacy=await api.get('/api/v1/auth/me',{headers:{authorization:`Bearer ${credential.token}`}});expect(legacy.ok()).toBe(true);
    await expect.poll(async()=>(await invoke('app_state')).sync.sync.last_sync_ms,{timeout:20000}).toBeTruthy();
    const exportPath=await invoke('export_market');const exported=JSON.parse(fs.readFileSync(exportPath,'utf8'));
    expect(exported.items).toHaveLength(2);expect(exported.items[0].value.recent_price).toBe('100');
    const source=(await promisify(execFile)('git',['rev-parse','HEAD'])).stdout.trim();
    fs.mkdirSync(path.resolve('artifacts/companion-v2'),{recursive:true});
    fs.writeFileSync(path.resolve('artifacts/companion-v2/legacy-upgrade.json'),JSON.stringify({fixture:true,source_commit:source,from_version:'0.1.0',to_version:state.version,
      actual_old_installer:true,actual_new_installer:true,legacy_credentials_preserved:true,cache_preserved:true,connection_settings_preserved:true,
      legacy_metadata_migrated:true,new_native_sync:true,export_contract_preserved:true,signed_updater_sdk_install:sdkInstall,uninstall_data_preservation_verified_by_parent:false},null,2));
    await invoke('quit').catch(()=>{});await expect.poll(available).toBe(false);
    console.log('Actual 0.1 -> v2 installed upgrade preserves legacy credential, connection, cache, sync and export.');
  }finally{await api.dispose();await browser.close().catch(()=>{});}
})().catch(error=>{console.error(error);process.exitCode=1});
