import {test,expect,Page} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
const secret='synthetic preferences password';
async function login(page:Page,name:string) {
 await page.goto('/');await page.getByLabel('Username',{exact:true}).fill(name);
 await page.getByLabel('Password',{exact:true}).fill(secret);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Market Explorer',exact:true})).toBeVisible();
 await expect(market(page)).toBeEnabled();
}
const market=(page:Page)=>page.locator('select').filter({has:page.locator('option[value="2"]')}).first();
const read=async(page:Page)=>(await page.request.get('/api/v1/me/preferences')).json();
async function saved(page:Page,values:Record<string,unknown>) {
 await expect.poll(async()=>(await read(page)).values).toMatchObject(values);
 await expect(page.getByText('Saving preferences…',{exact:true})).toHaveCount(0);
}
async function account(page:Page) {
 await page.getByRole('button',{name:'Account & devices',exact:true}).click();
 return page.getByRole('region',{name:'My Preferences',exact:true});
}
async function signOut(page:Page) {
 await page.getByRole('button',{name:'Sign out',exact:true}).click();
 await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
}

test('preferences auto-save every supported choice and restore across independent sessions and devices',async({page,browser})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await login(page,'prefs_persistence');
 const schedules=(await(await page.request.get('/api/v1/markets')).json()).markets.map((m:any)=>({id:m.id,enabled:m.enabled,interval_seconds:m.interval_seconds}));
 await market(page).selectOption('2');
 const catalogue=page.getByRole('region',{name:'Item catalogue',exact:true});
 await expect(catalogue.locator('tbody tr').first()).toBeVisible();
 await catalogue.getByLabel('Items per page').selectOption('50');
 await catalogue.getByText('Item columns',{exact:true}).click();
 await catalogue.getByLabel('Listings',{exact:true}).uncheck();
 await catalogue.getByRole('columnheader',{name:/Supply/}).getByRole('button').click();
 await catalogue.getByRole('columnheader',{name:/Supply/}).getByRole('button').click();
 await page.getByRole('button',{name:'60D',exact:true}).click();
 await saved(page,{market_id:2,explorer_days:60,item_page_size:50,item_columns:{listing_count:false},item_sort:{id:'supply',desc:true}});
 await page.getByRole('button',{name:'Deal Finder',exact:true}).click();
 await page.getByRole('tab',{name:'Below reference',exact:true}).click();
 await page.getByLabel('Maximum spend (gold)').fill('123.45');
 await page.getByRole('tab',{name:'Price changes',exact:true}).click();
 await page.getByLabel('Minimum change (%)').fill('30');
 await page.getByLabel('Minimum observed days').fill('5');
 await page.getByRole('combobox',{name:'Direction',exact:true}).selectOption('decrease');
 await page.getByRole('combobox',{name:'Evidence',exact:true}).selectOption('moderate');
 await saved(page,{deal_mode:'price',deal_change:30,deal_spend_gold:123.45,deal_coverage:5,deal_direction:'decrease',deal_confidence:'moderate'});
 const preferences=await account(page);
 await expect(preferences.getByLabel('Preferred market')).toHaveValue('2');
 await expect(preferences.getByLabel('Explorer chart range')).toHaveValue('60');
 await expect(preferences.getByLabel('Item table page size')).toHaveValue('50');
 const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();expect(axe.violations).toEqual([]);
 fs.mkdirSync('../artifacts/modernization',{recursive:true});
 await page.screenshot({path:'../artifacts/modernization/my-preferences-desktop.png',fullPage:true});
 const device=await browser.newContext();const other=await device.newPage();await login(other,'prefs_persistence');
 await expect(market(other)).toHaveValue('2');
 const otherTable=other.getByRole('region',{name:'Item catalogue',exact:true});
 await expect(otherTable.getByLabel('Items per page')).toHaveValue('50');
 await expect(otherTable.locator('th[aria-sort="descending"]')).toContainText('Supply');
 await expect(otherTable.getByRole('columnheader',{name:'Listings',exact:true})).toHaveCount(0);
 await expect(other.getByRole('button',{name:'60D',exact:true})).toHaveClass(/selected/);
 await other.getByRole('button',{name:'Deal Finder',exact:true}).click();
 await expect(other.getByRole('tab',{name:'Price changes',exact:true})).toHaveAttribute('aria-selected','true');
 await expect(other.getByLabel('Minimum change (%)')).toHaveValue('30');
 await expect(other.getByRole('combobox',{name:'Direction',exact:true})).toHaveValue('decrease');
 await other.reload();await expect(market(other)).toHaveValue('2');
 const after=(await(await page.request.get('/api/v1/markets')).json()).markets.map((m:any)=>({id:m.id,enabled:m.enabled,interval_seconds:m.interval_seconds}));
 expect(after).toEqual(schedules);expect(errors).toEqual([]);
 await device.close();
});

test('same-browser account switching and reset keep preferences private',async({page,browser})=>{
 await login(page,'prefs_isolation_a');await market(page).selectOption('2');
 let preferences=await account(page);await preferences.getByLabel('Explorer chart range').selectOption('365');
 await saved(page,{market_id:2,explorer_days:365});await signOut(page);
 await login(page,'prefs_isolation_b');await expect(market(page)).toHaveValue('1');
 expect((await read(page)).values.explorer_days).toBe(14);
 preferences=await account(page);await preferences.getByLabel('Item table page size').selectOption('100');
 await saved(page,{item_page_size:100});await signOut(page);
 await login(page,'prefs_isolation_a');await expect(market(page)).toHaveValue('2');
 preferences=await account(page);await expect(preferences.getByLabel('Explorer chart range')).toHaveValue('365');
 await expect(preferences.getByLabel('Item table page size')).toHaveValue('25');
 await preferences.getByRole('button',{name:'Reset my preferences',exact:true}).click();
 await saved(page,{market_id:null,explorer_days:14,item_page_size:25,deal_mode:'listings'});
 await page.reload();preferences=await account(page);
 await expect(preferences.getByLabel('Explorer chart range')).toHaveValue('14');
 const second=await browser.newContext();const secondPage=await second.newPage();await login(secondPage,'prefs_isolation_a');
 expect((await read(secondPage)).values.market_id).toBeNull();await second.close();
 await page.setViewportSize({width:390,height:844});
 await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:'../artifacts/modernization/my-preferences-mobile.png',fullPage:true});
});

