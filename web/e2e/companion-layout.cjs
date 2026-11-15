// Browser-only rendering/accessibility checks. These do not claim native/Windows evidence.
const {chromium,expect}=require('@playwright/test');const AxeBuilder=require('@axe-core/playwright').default;
const path=require('node:path');const fs=require('node:fs');
const settings={schema_version:1,server:'https://market.twich.gg/',launch_at_login:false,start_in_tray:false,minimize_to_tray:false,close_to_tray:true,
  automatic_sync:true,interval_minutes:30,sync_on_startup:true,error_notifications:true,selected_market:null,onboarding_completed:false};
const state={version:'2.0.0-beta.1',settings,mode:'disconnected',connected:false,account:null,bootstrap:null,offline_market:null,
  sync:{revision:0,sync:{phase:'not_connected',automatic_sync:true,next_sync_ms:null,last_sync_ms:null,last_server_check_ms:null,upstream_update_ms:null,generation:null,
    received_new_generation:false,pages_completed:0,retry_attempts:0,selected_market:null,running:false},error:null},cache:null,approval:null,approving:false,refreshing:false,
  error:null,settings_valid:true,autostart_enabled:false,quitting:false,window_visible:true};
(async()=>{
 const browser=await chromium.launch({headless:true});try{
 const context=await browser.newContext({viewport:{width:520,height:710},reducedMotion:'reduce'});const page=await context.newPage();const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.addInitScript(initial=>{
   window.__layoutState=initial;window.__layoutCalls=[];const callbacks={};
   window.__layoutEmit=(name,payload)=>callbacks[name]?.({payload});
   window.__TAURI__={core:{invoke:async(command,args)=>{window.__layoutCalls.push({command,args});
     if(command==='app_state')return window.__layoutState;
     if(command==='update_state')return {status:'idle',message:'Check for verified companion updates.',restart_required:false};
     if(command==='check_update')return {status:'available',version:'2.0.0',notes:'Synthetic rendering fixture only',message:'Companion 2.0.0 is available.',restart_required:false};
     if(command==='install_update')return {status:'installing',message:'Synthetic intent only; no installation',restart_required:false};
     if(command==='save_settings'){window.__layoutState={...window.__layoutState,settings:args.settings};return null;}
     return null;
   }},event:{listen:async(name,callback)=>{callbacks[name]=callback;return()=>{};}}};
 },state);
 await page.goto('file:///repo/desktop/ui/index.html');await expect(page.locator('#welcome')).toBeVisible();await expect(page.locator('#sign-in')).toBeVisible();
 await expect(page.locator('#message')).toBeHidden();
 await expect(page.locator('#token')).toHaveCount(0);await expect(page.locator('input[type=number]')).toHaveCount(0);
 const folder=path.resolve('artifacts/companion-v2');fs.mkdirSync(folder,{recursive:true});await page.screenshot({path:path.join(folder,'layout-welcome.png')});
 let audit=await new AxeBuilder({page}).analyze();expect(audit.violations.filter(v=>['critical','serious'].includes(v.impact))).toEqual([]);
 await page.evaluate(()=>{const next=structuredClone(window.__layoutState);next.connected=true;next.sync.sync.phase='offline';window.__layoutState=next;window.__layoutEmit('companion-state',next);});
 await expect(page.locator('#status-title')).toHaveText('No offline prices downloaded yet.');
 await page.locator('#settings-open').click();await expect(page.locator('#settings-panel')).toBeVisible();
 await page.locator('#sync-interval').selectOption('60');
 await page.evaluate(()=>{const next=structuredClone(window.__layoutState);next.sync.revision=1;next.sync.sync.phase='synchronizing';next.sync.sync.pages_completed=1;next.sync.sync.running=true;
   window.__layoutState=next;window.__layoutEmit('companion-state',next);});
 await expect(page.locator('#sync-interval')).toHaveValue('60'); // Progress must never discard a draft preference.
 await page.locator('#settings-save').click();await expect(page.locator('#settings-panel')).toBeHidden();
 expect(await page.evaluate(()=>window.__layoutCalls.find(call=>call.command==='save_settings').args.settings.interval_minutes)).toBe(60);
 expect(await page.evaluate(()=>window.__layoutCalls.filter(call=>call.command==='save_settings').length)).toBe(1);
 await page.evaluate(()=>{const next=structuredClone(window.__layoutState);next.settings.onboarding_completed=true;next.mode='companion';next.connected=true;next.account={id:1,username:'Synthetic preview'};
 next.bootstrap={markets:[{id:2,label:'US — Normal — Horde',available_for_sync:true}],suggested_market_id:2,preference_fallback:false};
 next.sync.revision=2;Object.assign(next.sync.sync,{phase:'ready',running:false,selected_market:2,last_sync_ms:1794666000000,last_server_check_ms:1794665700000,upstream_update_ms:1794665400000,next_sync_ms:1794667800000});
 next.cache={market_id:2,item_count:12345,has_completed_cache:true,downloading:false,synthetic:true};window.__layoutState=next;window.__layoutEmit('companion-state',next);});
 await expect(page.locator('#market-name')).toHaveText('US — Normal — Horde');await expect(page.locator('#cache-count')).toContainText('12,345');
 await page.screenshot({path:path.join(folder,'layout-dashboard.png')});await page.locator('#settings-open').click();await page.screenshot({path:path.join(folder,'layout-settings.png'),fullPage:true});
 await page.setViewportSize({width:440,height:560});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await page.locator('#update-check').click();await expect(page.locator('#update-install')).toBeVisible();
 await page.locator('#update-install').click();await expect(page.locator('#update-confirm')).toBeVisible();
 expect(await page.evaluate(()=>window.__layoutCalls.filter(call=>call.command==='install_update').length)).toBe(0);
 await page.locator('#update-confirm-cancel').click();await expect(page.locator('#update-confirm')).toBeHidden();
 await page.locator('#update-install').click();await page.locator('#update-confirm-install').click();
 expect(await page.evaluate(()=>window.__layoutCalls.find(call=>call.command==='install_update').args.version)).toBe('2.0.0');
 audit=await new AxeBuilder({page}).analyze();expect(audit.violations.filter(v=>['critical','serious'].includes(v.impact))).toEqual([]);
 await page.keyboard.press('Escape');await expect(page.locator('#settings-panel')).toBeHidden();await expect(page.locator('#settings-open')).toBeFocused();
 expect(errors).toEqual([]);console.log('Rendering only: compact layout, keyboard focus, settings draft preservation, safe intent and accessibility passed. Native evidence is separate.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
