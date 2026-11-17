import {test,expect,Page} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
const output=process.env.MOBILE_SCREENSHOT_DIR || '../artifacts/mobile-experience';
const widths=[320,344,360,375,390,430,600,768,1024,1440];
async function login(page:Page){await page.route('**/api/v1/markets',async route=>{const response=await route.fetch();const body=await response.json();body.markets=body.markets.map((market:object,index:number)=>index===0?{...market,label:'Synthetic market with an exceptionally long regional and faction description'}:market);await route.fulfill({response,json:body});});await page.goto('/?market=1');await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('synthetic browser owner password');await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page.getByRole('heading',{name:'Market Explorer',exact:true})).toBeVisible();}
async function overflow(page:Page){const wide=await page.evaluate(w=>[...document.querySelectorAll('main *')].filter(e=>e.getBoundingClientRect().right>w).slice(0,12).map(e=>({tag:e.tagName,cls:e.className,width:e.getBoundingClientRect().width})),page.viewportSize()!.width);expect(await page.evaluate(()=>({viewport:innerWidth,width:document.documentElement.scrollWidth})),JSON.stringify(wide)).toEqual({viewport:page.viewportSize()!.width,width:page.viewportSize()!.width});}
async function shot(page:Page,name:string){fs.mkdirSync(output,{recursive:true});await page.screenshot({path:`${output}/${name}.png`,fullPage:true});}
test('mobile shell and search geometry across viewport matrix',async({page})=>{
 await login(page);
 for(const width of widths){await page.setViewportSize({width,height:900});await overflow(page);
 const market=await page.getByRole('combobox',{name:'Market',exact:true}).boundingBox();const search=await page.getByRole('button',{name:'Search',exact:true}).boundingBox();expect(market).toBeTruthy();expect(search).toBeTruthy();expect(market!.x+market!.width<=search!.x || market!.y+market!.height<=search!.y).toBe(true);
 if(width<=800){await expect(page.getByRole('button',{name:'Menu',exact:true})).toBeVisible();await page.getByRole('button',{name:'Menu',exact:true}).click();await expect(page.getByRole('button',{name:'Administration',exact:true})).toBeVisible();await page.keyboard.press('Escape');await expect(page.getByRole('button',{name:'Menu',exact:true})).toBeFocused();}
 await shot(page,`after-explorer-${width}`);
 }
});
test('mobile catalogue variants sorting exact navigation and history',async({page})=>{
 await page.setViewportSize({width:344,height:820});await login(page);await expect(page.locator('.mobile-item').first()).toBeVisible();
 await page.getByRole('combobox',{name:'Sort items',exact:true}).selectOption('name');await expect(page).toHaveURL(/sort=name/);
 const expand=page.getByRole('button',{name:/Show \d+ exact variants/}).first();await expand.click();await expect(page.getByRole('link',{name:/Inspect .*:/}).first()).toBeVisible();await overflow(page);await shot(page,'after-variants-344');
 const link=page.getByRole('link',{name:/Inspect .*:/}).first();const destination=await link.getAttribute('href');await link.click();await expect(page).toHaveURL(new RegExp(destination!.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));await expect(page.getByRole('heading',{level:1})).toBeVisible();await overflow(page);await shot(page,'after-item-details-344');await page.goBack();await expect(page.getByRole('combobox',{name:'Sort items',exact:true})).toHaveValue('name');await expect(page.getByRole('button',{name:/Hide \d+ exact variants/}).first()).toBeVisible();
 await page.getByRole('button',{name:'Next items',exact:true}).scrollIntoViewIfNeeded();await shot(page,'after-pagination-344');
});
test('page and administration geometry review',async({page})=>{
 test.setTimeout(90000);
 await login(page);
 for(const width of [320,390,768,1440]){
 await page.setViewportSize({width,height:900});
 for(const route of ['/deals','/account','/companion','/administration']){await page.goto(route);await expect(page.getByRole('heading',{level:1})).toBeVisible();await page.waitForTimeout(350);await overflow(page);await shot(page,`after-${route.slice(1)}-${width}`);}
 const tabs=page.getByRole('tab');const section=page.getByRole('combobox',{name:'Administration section',exact:true});const count=width<=700 ? await section.locator('option').count() : await tabs.count();
 for(let i=0;i<count;i++){if(width<=700)await section.selectOption({index:i});else await tabs.nth(i).click();await page.waitForTimeout(150);await overflow(page);await shot(page,`after-admin-${i}-${width}`);}
 }
 await page.setViewportSize({width:390,height:844});await page.goto('/account');expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations).toEqual([]);
});
test('touch disclosure long records delayed search enlarged text and loading stability',async({page})=>{
 await page.setViewportSize({width:320,height:740});await page.emulateMedia({reducedMotion:'reduce'});await login(page);
 await page.route('**/api/v1/markets/*/catalogue?**',async route=>{const response=await route.fetch();const body=await response.json();body.items=body.items.map((item:object)=>({...item,name:'Synthetic extraordinarily long item name with an unusually extensive descriptive suffix',icon_url:'/api/v1/missing-fixture-icon'}));await new Promise(r=>setTimeout(r,300));await route.fulfill({response,json:body});});
 await page.getByLabel('Search items',{exact:true}).fill('Synthetic');await page.getByLabel('Search items',{exact:true}).press('Enter');await expect(page.locator('.mobile-item').first()).toContainText('extraordinarily');await overflow(page);
 await page.addStyleTag({content:':root{font-size:28px}'});await overflow(page);await shot(page,'after-text-200-percent-320');
 await page.getByRole('button',{name:'Menu',exact:true}).click();await expect(page.getByRole('button',{name:'Account & devices',exact:true})).toBeVisible();await page.getByRole('button',{name:'Account & devices',exact:true}).click();await expect(page.getByRole('button',{name:'Menu',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Sign out',exact:true})).not.toBeVisible();await overflow(page);
});
test('landscape phone navigation remains reachable without a fixed short sidebar',async({page})=>{
 await login(page);
 for(const viewport of [{width:844,height:390},{width:932,height:430},{width:600,height:320}]){
  await page.setViewportSize(viewport);await overflow(page);await page.getByRole('button',{name:'Menu',exact:true}).click();
  const logout=page.getByRole('button',{name:'Sign out',exact:true});await logout.scrollIntoViewIfNeeded();await expect(logout).toBeVisible();await overflow(page);await page.keyboard.press('Escape');await expect(page.getByRole('button',{name:'Menu',exact:true})).toBeFocused();
 }
});
test('pending environment discovery never flashes a large incorrect preview banner',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 let finish!:()=>void;const gate=new Promise<void>(resolve=>{finish=resolve;});
 await page.route('**/api/v1/environment',async route=>{await gate;await route.continue();});
 await login(page);const title=page.getByRole('heading',{name:'Market Explorer',exact:true});const before=await title.boundingBox();
 await expect(page.getByText('Interactive preview · Your preferences save automatically. Collection and account administration are read-only.',{exact:true})).toHaveCount(0);
 const response=page.waitForResponse(r=>r.url().endsWith('/api/v1/environment'));finish();await response;
 await expect.poll(async()=>Math.round((await title.boundingBox())!.y)).toBe(Math.round(before!.y));
});