test('unavailable preferred market falls back and returns without a destructive automatic save',async({page})=>{
 await login(page,'prefs_persistence');expect((await read(page)).values.market_id).toBe(2);
 let writes=0;page.on('request',r=>{if(r.url().endsWith('/me/preferences')&&r.method()==='PATCH')writes++;});
 await page.route('**/api/v1/markets',async route=>{
  const response=await route.fetch();const data=await response.json();
  await route.fulfill({response,json:{...data,markets:data.markets.filter((m:any)=>m.id===1)}});
 });
 await page.reload();await expect(page.getByText('Your preferred market is unavailable.',{exact:false})).toBeVisible();
 await expect(page.locator('select').filter({has:page.locator('option[value="1"]')}).first()).toHaveValue('1');
 expect((await read(page)).values.market_id).toBe(2);expect(writes).toBe(0);
 await page.unroute('**/api/v1/markets');await page.reload();await expect(market(page)).toHaveValue('2');
 expect(writes).toBe(0);
});

test('rapid choices, delayed acknowledgements, offline retry, and concurrent device updates preserve latest intent',async({page,context,browser})=>{
 await login(page,'prefs_resilience');
 let release!:()=>void;const barrier=new Promise<void>(resolve=>{release=resolve;});
 let observed!:()=>void;const sent=new Promise<void>(resolve=>{observed=resolve;});let first=true;
 await page.route('**/api/v1/me/preferences',async route=>{
  if(route.request().method()==='PATCH'&&first){first=false;const response=await route.fetch();observed();await barrier;await route.fulfill({response});}
  else await route.continue();
 });
 await market(page).selectOption('1');await sent;
 await market(page).selectOption('2');
 let preferences=await account(page);
 await preferences.getByLabel('Explorer chart range').selectOption('60');
 await preferences.getByLabel('Explorer chart range').selectOption('3650');
 await preferences.getByLabel('Item table page size').selectOption('100');
 release();await saved(page,{market_id:2,explorer_days:3650,item_page_size:100});await page.unroute('**/api/v1/me/preferences');
 await context.setOffline(true);
 await preferences.getByLabel('Item table page size').selectOption('50');
 await expect(page.getByText('Your choices are kept here.',{exact:false}).first()).toBeVisible();
 await expect(preferences.getByLabel('Item table page size')).toHaveValue('50');
 await context.setOffline(false);await saved(page,{item_page_size:50});
 // A separate device commits a different field before this device's next PATCH.
 const device=await browser.newContext();const other=await device.newPage();await login(other,'prefs_resilience');
 const session=await(await other.request.get('/api/v1/auth/session')).json();const previous=await read(other);
 expect((await other.request.patch('/api/v1/me/preferences',{headers:{'X-CSRF-Token':session.csrf_token},data:{schema_version:1,expected_revision:previous.revision,changes:{deal_mode:'supply'}}})).status()).toBe(200);
 await preferences.getByLabel('Explorer chart range').selectOption('7');
 await saved(page,{explorer_days:7,deal_mode:'supply',item_page_size:50,market_id:2});
 await page.reload();preferences=await account(page);
 await expect(preferences.getByLabel('Explorer chart range')).toHaveValue('7');
 await expect(preferences.getByLabel('Item table page size')).toHaveValue('50');await device.close();
});

test('a session changed in another tab cannot inject that account’s preferences into the old account',async({page,context})=>{
 await login(page,'prefs_isolation_a');
 const owner=(await read(page)).user_id;
 const other=await context.newPage();await other.goto('/');
 await expect(other.getByRole('heading',{name:'Market Explorer',exact:true})).toBeVisible();
 await signOut(other);await login(other,'prefs_isolation_b');
 expect((await read(other)).user_id).not.toBe(owner);
 const recheck=page.waitForResponse(r=>r.url().endsWith('/me/preferences')&&r.request().method()==='GET'&&r.status()===200);
 await page.bringToFront();
 // Visibility changes trigger the same focused-tab reconciliation used in the website.
 await page.evaluate(()=>window.dispatchEvent(new Event('visibilitychange')));
 await recheck;
 await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'My Preferences',exact:true})).toHaveCount(0);
 await other.close();
});

test('incomplete numeric filter drafts cannot poison automatic saves when changing modes',async({page})=>{
 await login(page,'prefs_resilience');
 await page.getByRole('button',{name:'Deal Finder',exact:true}).click();
 await page.getByRole('tab',{name:'Below reference',exact:true}).click();
 await page.getByLabel('Minimum discount (%)').fill('');
 await page.getByLabel('Minimum observed days').fill('');
 await page.getByRole('tab',{name:'Supply changes',exact:true}).click();
 await saved(page,{deal_mode:'supply',deal_change:1,deal_coverage:1});
 await expect(page.getByText('Preferences could not be saved.',{exact:false})).toHaveCount(0);
});
