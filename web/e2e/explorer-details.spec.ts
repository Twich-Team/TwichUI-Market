import {test,expect,Page} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
const output='../artifacts/explorer-details/screenshots';
async function signIn(page:Page,path='/?market=1'){
 await page.goto(path);await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('synthetic browser owner password');await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page.getByRole('button',{name:'Sign out',exact:true})).toBeVisible();
}
async function capture(page:Page,name:string){fs.mkdirSync(output,{recursive:true});await page.screenshot({path:`${output}/${name}.png`,fullPage:true});}
async function accessible(page:Page,name:string){const a=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();fs.mkdirSync('../artifacts/explorer-details/accessibility',{recursive:true});fs.writeFileSync(`../artifacts/explorer-details/accessibility/${name}.json`,JSON.stringify(a.violations,null,2));expect(a.violations).toEqual([]);}
async function exact(page:Page,item=12363,market=1){const r=await page.request.get(`/api/v1/markets/${market}/catalogue/${item}/variants`);expect(r.status()).toBe(200);return (await r.json()).variants[0].variant_key as string;}
test('a stalled search ends with an actionable error and Retry can reach an empty result',async({page})=>{
 await signIn(page);
 const table=page.getByRole('region',{name:'Item catalogue',exact:true});
 await expect(table.getByRole('link',{name:/^Research /}).first()).toBeVisible();
 let release!:()=>void;const gate=new Promise<void>(resolve=>{release=resolve;});let attempts=0;
 await page.route('**/api/v1/markets/*/catalogue?**',async route=>{
  if(new URL(route.request().url()).searchParams.get('q')==='timeout-query'){
   attempts++;await gate;await route.abort();
  }else await route.continue();
 });
 await page.clock.install();
 await page.getByLabel('Search items',{exact:true}).fill('timeout-query');
 await page.getByRole('button',{name:'Search',exact:true}).click();
 await expect.poll(()=>attempts).toBe(1);
 await page.clock.fastForward(15_100);
 await expect(page.getByRole('alert')).toContainText('Try an item ID or a narrower search');
 await expect(table.locator('.catalogue-scroll')).not.toHaveClass(/catalogue-loading/);
 await expect(table.getByRole('link',{name:/^Research /})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Sign out',exact:true})).toBeVisible();
 expect(attempts).toBe(1);release();await page.unrouteAll({behavior:'wait'});
 await table.getByRole('button',{name:'Retry catalogue',exact:true}).click();
 await expect(table.getByText('No matching current items. Try an item ID or another search.',{exact:true})).toBeVisible();
 await expect(page.getByRole('alert')).toHaveCount(0);
});
test('Explorer stays browse-only and Back restores URL controls, expansion, focus and page clamping',async({page,context})=>{
 test.setTimeout(60000);const researchRequests:string[]=[];page.on('request',r=>{if(/\/items\/\d+\/[a-f0-9]{64}|\/distribution\//.test(r.url()))researchRequests.push(r.url());});
 await page.setViewportSize({width:1440,height:1000});await signIn(page,'/?market=1&sort=item_id&direction=asc&page=1&page_size=25');
 const table=page.getByRole('region',{name:'Item catalogue',exact:true});await expect(table.getByRole('status',{name:'Catalogue page'})).toHaveText('Page 2 of 2');await expect(page.getByRole('heading',{name:'Price history',exact:true})).toHaveCount(0);expect(researchRequests).toEqual([]);expect(await page.evaluate(()=>performance.getEntriesByType('resource').some(r=>r.name.includes('chart-engine')))).toBe(false);
 await capture(page,'explorer-normal');const saved=page.url();const link=table.getByRole('link',{name:/Research/}).last(),href=await link.getAttribute('href');const label=await link.getAttribute('aria-label');
 await link.scrollIntoViewIfNeeded();const scroll=await page.evaluate(()=>scrollY);await link.click();await expect(page).toHaveURL(new URL(href!,page.url()).href);await expect(page.getByRole('heading',{name:'Item metadata',exact:true})).toBeVisible();await page.goBack();await expect(page).toHaveURL(saved);await expect(table.getByRole('status',{name:'Catalogue page'})).toHaveText('Page 2 of 2');await expect(table.getByRole('link',{name:label!,exact:true})).toBeFocused();await expect.poll(async()=>Math.abs((await page.evaluate(()=>scrollY))-scroll)).toBeLessThan(80);
 await page.goForward();await expect(page).toHaveURL(new URL(href!,page.url()).href);await page.getByRole('link',{name:'← Back to Explorer',exact:true}).click();await expect(page).toHaveURL(saved);
 await page.getByLabel('Search items',{exact:true}).fill('Synthetic');await page.getByRole('button',{name:'Search',exact:true}).click();await table.getByRole('button',{name:/Supply/}).click();await table.getByLabel('Items per page').selectOption('50');await expect(page).toHaveURL(/page_size=50/);await expect(table.locator('tbody>tr')).toHaveCount(8);await capture(page,'explorer-search-filters');await accessible(page,'explorer');
 const blade=table.locator('.catalogue-table > tbody > tr').filter({has:page.getByRole('link',{name:'Research Synthetic Enchanted Blade',exact:true})});await blade.getByRole('button',{name:/2 variants/}).click();await expect(page.getByRole('table',{name:'Variants of Synthetic Enchanted Blade'})).toBeVisible();
 const origin=page.url();await blade.getByRole('link',{name:'Research Synthetic Enchanted Blade',exact:true}).click();await expect(page.getByRole('heading',{name:'Synthetic Enchanted Blade',exact:true})).toBeVisible();await expect(page.getByLabel('Variant ranges and total supply')).toContainText('5 units');await expect(page.getByRole('heading',{name:'Price history',exact:true})).toHaveCount(0);await capture(page,'details-multiple-variants');
 await page.goBack();await expect(page).toHaveURL(origin);await expect(page.getByRole('table',{name:'Variants of Synthetic Enchanted Blade'})).toBeVisible();await expect(page.getByLabel('Search items',{exact:true})).toHaveValue('Synthetic');
 const variantLink=page.getByRole('table',{name:'Variants of Synthetic Enchanted Blade'}).getByRole('link',{name:/Inspect Synthetic Enchanted Blade:/}).first();
 await variantLink.click();await expect(page.getByLabel('Exact variant current market')).toBeVisible();
 await page.goBack();await expect(page).toHaveURL(origin);await expect(variantLink).toBeFocused();
 const fresh=await context.newPage();await fresh.goto(new URL(href!,page.url()).href);await expect(fresh.getByRole('heading',{name:'Item metadata',exact:true})).toBeVisible();await fresh.close();
 await page.goto('/?market=1&page=999&page_size=25&sort=item_id&direction=asc');await expect(page.getByText('The live results changed.',{exact:false})).toBeVisible();await expect(page.getByRole('region',{name:'Item catalogue',exact:true}).getByRole('status',{name:'Catalogue page'}).filter({hasText:'Page 2'})).toBeVisible();await page.reload();await expect(page).toHaveURL(/page=1&/);
});
test('deep links authenticate independently and exact variants preserve prices, charts, provenance and mobile layouts',async({page})=>{
 test.setTimeout(60000);await signIn(page);const variant=await exact(page);await page.getByRole('button',{name:'Sign out',exact:true}).click();
 const path=`/markets/1/items/12363?variant=${variant}`;await signIn(page,path);await expect(page).toHaveURL(new RegExp(path.replace('?','\\?')));await expect(page.getByRole('heading',{name:'Synthetic Arcane Crystal',exact:true})).toBeVisible();
 await expect(page.getByLabel('Exact variant current market')).toContainText('10 units');await expect(page.getByLabel('Exact variant current market')).toContainText('50');await expect(page.getByRole('region',{name:'Item metadata',exact:true})).toContainText('+10 Fixture Strength');
 await expect(page.getByRole('heading',{name:'Synthetic Arcane Crystal',exact:true}).locator('.item-name')).toHaveCSS('color','rgb(30, 255, 0)');
 await page.locator('.chart-viewport').first().scrollIntoViewIfNeeded();await expect(page.getByRole('img',{name:'Observed asking-price history',exact:true})).toBeVisible();
 await page.getByRole('img',{name:'Observed asking-price history',exact:true}).locator('canvas').first().waitFor();
 const zoomWidth = await page.evaluate(() => {
   document.documentElement.style.zoom = '2';
   const width = { viewport: innerWidth, scroll: document.documentElement.scrollWidth };
   document.documentElement.style.zoom = '';
   return width;
 });
 expect(zoomWidth.scroll).toBeLessThanOrEqual(zoomWidth.viewport);
 await expect(page.getByRole('region',{name:'Supply information',exact:true})).toContainText('10 units at');await capture(page,'details-price-supply-charts');await accessible(page,'details');
 await page.getByRole('region',{name:'Current auctions',exact:true}).scrollIntoViewIfNeeded();await expect(page.getByRole('table',{name:'current listings',exact:true})).toContainText('10');await capture(page,'details-current-auctions');
 await page.getByRole('button',{name:'60D',exact:true}).click();await expect(page).toHaveURL(/days=60/);await page.reload();await expect(page.getByRole('button',{name:'60D',exact:true})).toHaveAttribute('aria-pressed','true');
 await page.setViewportSize({width:390,height:844});await capture(page,'details-mobile');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await accessible(page,'details-mobile');
 await page.goto(`/markets/2/items/12363?variant=${variant}`);await expect(page.getByLabel('Exact variant current market')).toContainText('20 units');await expect(page.getByText('Synthetic Horde',{exact:true}).first()).toBeVisible();
});
test('unknown routes, missing markets, disappeared variants and metadata failures stay honest',async({page})=>{
 await signIn(page,'/markets/1/items/20003');const common=await exact(page,20003);await page.goto('/markets/1/items/20003?variant='+common);await expect(page.getByRole('heading',{name:'Synthetic Common Item',exact:true})).toBeVisible();await capture(page,'details-common');
 const epic=await exact(page,20004);await page.goto('/markets/1/items/20004?variant='+epic);await expect(page.getByRole('heading',{name:'Synthetic Epic Item',exact:true}).locator('.item-name')).toHaveCSS('color','rgb(163, 53, 238)');await capture(page,'details-epic');
 for(const path of ['/markets/0/items/25','/markets/1/items/name','/markets/1/items/25?variant=bad','/not-a-page']){await page.goto(path);await expect(page.getByRole('heading',{name:'Page not found',exact:true})).toBeVisible();}
 await page.goto('/markets/999/items/25');await expect(page.getByRole('heading',{name:'Market unavailable',exact:true})).toBeVisible();await expect(page).toHaveURL(/markets\/999/);
 await page.goto('/markets/1/items/299999?variant='+'f'.repeat(64));await expect(page.getByText('This exact variant is not currently listed',{exact:false})).toBeVisible();await expect(page.getByRole('region',{name:'Item metadata',exact:true})).toContainText('Missing facts are not guessed');await capture(page,'details-missing-metadata-history');await accessible(page,'missing-details');
 await page.route('**/item-profiles/12363',r=>r.fulfill({status:503,contentType:'application/json',body:'{"detail":"Synthetic metadata outage"}'}));await page.goto('/markets/1/items/12363');await expect(page.getByRole('button',{name:'Retry metadata',exact:true})).toBeVisible();await expect(page.getByLabel('Exact variant current market')).toContainText('10 units');await page.unroute('**/item-profiles/12363');await page.getByRole('button',{name:'Retry metadata',exact:true}).click();await expect(page.getByRole('region',{name:'Item metadata',exact:true})).toContainText('+10 Fixture Strength');
});
test('Deal Finder opens the common item destination and restores its own applied filters',async({page})=>{
 await signIn(page,'/deals?market=1&mode=listings&change=15&spend=500&coverage=1&confidence=limited&direction=any');await expect(page.getByRole('heading',{name:'Deal Finder',exact:true})).toBeVisible();
 await page.getByLabel('Maximum spend (gold)',{exact:true}).fill('300');await page.getByRole('button',{name:'Apply filters',exact:true}).click();const origin=page.url();
 await page.getByRole('link',{name:'Inspect item ↗',exact:true}).first().click();await expect(page).toHaveURL(/\/markets\/1\/items\/\d+\?variant=[a-f0-9]{64}/);await capture(page,'deal-finder-to-details');await page.getByRole('link',{name:'← Back to Deal Finder',exact:true}).click();await expect(page).toHaveURL(origin);await expect(page.getByLabel('Maximum spend (gold)',{exact:true})).toHaveValue('300');await page.reload();await expect(page.getByLabel('Maximum spend (gold)',{exact:true})).toHaveValue('300');
});
test('variant switches replace the canonical URL and keep exact quantities and prices separate',async({page})=>{
 await signIn(page,'/?market=1&q=20000&sort=item_id&direction=asc&page=0&page_size=25');await page.getByRole('link',{name:'Research Synthetic Enchanted Blade',exact:true}).click();
 const variants=page.getByRole('table',{name:'Variants of Synthetic Enchanted Blade',exact:true});const links=variants.getByRole('link',{name:/Inspect Synthetic Enchanted Blade:/});await expect(links).toHaveCount(2);
 const all=(await(await page.request.get('/api/v1/markets/1/catalogue/20000/variants')).json()).variants;
 const first=`/markets/1/items/20000?variant=${all.find((v:any)=>v.supply===2).variant_key}`,second=`/markets/1/items/20000?variant=${all.find((v:any)=>v.supply===3).variant_key}`;expect(first).not.toBe(second);
 await variants.locator(`a[href="${first}"]`).click();await expect(page).toHaveURL(new RegExp(first.replace('?','\\?')));await expect(page.getByLabel('Exact variant current market')).toContainText('2 units');await expect(page.getByLabel('Exact variant current market')).toContainText('2g');
 await page.getByRole('button',{name:'60D',exact:true}).click();await page.getByText('2 variants · Change variant',{exact:true}).click();await variants.locator(`a[href^="${second}"]`).click();await expect(page).toHaveURL(new RegExp(second.replace('?','\\?')));await expect(page.getByLabel('Exact variant current market')).toContainText('3 units');await expect(page.getByLabel('Exact variant current market')).toContainText('3g');await expect(page).toHaveURL(/days=60/);await expect(page).toHaveTitle(/Synthetic Enchanted Blade/);await expect(variants.locator(`a[href^="${second}"]`)).toHaveAttribute('aria-current','page');await accessible(page,'rare-exact');await capture(page,'details-rare-exact');
 await page.goBack();await expect(page.getByRole('heading',{name:'Market Explorer',exact:true})).toBeVisible();await expect(page.getByLabel('Search items',{exact:true})).toHaveValue('20000');
});
test('independent research errors remain retryable while metadata and exact identity stay visible',async({page})=>{
 await signIn(page);const variant=await exact(page);const path=`/markets/1/items/12363?variant=${variant}`;
 const history='**/items/12363/*/history?*',supply='**/distribution/12363/*',auctions='**/items/12363/*/listings?*';
 for(const pattern of [history,supply,auctions])await page.route(pattern,r=>r.fulfill({status:503,contentType:'application/json',body:'{"detail":"Synthetic research outage"}'}));
 await page.goto(path);for(const name of ['Retry price history','Retry supply distribution','Retry current auctions'])await expect(page.getByRole('button',{name,exact:true})).toBeVisible();
 await expect(page.getByRole('region',{name:'Item metadata',exact:true})).toContainText('+10 Fixture Strength');await expect(page.getByRole('heading',{name:'Synthetic Arcane Crystal',exact:true})).toBeVisible();
 for(const pattern of [history,supply,auctions])await page.unroute(pattern);
 for(const name of ['Retry price history','Retry supply distribution','Retry current auctions'])await page.getByRole('button',{name,exact:true}).click();await expect(page.getByRole('table',{name:'current listings',exact:true})).toContainText('10');
 await expect(page.getByRole('button',{name:'Retry price history',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'Retry supply distribution',exact:true})).toHaveCount(0);
});
test('bounded isolated browser measurements retain lazy charts and cached return navigation',async({browser})=>{
 test.setTimeout(60000);const runs=[];
 for(let index=0;index<3;index++){
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();let catalogueRequests=0;page.on('request',r=>{if(/\/catalogue\?/.test(r.url()))catalogueRequests++;});
  const start=Date.now();await signIn(page,'/?market=1&q=12363&sort=item_id&direction=asc&page=0&page_size=25');const catalogue=page.getByRole('region',{name:'Item catalogue',exact:true});await expect(catalogue.getByRole('link',{name:'Research Synthetic Arcane Crystal',exact:true})).toBeVisible();const signedInCatalogueMs=Date.now()-start;
  const resources=await page.evaluate(()=>performance.getEntriesByType('resource').map(r=>({url:r.name,bytes:(r as PerformanceResourceTiming).encodedBodySize})));expect(resources.some(r=>r.url.includes('chart-engine'))).toBe(false);
  const details=Date.now();await catalogue.getByRole('link',{name:'Research Synthetic Arcane Crystal',exact:true}).click();await expect(page.getByLabel('Exact variant current market')).toContainText('10 units');const detailsMs=Date.now()-details;
  const before=catalogueRequests,back=Date.now();await page.getByRole('link',{name:'← Back to Explorer',exact:true}).click();await expect(catalogue.getByRole('link',{name:'Research Synthetic Arcane Crystal',exact:true})).toBeVisible();const backMs=Date.now()-back;
  const renderedRows=await catalogue.locator('tbody>tr').count();expect(renderedRows).toBeLessThanOrEqual(25);runs.push({signed_in_catalogue_including_login_ms:signedInCatalogueMs,parent_and_exact_navigation_ms:detailsMs,back_ms:backMs,catalogue_requests_on_return:catalogueRequests-before,rendered_rows:renderedRows,initial_js_encoded_bytes:resources.filter(r=>/\.js$/.test(r.url)).reduce((a,r)=>a+r.bytes,0),echarts_requested_by_explorer:false});await context.close();
 }
 fs.mkdirSync('../artifacts/explorer-details',{recursive:true});fs.writeFileSync('../artifacts/explorer-details/performance.json',JSON.stringify({synthetic:true,scope:'Isolated rootless browser, one CPU; three contexts. Includes real fixture API/auth requests. Not production p95 or a before/after speedup claim.',runs},null,2));
});
test('direct research retains supplemental attribution and neutral unknown quality',async({page})=>{
 await signIn(page,'/markets/1/items/20001');await expect(page.getByRole('heading',{name:'Synthetic Recovered Gloves',exact:true})).toBeVisible();
 await page.getByRole('heading',{name:'Item metadata',exact:true}).click();
 await expect(page.getByRole('link',{name:'Data from Everloot, CC BY-SA 4.0',exact:true}).first()).toHaveAttribute('href','https://everloot.app');
 await page.getByRole('region',{name:'Item metadata',exact:true}).getByText('Technical details',{exact:true}).click();await expect(page.getByRole('region',{name:'Item metadata',exact:true})).toContainText('everloot');await expect(page.getByRole('heading',{name:'Synthetic Recovered Gloves',exact:true}).locator('.item-name')).toHaveCSS('color','rgb(214, 208, 196)');
});
test('a disappeared exact variant keeps its URL and retained historical chart without substituting a current sibling',async({page})=>{
 await signIn(page);const response=await page.request.get('/api/v1/markets/1/catalogue/20000/variants'),data=await response.json(),gone=data.variants[0],remaining=data.variants[1];
 const original=await(await page.request.get(`/api/v1/markets/1/items/20000/${gone.variant_key}`)).json();
 // Explicit synthetic response transition: no database/history is modified.
 await page.route(`**/api/v1/markets/1/items/20000/${gone.variant_key}`,r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({...original,listings:[],valuation:{...original.valuation,lowest_buyout:null,recent_price:null,supply:0,priced_supply:0,listing_count:0}})}));
 await page.route('**/catalogue/20000/variants?*',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({...data,variants:[remaining],total_variants:1})}));
 await page.route(`**/items/20000/${gone.variant_key}/listings?*`,r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({listings:[],total:0,snapshot_id:data.snapshot_id})}));
 await page.goto(`/markets/1/items/20000?variant=${gone.variant_key}`);await expect(page.getByText('This exact variant is not currently listed',{exact:false})).toBeVisible();await expect(page).toHaveURL(new RegExp(gone.variant_key));
 await page.locator('.chart-viewport').first().scrollIntoViewIfNeeded();await expect(page.getByRole('img',{name:'Observed asking-price history',exact:true})).toBeVisible();await expect(page.getByLabel('Exact variant current market')).toContainText('0 units');
});

