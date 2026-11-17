// Run after isolated fixtures; no production endpoint or write is used.
const {chromium}=require('playwright');const fs=require('node:fs');
(async()=>{
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH});
const context=await browser.newContext({viewport:{width:390,height:844}});const page=await context.newPage();
await page.goto('http://127.0.0.1:5173');await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('synthetic browser owner password');await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.getByRole('heading',{name:'Market Explorer',exact:true}).waitFor();
const out=require('node:path').resolve(__dirname,'../../artifacts/mobile-experience');fs.mkdirSync(out,{recursive:true});
for(const [phase,port] of [['before',5176],['after',5173]].filter(([phase])=>!process.env.PHASE || phase===process.env.PHASE)){
 for(const width of [320,344,390,768,1440]){
 await page.setViewportSize({width,height:900});
 for(const path of ['/?market=1','/deals','/account','/companion','/administration','/markets/1/items/20000']){
 await page.goto(`http://127.0.0.1:${port}${path}`);await page.locator('main h1').waitFor();await page.waitForTimeout(250);
 const name=path.startsWith('/?')?'explorer':path.includes('/items/')?'item-overview':path.slice(1);
 await page.screenshot({path:`${out}/${phase}-${name}-${width}.png`,fullPage:true});
 if(path==='/administration'){
 const tabs=page.getByRole('tab');const section=page.getByRole('combobox',{name:'Administration section',exact:true});const mobile=await section.isVisible();const count=mobile ? await section.locator('option').count() : await tabs.count();for(let i=0;i<count;i++){if(mobile)await section.selectOption({index:i});else await tabs.nth(i).click();await page.waitForTimeout(200);await page.screenshot({path:`${out}/${phase}-admin-${i}-${width}.png`,fullPage:true});}
 }
 }
 }
}
const metrics=[];
for(const phase of ['before','after'])for(let i=0;i<3;i++){
 const ctx=await browser.newContext({storageState:await context.storageState(),viewport:{width:390,height:844}});const p=await ctx.newPage();let requests=0;
 p.on('request',r=>{if(/\/catalogue\?/.test(r.url()))requests++;});
 await p.addInitScript(()=>{window.mobileCLS=0;new PerformanceObserver(list=>{for(const e of list.getEntries())if(!e.hadRecentInput)window.mobileCLS+=e.value;}).observe({type:'layout-shift',buffered:true});});
 const start=Date.now();await p.goto(`http://127.0.0.1:${phase==='before'?5176:5173}/?market=1&q=`);await p.locator(phase==='before'?'.catalogue-table tbody > tr':'.mobile-item').first().waitFor();const first=Date.now()-start;
 const searchStart=Date.now();await p.getByLabel('Search items',{exact:true}).fill('Crystal');const reply=p.waitForResponse(r=>r.url().includes('/catalogue?')&&r.url().includes('Crystal'));await p.getByRole('button',{name:'Search',exact:true}).click();await reply;
 metrics.push({phase,catalogueReadyMs:first,searchResponseMs:Date.now()-searchStart,catalogueRequests:requests,...await p.evaluate(()=>({cls:window.mobileCLS,heapBytes:performance.memory?.usedJSHeapSize,domNodes:document.querySelectorAll('*').length}))});await ctx.close();
}
fs.writeFileSync(`${out}/performance.json`,JSON.stringify({fixture:true,network:'local loopback; not cellular or real device',samples:metrics},null,2));await browser.close();
})();
