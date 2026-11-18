// Rendering/intent only. Actual Windows picker and component integration are separate gates.
const {chromium,expect}=require('@playwright/test');
const AxeBuilder=require('@axe-core/playwright').default;
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
(async()=>{
 const root=path.resolve(__dirname,'../../desktop/ui');
 const server=http.createServer((req,res)=>{const file=({'/':'index.html','/app.js':'app.js','/style.css':'style.css','/icon.png':'icon.png'})[req.url];if(!file){res.writeHead(404).end();return;}res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.png')?'image/png':'text/html');res.end(fs.readFileSync(path.join(root,file)));});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH}:{})});
 try{
  const context=await browser.newContext({viewport:{width:520,height:850},reducedMotion:'reduce'});
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   window.__state={version:'synthetic summary candidate',settings:{schema_version:1,server:'https://fixture.invalid/',selected_market:2,automatic_sync:true,interval_minutes:30,close_to_tray:true},mode:'companion',connected:true,account:{id:1,username:'Synthetic player'},bootstrap:{account:{id:1},markets:[{id:2,label:'US — Normal — Horde',available_for_sync:true}],suggested_market_id:2},sync:{revision:1,sync:{phase:'ready',running:false,selected_market:2,automatic_sync:true}},cache:{has_completed_cache:true,item_count:5197},settings_valid:true,delivery:{notice:'Not connected'}};
   const callbacks={};window.__calls=[];window.__emit=()=>{window.__state.sync.revision++;callbacks['companion-state']?.({payload:structuredClone(window.__state)});};
   window.__TAURI__={event:{listen:async(name,fn)=>{callbacks[name]=fn;return()=>{};}},core:{invoke:async(command,args)=>{
    window.__calls.push({command,args});if(command==='app_state')return structuredClone(window.__state);
    if(command==='update_state')return {status:'idle',message:'Synthetic fixture'};
    if(command==='prepare_workshop'){
     if(window.__defer)return await new Promise((resolve,reject)=>{window.__resolveReview=resolve;window.__rejectReview=reject;});
     if(window.__fail)throw new Error(window.__fail);
     if(window.__state.delivery?.configuration?.enabled){window.__state.delivery.status.error=null;return {connected:true};}
     return {review_id:'native-owned-review',installation:'C:\\Games\\Forever',market:'US — Normal — Horde'};
    }
    if(command==='cancel_workshop')return null;
    if(command==='confirm_workshop'){
     if(args.reviewId!=='native-owned-review')throw new Error('wrong native review');
     window.__state.delivery={configuration:{version:2,enabled:true,scope:{algorithm:'twichui-pricing-v1'},installation:'C:\\Games\\Forever',selection:{kind:'broad_summary',market_id:2,region:'us'},history_days:0},status:{published_generation:'a'.repeat(64),last_successful_write:'2026-11-17T12:00:00Z',result:'Up to date.',error:null,summary_records:5197}};return null;
    }
    throw new Error('Unexpected IPC '+command);
   }}};
  });
  await page.goto('http://127.0.0.1:'+server.address().port);
  await expect(page.locator('#workshop-connect')).toBeVisible();await expect(page.locator('#workshop-state')).toHaveText('Not connected');
  await expect(page.locator('#workshop-market')).toHaveText('US — Normal — Horde');
  await expect(page.locator('.more > summary')).toHaveText('Developer diagnostics & recovery');
  for(const id of ['archive-budget','scope-variants','scope-from','scope-through','workshop-pricing','delivery-installation','delivery-days'])await expect(page.locator('#'+id)).toBeHidden();
  expect(await page.evaluate(()=>window.__calls.some(c=>['archive_workshop','configure_delivery','prepare_workshop'].includes(c.command)))).toBe(false);
  await page.locator('#workshop-connect').click();await expect(page.locator('#workshop-confirmation')).toBeVisible();await expect(page.locator('#workshop-authorize')).toBeFocused();
  await page.keyboard.press('Escape');await expect(page.locator('#workshop-confirmation')).toBeHidden();await expect(page.locator('#workshop-connect')).toBeFocused();
  expect(await page.evaluate(()=>window.__calls.some(c=>c.command==='confirm_workshop'))).toBe(false);
  await page.locator('#workshop-connect').click();await page.locator('#workshop-authorize').click();await expect(page.locator('#workshop-state')).toHaveText('Up to date');await expect(page.locator('#workshop-connect')).toBeHidden();await expect(page.locator('#workshop-state')).toBeFocused();
  expect(await page.evaluate(()=>window.__calls.filter(c=>c.command==='confirm_workshop').map(c=>c.args))).toEqual([{reviewId:'native-owned-review'}]);
  expect(await page.evaluate(()=>window.__calls.some(c=>c.command==='archive_workshop'))).toBe(false);
  const output=process.env.MARKET_WORKSHOP_UI_EVIDENCE||path.resolve('artifacts/workshop-delivery/browser');fs.mkdirSync(output,{recursive:true});
  await page.screenshot({path:path.join(output,'workshop-connected.png'),fullPage:true});
  await page.evaluate(()=>{window.__state.delivery.status.result='Preparing market data.';window.__state.delivery.status.error='Market summaries are being prepared; synchronization will retry';window.__state.sync.error=window.__state.delivery.status.error;window.__emit();});
  await expect(page.locator('#workshop-state')).toHaveText('Updating');await expect(page.locator('#message')).toBeHidden();
  await page.evaluate(()=>{window.__state.sync.error='Server request failed';window.__emit();});await expect(page.locator('#workshop-state')).toHaveText('Needs attention');await expect(page.locator('#message')).toContainText('Server request failed');
  await page.evaluate(()=>{window.__state.sync.error=null;window.__emit();});
  await page.evaluate(()=>{window.__state.delivery.status.result='Waiting for World of Warcraft to close.';window.__state.delivery.status.error='Waiting for World of Warcraft to close.';window.__emit();});
  await expect(page.locator('#workshop-state')).toHaveText('Waiting for WoW to close');await expect(page.locator('#workshop-connect')).toBeHidden();
  await page.evaluate(()=>{window.__state.delivery.status.result='Update failed';window.__state.delivery.status.error='technical diagnostic only';window.__emit();});
  await expect(page.locator('#workshop-state')).toHaveText('Needs attention');await expect(page.locator('#workshop-connect')).toHaveText('Retry');
  await page.locator('#workshop-connect').click();await expect(page.locator('#workshop-confirmation')).toBeHidden();await expect(page.locator('#workshop-state')).toHaveText('Up to date');
  expect(await page.evaluate(()=>window.__calls.filter(c=>c.command==='confirm_workshop').length)).toBe(1);
  for(const width of [320,390,520]){await page.setViewportSize({width,height:850});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);}
  await page.screenshot({path:path.join(output,'workshop-phone.png'),fullPage:true});
  const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();expect(audit.violations).toEqual([]);
  await page.evaluate(()=>{window.__state.delivery={notice:'Not connected'};window.__defer=true;window.__emit();});
  await page.locator('#workshop-connect').click();await expect.poll(()=>page.evaluate(()=>Boolean(window.__resolveReview))).toBe(true);await expect(page.locator('#workshop-state')).toHaveText('Connecting Workshop');
  await page.evaluate(()=>{window.__state.account.id=2;window.__state.bootstrap.account.id=2;window.__emit();window.__resolveReview({review_id:'stale',installation:'C:\\PrivateOldAccount',market:'old'});});
  await expect(page.locator('#workshop-connect')).toBeEnabled();await expect(page.locator('#workshop-confirmation')).toBeHidden();await expect(page.locator('#workshop-note')).not.toContainText('PrivateOldAccount');
  await page.evaluate(()=>{window.__resolveReview=null;window.__rejectReview=null;});await page.locator('#workshop-connect').click();await expect.poll(()=>page.evaluate(()=>Boolean(window.__rejectReview))).toBe(true);
  await page.evaluate(()=>{window.__state.account.id=3;window.__state.bootstrap.account.id=3;window.__emit();window.__rejectReview(new Error('old account failure'));});await expect(page.locator('#workshop-connect')).toBeEnabled();await expect(page.locator('#workshop-note')).not.toContainText('old account failure');
  await expect(page.locator('#workshop-note')).toHaveText('Your account or market changed during setup. Connect Workshop again.');
  await page.evaluate(()=>{window.__resolveReview=null;window.__rejectReview=null;});await page.locator('#workshop-connect').click();await expect.poll(()=>page.evaluate(()=>Boolean(window.__resolveReview))).toBe(true);
  await page.evaluate(()=>{window.__state.settings.selected_market=3;window.__emit();window.__resolveReview({review_id:'stale-market',installation:'C:\\PrivateOldMarket',market:'old'});});
  await expect(page.locator('#workshop-connect')).toBeEnabled();await expect(page.locator('#workshop-confirmation')).toBeHidden();await expect(page.locator('#workshop-note')).toHaveText('Your account or market changed during setup. Connect Workshop again.');
  await page.evaluate(()=>{window.__defer=false;window.__fail='Unsupported or invalid market data: Workshop needs an update.';});await page.locator('#workshop-connect').click();await expect(page.locator('#workshop-note')).toContainText('Workshop needs an update');
  const failures=[
   ['wrong_folder','game_folder','Choose the Forever game folder containing Wow.exe and Interface/AddOns.'],
   ['unsupported_client','executable_version','This Wow.exe version is not verified for Forever. Choose a supported Forever installation.'],
   ['workshop_addon','workshop_addon','Workshop needs an update or is missing files. Install the compatible TwichUI addon, then retry.'],
   ['access_denied','destination','Windows could not access this installation safely. Choose a folder where your Windows account can read the game and write addon data.'],
   ['ownership_conflict','destination','Existing Market data could not be safely adopted. Reconnect its original Market account and market, or choose another installation. Your files were preserved.'],
   ['context_changed','setup_context','Your account or market changed during setup. Connect Workshop again.'],
   ['folder_picker','folder_picker','Windows could not open or read the folder picker. Close the dialog and retry Connect Workshop.'],
   ['internal','setup','Workshop setup could not finish because of an unexpected error. Retry or save developer diagnostics. Your files were preserved.'],
   ['cancelled','folder_picker','Folder selection cancelled.'],
  ];
  for(const [code,stage,message] of failures){
   await page.evaluate(value=>{window.__fail=JSON.stringify(value);},{code,stage,message,details:'sanitized fixture detail'});
   await page.locator('#workshop-connect').click();
   await expect(page.locator('#workshop-note')).toHaveText(message);
   await expect(page.locator('#workshop-state')).toHaveText(code==='cancelled'?'Not connected':'Needs attention');
   await expect(page.locator('#message')).toBeHidden();
  }
  await page.locator('.more > summary').click();await expect(page.locator('#delivery-status')).toContainText('Setup detail: cancelled · folder_picker');
  await page.evaluate(()=>{window.__fail=null;});await page.locator('#workshop-connect').click();await expect(page.locator('#workshop-confirmation')).toBeVisible();
  expect(errors).toEqual([]);console.log('PASS mocked IPC: simple connection, one native confirmation, retry, no archive, safe status, Escape/focus, mobile, WCAG A/AA and delayed account isolation. Not native evidence.');
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