test('Explorer keeps source age in the heading and search directly above results', async ({page}) => {
 const staleSource = new Date(Date.now() - 6 * 3_600_000).toUTCString();
 const newSource = new Date(Date.now() - 60_000).toUTCString();
 const checks = ["2026-11-22T10:00:00Z", "2026-11-22T11:00:00Z", "2026-11-22T12:00:00Z"];
 let refreshed = 0;
 await page.route("**/api/v1/markets/1/catalogue?*", async (route) => {
  const response = await route.fetch();
  if (!response.ok()) return route.fulfill({response});
  const data = await response.json();
  const index = Math.min(2, refreshed++);
  await route.fulfill({json: {...data, market: {...data.market, last_modified: index === 2 ? newSource : staleSource, last_success: checks[index]}}});
 });
 await signIn(page);
 const source = page.locator(".explorer-heading time");
 await expect(source).toHaveText("Source updated 6 hours ago");
 await expect(source).toHaveAttribute("datetime", new Date(staleSource).toISOString());
 await expect(page.getByText("Timing", {exact:true})).toHaveCount(0);
 await expect(page.getByText(/Prices may have changed since the last source update/)).toHaveCount(0);
 for (const width of [1280, 390]) {
  await page.setViewportSize({width, height:900});
  const results = width === 390 ? ".mobile-catalogue" : ".catalogue-scroll";
  await expect(page.locator(`.explorer-search + ${results}`)).toBeVisible();
 }
 const refresh = page.getByRole("button", {name:"Refresh catalogue"});
 await refresh.click();
 await expect.poll(() => refreshed).toBe(2);
 await expect(refresh).toBeEnabled();
 await expect(source).toHaveAttribute("datetime", new Date(staleSource).toISOString());
 await refresh.click();
 await expect(source).toHaveText("Source updated 1 minute ago");
 await expect(source).toHaveAttribute("datetime", new Date(newSource).toISOString());
});
