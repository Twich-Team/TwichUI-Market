// Focused rendering/intent proof with mocked IPC. Native HTTP and Windows tests
// independently verify actual production components; this does not install them.
const {chromium,expect}=require('@playwright/test');
const AxeBuilder=require('@axe-core/playwright').default;
const path=require('node:path');const fs=require('node:fs');const http=require('node:http');
(async()=>{
 const root=path.resolve(__dirname,'../../desktop/ui');
 const server=http.createServer((req,res)=>{const name=({'/':'index.html','/app.js':'app.js','/style.css':'style.css','/icon.png':'icon.png'})[req.url];if(!name){res.writeHead(404).end();return;}res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.png')?'image/png':'text/html');res.end(fs.readFileSync(path.join(root,name)));});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH||undefined});
 try{
 const context=await browser.newContext({viewport:{width:520,height:850}});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{
  const settings={schema_version:1,server:'https://fixture.invalid/',selected_market:2,automatic_sync:false,interval_minutes:30,close_to_tray:true};
  window.__state={version:'L2 synthetic UI',settings,mode:'companion',connected:true,account:{id:1,username:'Synthetic'},bootstrap:{account:{id:1},markets:[{id:2,label:'US — Normal — Horde',available_for_sync:true}],suggested_market_id:2},
   sync:{revision:1,sync:{phase:'ready',running:false,selected_market:2,automatic_sync:false}},cache:{has_completed_cache:true,item_count:2},settings_valid:true};
  window.__calls=[];const callbacks={};window.__emit=(v)=>callbacks['companion-state']?.({payload:v});
  window.__TAURI__={core:{invoke:async(command,args)=>{
   window.__calls.push({command,args});
   if(command==='app_state')return window.__state;
   if(command==='update_state')return {status:'idle',message:'Synthetic updates disabled'};
   if(command==='archive_workshop'){
    if(args.publish&&!args.compatible)throw new Error('Acknowledge schema-3 testing compatibility before publication');
    if(window.__refuse)throw new Error('Delivery exceeds canonical_bytes: 2500000 exceeds 2097152; previous data is preserved');
    if(window.__switch){window.__state=structuredClone(window.__state);window.__state.bootstrap.account.id=2;window.__state.account.id=2;}
    return {header:{market:{region:'us',house_id:114},pricing_algorithm:'twichui-pricing-v1',total_observations:2,checkpoint_id:'c'.repeat(64),generated_at:'2026-11-16T12:00:00Z'},archive_bytes:1048576,selection:null,
     sizes:{records:args.selected?.variants.length||0,canonical_bytes:12345,lua_bytes:20000,manifest_bytes:5000},generation_id:'d'.repeat(64),path:args.publish?'C:\\Companion\\workshop-testing\\fixture\\TwichUI_MarketData\\Data.lua':null};
   }
   throw new Error('Unexpected mocked command '+command);
  }},event:{listen:async(name,callback)=>{callbacks[name]=callback;return()=>{};}}};
 });
 await page.goto('http://127.0.0.1:'+server.address().port);
 await expect(page.locator('#account-name')).toHaveText('Synthetic');
 expect(await page.evaluate(()=>window.__calls.filter(c=>c.command==='archive_workshop').length)).toBe(0);
 // Preserve the installed-client legacy selector's unique existing More actions.
 await expect(page.locator('.more summary')).toHaveCount(1);await expect(page.locator('.advanced summary')).toHaveCount(1);
 await page.locator('#history-panel summary').click();await page.locator('#archive-sync').click();
 await expect(page.locator('#archive-status')).toContainText('Checkpoint '+ 'c'.repeat(64));
 await expect(page.locator('#scope-through')).toHaveValue('2026-11-16');await expect(page.locator('#scope-from')).toHaveValue('2026-09-18');
 await page.locator('#scope-variants').fill('2589 '+ 'a'.repeat(64));
 await page.locator('#scope-preview').click();await expect(page.locator('#scope-status')).toContainText('exact data 12,345 bytes');
 let calls=await page.evaluate(()=>window.__calls.filter(c=>c.command==='archive_workshop'));expect(calls.at(-1).args.publish).toBe(false);expect(calls.at(-1).args.diskBudgetMib).toBe(4096);
 await page.locator('#scope-export').click();await expect(page.locator('#message')).toContainText('Acknowledge schema-3');
 await page.locator('#scope-compatible').check();await page.locator('#scope-export').click();
 await expect(page.locator('#scope-status')).toContainText('Exported to C:\\Companion\\workshop-testing');
 await expect(page.locator('#scope-status')).toContainText('No game files were installed or loaded');await expect(page.locator('#message')).toBeHidden();
 await page.evaluate(()=>window.__refuse=true);await page.locator('#scope-preview').click();await expect(page.locator('#message')).toContainText('previous data is preserved');
 await page.evaluate(()=>window.__refuse=false);await page.locator('#scope-variants').fill('2589 incomplete-key');
 const before=await page.evaluate(()=>window.__calls.length);await page.locator('#scope-preview').click();await expect(page.locator('#message')).toContainText('full exact variant key');
 expect(await page.evaluate(()=>window.__calls.length)).toBe(before);
 await page.locator('#scope-variants').fill('2589 '+ 'a'.repeat(64));
 const folder=process.env.MARKET_ARCHIVE_UI_EVIDENCE||path.resolve('artifacts/companion-v2');fs.mkdirSync(folder,{recursive:true});
 await page.screenshot({path:path.join(folder,'archive-manual-controls.png'),fullPage:true});
 const audit=await new AxeBuilder({page}).analyze();expect(audit.violations.filter(v=>['critical','serious'].includes(v.impact))).toEqual([]);
 await page.evaluate(()=>window.__switch=true);await page.locator('#scope-preview').click();
 await expect(page.locator('#archive-status')).toHaveText('No completed archive selected.');
 await expect(page.locator('#scope-variants')).toHaveValue('');await expect(page.locator('#scope-compatible')).not.toBeChecked();
 await page.setViewportSize({width:440,height:560});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 expect(errors).toEqual([]);console.log('PASS mocked IPC: explicit sync, exact selection, preview/publication warning, refusal, account-switch clearing, accessibility; no native/client acceptance claimed');
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1;});
