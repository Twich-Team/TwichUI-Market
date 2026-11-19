// Real installed candidate, actual native picker + worker + authenticated API.
// Invoked before the optional history archive exists. No IPC is mocked.
const fs=require('node:fs');const path=require('node:path');const {createHash}=require('node:crypto');const {execFile}=require('node:child_process');const {promisify}=require('node:util');const {expect}=require('@playwright/test');
module.exports=async({page,invoke,api,shots,sourceCommit})=>{
 if(process.platform!=='win32'||process.env.GITHUB_ACTIONS!=='true')throw Error('Disposable Windows runner required');
 const helper=async(action,gamePath)=>{
  const args=['-NoProfile','-NonInteractive','-File',path.resolve('scripts/windows/workshop-fixtures.ps1'),'-Action',action];
  if(gamePath)args.push('-GamePath',gamePath);
  return JSON.parse((await promisify(execFile)('powershell.exe',args,{timeout:45000})).stdout.trim());
 };
 const hash=file=>createHash('sha256').update(fs.readFileSync(file)).digest('hex');
 const archive=path.join(process.env.MARKET_TEST_APP_DATA,'history-archive-v1.sqlite');expect(fs.existsSync(archive)).toBe(false);
 const fixture=await helper('Setup');const game=fixture.first;
 const configFile=path.join(process.env.MARKET_TEST_APP_DATA,'workshop-delivery-v1.json');
 const target=path.join(game,'Interface','AddOns','TwichUI_MarketData','Data.lua');
 const saved=path.join(game,'WTF','Account','SyntheticOnly','SavedVariables','TwichUIWorkshop.lua');const savedHash=hash(saved);
 const root=path.join(shots,'workshop-installed');fs.mkdirSync(root,{recursive:true});
 const waitIdle=()=>expect.poll(async()=>(await invoke('app_state')).sync.sync.running,{timeout:60000}).toBe(false);
 const clickPicker=async(action,folder)=>{
  await page.locator('#workshop-connect').click();
  return helper(action,folder);
 };
 try{
  if(!(await invoke('app_state')).sync.sync.automatic_sync){await page.locator('#pause').click();await waitIdle();}
  // No discovery metadata: real Windows shell dialog, cancelled, no saved permission.
  await clickPicker('CancelFolder');await expect(page.locator('#workshop-connect')).toBeEnabled();expect(fs.existsSync(configFile)).toBe(false);
  const wrong=path.join(fixture.base,'WrongGame');fs.mkdirSync(wrong);fs.writeFileSync(path.join(wrong,'Wow.exe'),'not a PE/game');
  await clickPicker('ChooseFolder',wrong);await expect(page.locator('#workshop-state')).toHaveText('Needs attention');expect(fs.existsSync(configFile)).toBe(false);
  await expect(page.locator('#workshop-note')).toHaveText('Choose the Forever game folder containing Wow.exe and Interface/AddOns.');
  const diagnosticPath=await invoke('save_diagnostics');const diagnostic=JSON.parse(fs.readFileSync(diagnosticPath,'utf8')).workshop_setup;
  expect(diagnostic.code).toBe('wrong_folder');expect(diagnostic.stage).toBe('game_folder');expect(JSON.stringify(diagnostic)).not.toContain(wrong);
  fs.writeFileSync(path.join(root,'setup-failure-diagnostics.json'),JSON.stringify(diagnostic,null,2));
  await page.screenshot({path:path.join(root,'native-setup-wrong-folder.png'),fullPage:true});
  const summaryLua=path.join(game,'Interface','AddOns','TwichUI_Workshop','Summary.lua');
  fs.renameSync(summaryLua,summaryLua+'.fixture-backup');
  try {
   await clickPicker('ChooseFolder',game);await expect(page.locator('#workshop-state')).toHaveText('Needs attention');
   await expect(page.locator('#workshop-note')).toContainText('Workshop Summary.lua is missing or unreadable');await expect(page.locator('#workshop-note')).toContainText('(Check: summary_lua)');const missingDiagnostic=JSON.parse(fs.readFileSync(await invoke('save_diagnostics'),'utf8')).workshop_setup;expect(missingDiagnostic.code).toBe('workshop_addon');expect(missingDiagnostic.check).toBe('summary_lua');expect(fs.existsSync(configFile)).toBe(false);
   expect(hash(saved)).toBe(savedHash);
  } finally {fs.renameSync(summaryLua+'.fixture-backup',summaryLua);}
  // The next native selection uses the real coordinated addon source/capability.
  await clickPicker('ChooseFolder',game);await expect(page.locator('#workshop-confirmation')).toBeVisible();
  await expect(page.locator('#workshop-confirmed-folder')).toContainText(game);
  await page.screenshot({path:path.join(root,'native-one-permission.png'),fullPage:true});
  const syncBefore=await (await api.get('/__fixture__/native-network')).json();
  await page.locator('#workshop-authorize').click();
  await expect.poll(async()=>(await invoke('app_state')).delivery.status?.published_generation,{timeout:90000}).toMatch(/^[a-f0-9]{64}$/);
  await waitIdle();const syncAfter=await (await api.get('/__fixture__/native-network')).json();
  expect(syncAfter.summary_preparations-syncBefore.summary_preparations).toBeGreaterThan(0);
  expect(syncAfter.price_runs-syncBefore.price_runs).toBe(1);
  const first=(await invoke('app_state')).delivery;expect(first.configuration.version).toBe(2);
  expect(first.status.summary_records).toBe(2);expect(first.status.loaded_game_generation).toBeNull();expect(fs.existsSync(archive)).toBe(false);
  const beforeHash=hash(target),mtime=fs.statSync(target).mtimeMs;await invoke('sync_now');
  await expect.poll(async()=>(await invoke('app_state')).delivery.status?.result,{timeout:60000}).toBe('Up to date.');await waitIdle();
  expect(hash(target)).toBe(beforeHash);expect(fs.statSync(target).mtimeMs).toBe(mtime);expect(hash(saved)).toBe(savedHash);
  await page.screenshot({path:path.join(root,'native-archive-free-connected.png'),fullPage:true});
  // Native source is advanced in the isolated fixture only. While Wow.exe is
  // running, the actual worker publishes the new generation without a game close.
  await helper('StartGame');expect((await helper('GameRunning')).running).toBe(true);
  expect((await api.post('/__fixture__/workshop-source',{data:{action:'advance'}})).ok()).toBe(true);
  await invoke('sync_now');
  await expect.poll(async()=>(await invoke('app_state')).delivery.status?.published_generation,{timeout:60000}).not.toBe(first.status.published_generation);await waitIdle();
  expect((await helper('GameRunning')).running).toBe(true);
  expect(hash(target)).not.toBe(beforeHash);await expect(page.locator('#workshop-state')).toHaveText('Files ready');
  await expect(page.locator('#workshop-note')).toContainText('reload');
  await page.screenshot({path:path.join(root,'native-wow-open-publication.png'),fullPage:true});
  await helper('StopGame');
  const second=(await invoke('app_state')).delivery;expect(fs.existsSync(path.join(path.dirname(target),'Previous.lua'))).toBe(true);
  // Corruption is injected on the HTTP fixture boundary. Native validation,
  // staging and installed files remain the real product implementation.
  const secondHash=hash(target);expect((await api.post('/__fixture__/workshop-source',{data:{action:'corrupt'}})).ok()).toBe(true);
  await invoke('sync_now');await expect(page.locator('#workshop-state')).toHaveText('Needs attention',{timeout:60000});await waitIdle();expect(hash(target)).toBe(secondHash);
  expect((await api.post('/__fixture__/workshop-source',{data:{action:'normal'}})).ok()).toBe(true);
  await page.locator('#workshop-connect').click();await waitIdle();await expect(page.locator('#workshop-confirmation')).toBeHidden();
  expect(hash(saved)).toBe(savedHash);expect(fs.existsSync(archive)).toBe(false);
  const addons=path.join(game,'Interface','AddOns');const publication=path.join(root,'publication');fs.mkdirSync(publication,{recursive:true});
  for(const name of fs.readdirSync(addons).filter(n=>/^TwichUI_Market(?:Data|Part[AB]\d\d)$/.test(n)))fs.cpSync(path.join(addons,name),path.join(publication,name),{recursive:true});
  const facts={synthetic:true,real_game:false,source_commit:sourceCommit,coordinated_addon_commit:fs.readFileSync('contracts/workshop-summary/v1/addon-source.txt','utf8').trim(),first_status:first.status,second_status:second.status,native_picker:true,wrong_game_refused:true,one_installation_confirmation:true,no_archive:true,no_change_mtime_preserved:true,wow_running_publication:true,wow_alive_after_publication:true,corrupt_http_preserved:true,savedvariables_sha256:savedHash,game_consumption:'not performed'};
  fs.writeFileSync(path.join(root,'evidence.json'),JSON.stringify(facts,null,2));
  // Stop this source candidate's delivery before the independent legacy M2 test.
  await page.locator('#pause').click();await waitIdle();
  await invoke('configure_delivery',{installation:game,algorithm:'twichui-pricing-v1',historyDays:0,operation:'disable',confirmed:false,variants:null});
  // Registry discovery receives two candidates, with no prior native config.
  const backup=configFile+'.summary-fixture';fs.renameSync(configFile,backup);
  await helper('Register');await helper('RegisterSecond');
  await page.locator('#workshop-connect').click();await helper('ChooseFolder',fixture.second);
  await expect(page.locator('#workshop-confirmation')).toBeVisible();await expect(page.locator('#workshop-confirmed-folder')).toContainText(fixture.second);
  await page.locator('#workshop-cancel').click();expect(fs.existsSync(configFile)).toBe(false);fs.renameSync(backup,configFile);
  facts.multiple_candidates_native_choice=true;fs.writeFileSync(path.join(root,'evidence.json'),JSON.stringify(facts,null,2));
 } catch(error){
  const state=await invoke('app_state').catch(()=>null);if(state)fs.writeFileSync(path.join(root,'failure-state.json'),JSON.stringify({version:state.version,connected:state.connected,error:state.error,sync:state.sync,delivery:state.delivery,automatic_sync:state.settings.automatic_sync},null,2));
  await page.screenshot({path:path.join(root,'failure-state.png'),fullPage:true}).catch(()=>{});throw error;
 } finally {await helper('StopGame').catch(()=>{});await helper('ClearRegistry').catch(()=>{});}
};
