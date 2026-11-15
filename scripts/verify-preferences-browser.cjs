// Live preview: only the audited temporary member's own preferences are changed.
const {chromium,expect}=require('../web/node_modules/@playwright/test');
const AxeBuilder=require('../web/node_modules/@axe-core/playwright').default;
const fs=require('node:fs'),net=require('node:net');
const root='/work/artifacts/preferences-live',origin='https://localhost:18444';
fs.mkdirSync(root,{recursive:true});
const server=net.createServer(socket=>{
 const remote=net.connect(443,'twichui-market-modernization-preview');socket.pipe(remote);remote.pipe(socket);
 remote.on('error',()=>socket.destroy());socket.on('error',()=>remote.destroy());
});
let phase='startup';
(async()=>{
 await new Promise(resolve=>server.listen(18444,'127.0.0.1',resolve));
 const browser=await chromium.launch();
 async function login(){
  const context=await browser.newContext({baseURL:origin,ignoreHTTPSErrors:false,viewport:{width:1440,height:1100}});
  const page=await context.newPage();await page.goto('/');
  await page.getByLabel('Username',{exact:true}).fill(process.env.MARKET_LIVE_CHECK_USERNAME);
  await page.getByLabel('Password',{exact:true}).fill(process.env.MARKET_LIVE_CHECK_PASSWORD);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Market Explorer',exact:true})).toBeVisible();
  return {context,page};
 }
 const read=async page=>(await page.request.get('/api/v1/me/preferences')).json();
 const account=async page=>{
  await page.getByRole('button',{name:'Account & devices',exact:true}).click();
  return page.getByRole('region',{name:'My Preferences',exact:true});
 };
 async function saved(page,values){await expect.poll(async()=>(await read(page)).values).toMatchObject(values);}
 try{
  phase='login';const {context,page}=await login(),errors=[];page.on('pageerror',error=>errors.push(error.name));
  const session=await(await page.request.get('/api/v1/auth/session')).json();
  const initial=await read(page);expect(initial.user_id).toBe(session.user.id);expect(initial.revision).toBe(0);
  const markets=(await(await page.request.get('/api/v1/markets')).json()).markets;
  expect(markets.filter(m=>m.enabled).map(m=>m.id)).toEqual([2]);
  const environment=await(await page.request.get('/api/v1/environment')).json();expect(environment.read_only).toBe(true);
  phase='personal_preferences';const personal=await account(page);
  await expect(page.getByRole('button',{name:'Create device token',exact:true})).toBeDisabled();
  await personal.getByLabel('Preferred market').selectOption('2');
  await personal.getByLabel('Explorer chart range').selectOption('60');
  await personal.getByLabel('Item table page size').selectOption('50');
  await saved(page,{market_id:2,explorer_days:60,item_page_size:50});
  const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();expect(axe.violations).toEqual([]);
  fs.writeFileSync(root+'/account-axe.json',JSON.stringify(axe.violations));
  await page.screenshot({path:root+'/my-preferences-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  const preferredBox=await personal.getByLabel('Preferred market').boundingBox();
  const rangeBox=await personal.getByLabel('Explorer chart range').boundingBox();
  expect(preferredBox.y+preferredBox.height).toBeLessThanOrEqual(rangeBox.y);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:root+'/my-preferences-mobile.png',fullPage:true});await page.setViewportSize({width:1440,height:1100});
  phase='catalogue';await page.getByRole('button',{name:'Market Explorer',exact:true}).click();
  const catalogue=page.getByRole('region',{name:'Item catalogue',exact:true});
  await expect(catalogue.getByLabel('Items per page')).toHaveValue('50');
  await expect(page.getByRole('button',{name:'60D',exact:true})).toHaveClass(/selected/);
  await expect(catalogue.locator('tbody tr').first()).toBeVisible();
  await catalogue.getByText('Item columns',{exact:true}).click();await catalogue.getByLabel('ID',{exact:true}).uncheck();
  await catalogue.getByRole('columnheader',{name:/Supply/}).getByRole('button').click();
  await saved(page,{item_columns:{item_id:false},item_sort:{id:'supply',desc:false}});
  const live=await(await page.request.get('/api/v1/markets/2/catalogue?page_size=50')).json();
  expect(live.synthetic).toBe(false);expect(live.items.length).toBeGreaterThan(0);
  await expect(catalogue).toHaveAttribute('aria-busy','false');
  await expect(page.locator('.item-heading h2')).toBeVisible();
  await page.screenshot({path:root+'/explorer-preferences.png',fullPage:true});
  phase='deal_filters';await page.getByRole('button',{name:'Deal Finder',exact:true}).click();
  await page.getByLabel('Maximum spend (gold)').fill('250');
  await page.getByRole('tab',{name:'Price changes',exact:true}).click();
  await page.getByLabel('Minimum change (%)').fill('20');await page.getByLabel('Minimum observed days').fill('2');
  await page.getByRole('combobox',{name:'Direction',exact:true}).selectOption('decrease');
  await page.getByRole('combobox',{name:'Evidence',exact:true}).selectOption('moderate');
  await saved(page,{deal_mode:'price',deal_change:20,deal_spend_gold:250,deal_coverage:2,deal_direction:'decrease',deal_confidence:'moderate'});
  phase='independent_device';const second=await login();
  const secondTable=second.page.getByRole('region',{name:'Item catalogue',exact:true});
  await expect(secondTable.getByLabel('Items per page')).toHaveValue('50');
  await expect(secondTable.getByRole('columnheader',{name:'ID',exact:true})).toHaveCount(0);
  await expect(secondTable.locator('th[aria-sort="ascending"]')).toContainText('Supply');
  await second.page.getByRole('button',{name:'Deal Finder',exact:true}).click();
  await expect(second.page.getByRole('tab',{name:'Price changes',exact:true})).toHaveAttribute('aria-selected','true');
  await expect(second.page.getByLabel('Minimum change (%)')).toHaveValue('20');
  const restored=await read(second.page);expect(restored.values).toEqual((await read(page)).values);
  phase='read_only_boundary';
  expect((await page.request.post('/api/v1/devices',{headers:{'X-CSRF-Token':session.csrf_token},data:{name:'must remain forbidden'}})).status()).toBe(403);
  expect((await page.request.post('/api/v1/admin/markets',{headers:{'X-CSRF-Token':session.csrf_token},data:{}})).status()).toBe(403);
  expect((await page.request.get('/api/v1/me/preferences/1')).status()).toBe(404);
  phase='reset';const controls=await account(page);await controls.getByRole('button',{name:'Reset my preferences',exact:true}).click();
  await saved(page,{market_id:null,explorer_days:14,item_page_size:25,deal_mode:'listings'});
  await second.page.reload();const resetOnSecond=await read(second.page);expect(resetOnSecond.values.item_page_size).toBe(25);
  await expect(second.page.getByRole('region',{name:'Item catalogue',exact:true}).getByLabel('Items per page')).toHaveValue('25');
  const after=(await(await page.request.get('/api/v1/markets')).json()).markets;
  expect(after.map(m=>({id:m.id,enabled:m.enabled,interval:m.interval_seconds}))).toEqual(markets.map(m=>({id:m.id,enabled:m.enabled,interval:m.interval_seconds})));
  expect(errors).toEqual([]);
  fs.writeFileSync(root+'/verification.json',JSON.stringify({verified_at:new Date().toISOString(),source_synthetic:false,tls_errors_ignored:false,
   preview_read_only_except_personal_preferences:true,initial_revision:initial.revision,restored_values:restored.values,
   separate_session_restore:true,reset_restored_in_second_session:true,live_catalogue_snapshot:live.snapshot_id,
   live_catalogue_items:live.total_items,axe_violations:axe.violations.length,mobile_fields_do_not_overlap:true,
   market_collection_unchanged:true,page_errors:errors,screenshots:['my-preferences-desktop.png','my-preferences-mobile.png','explorer-preferences.png']},null,2));
  await second.context.close();await context.close();
  console.log('Live preferences preview verified: automatic saves, independent-session restore, reset, trusted TLS, accessibility, genuine market data and unchanged collection.');
 }finally{await browser.close();server.close();}
})().catch(error=>{console.error('Live preferences check failed at '+phase+' ('+error.name+'); credentials suppressed.');server.close();process.exitCode=1;});
