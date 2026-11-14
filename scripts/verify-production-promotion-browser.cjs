// Audited temporary users only. Keep real public/local sessions across deployment.
const {chromium,expect}=require('../web/node_modules/@playwright/test');
const AxeBuilder=require('../web/node_modules/@axe-core/playwright').default;
const fs=require('node:fs'),net=require('node:net');
const root='/work/artifacts/production-promotion';fs.mkdirSync(root,{recursive:true});
const nonce=process.env.MARKET_ACCESS_NONCE;
const gate=root+'/continue-'+nonce,ready=root+'/ready.json';
const publicOrigin='https://market.twich.gg',local='https://localhost:18443',preview='https://localhost:18444';
const servers=[18443,18444].map(port=>net.createServer(socket=>{
 const remote=net.connect(443,port===18443?'proxy':'twichui-market-modernization-preview');
 socket.pipe(remote);remote.pipe(socket);remote.on('error',()=>socket.destroy());socket.on('error',()=>remote.destroy());
}));
let phase='startup';
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
(async()=>{
 await Promise.all(servers.map((server,i)=>new Promise(resolve=>server.listen(18443+i,'127.0.0.1',resolve))));
 const browser=await chromium.launch(),errors=[];
 const context=await browser.newContext({viewport:{width:1440,height:1100},ignoreHTTPSErrors:false});
 const admin=await context.newPage();admin.on('pageerror',error=>errors.push(error.name));
 const members=await browser.newContext({viewport:{width:1440,height:1100},ignoreHTTPSErrors:false});
 const member=await members.newPage();member.on('pageerror',error=>errors.push(error.name));
 const locals=await browser.newContext({viewport:{width:1440,height:1100},ignoreHTTPSErrors:false});
 const localPage=await locals.newPage();localPage.on('pageerror',error=>errors.push(error.name));
 async function login(page,origin,role){
  await page.goto(origin+'/');await page.getByLabel('Username',{exact:true}).fill('market_access_'+nonce+'_'+role);
  await page.getByLabel('Password',{exact:true}).fill(process.env['MARKET_ACCESS_'+role.toUpperCase()+'_PASSWORD']);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Market Explorer',exact:true})).toBeVisible();
 }
 async function get(page,origin,path){const response=await page.request.get(origin+'/api/v1'+path);expect(response.status()).toBe(200);return response.json();}
 const read=page=>get(page,publicOrigin,'/me/preferences');
 async function saved(page,values){await expect.poll(async()=>(await read(page)).values).toMatchObject(values);}
 async function logout(page,origin){
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
  expect((await page.request.get(origin+'/api/v1/markets')).status()).toBe(401);
 }
 try{
  phase='predeployment_public_sessions';
  expect((await admin.request.get(publicOrigin+'/api/v1/markets')).status()).toBe(401);
  const first=await admin.goto(publicOrigin+'/');expect(first.status()).toBe(200);const tls=await first.securityDetails();
  phase='predeployment_admin_login';await login(admin,publicOrigin,'admin');
  phase='predeployment_member_login';await login(member,publicOrigin,'member');
  phase='predeployment_local_login';await login(localPage,local,'member');
  phase='predeployment_existing_device';
  const publicSession=await get(admin,publicOrigin,'/auth/session');
  const memberSession=await get(member,publicOrigin,'/auth/session');
  const localSession=await get(localPage,local,'/auth/session');
  const originalCookie=(await context.cookies()).find(c=>c.domain==='market.twich.gg'&&c.name==='market_session');
  expect(originalCookie.secure&&originalCookie.httpOnly).toBe(true);expect(originalCookie.sameSite).toBe('Strict');
  const tokenResponse=await admin.request.post(publicOrigin+'/api/v1/devices',{
   headers:{Origin:publicOrigin,'X-CSRF-Token':publicSession.csrf_token},data:{name:'Promotion continuity verification'}});
  expect(tokenResponse.status()).toBe(201);const device=await tokenResponse.json();
  const beforeSync=await admin.request.get(publicOrigin+'/api/v1/sync/markets/2?limit=1',{headers:{Authorization:'Bearer '+device.token}});
  expect(beforeSync.status()).toBe(200);const initialSync=await beforeSync.json();expect(initialSync.contract_version).toBe(1);
  phase='predeployment_saved_preferences';
  const previewPage=await members.newPage();await login(previewPage,preview,'member');
  await previewPage.getByRole('button',{name:'Account & devices',exact:true}).click();
  const controls=previewPage.getByRole('region',{name:'My Preferences',exact:true});
  await controls.getByLabel('Preferred market').selectOption('2');
  await controls.getByLabel('Explorer chart range').selectOption('60');
  await controls.getByLabel('Item table page size').selectOption('50');
  await expect.poll(async()=>(await get(previewPage,preview,'/me/preferences')).values).toMatchObject({market_id:2,explorer_days:60,item_page_size:50});
  const existingPreferences=await get(previewPage,preview,'/me/preferences');
  await logout(previewPage,preview);await previewPage.close();
  fs.writeFileSync(ready,JSON.stringify({ready_at:new Date().toISOString(),nonce,
   public_tls:tls,public_session_established:true,local_session_established:true,
   device_and_cursor_established:true,preferences_stored_before_deployment:true,
   continue_file:gate.replace('/work/','')},null,2));
  console.log('Predeployment public/local sessions, device cursor and saved settings established; waiting for scoped frontend/API replacement.');
  phase='waiting_for_deployment';
  const deadline=Date.now()+20*60*1000;
  while(!fs.existsSync(gate)){if(Date.now()>deadline)throw new Error('Deployment gate timed out');await pause(1000);}
  phase='existing_session_continuity';
  await admin.reload();await member.reload();await localPage.reload();
  for(const page of [admin,member,localPage])await expect(page.getByRole('heading',{name:'Market Explorer',exact:true})).toBeVisible();
  expect((await get(admin,publicOrigin,'/auth/session')).user.id).toBe(publicSession.user.id);
  expect((await get(member,publicOrigin,'/auth/session')).user.id).toBe(memberSession.user.id);
  expect((await get(localPage,local,'/auth/session')).user.id).toBe(localSession.user.id);
  expect((await context.cookies()).find(c=>c.domain==='market.twich.gg'&&c.name==='market_session').value).toBe(originalCookie.value);
  await expect(admin.getByText('Design review in progress',{exact:false})).toHaveCount(0);
  await expect(admin.getByText('Interactive preview',{exact:false})).toHaveCount(0);
  const environment=await get(admin,publicOrigin,'/environment');expect(environment.read_only).toBe(false);expect(environment.origin).toBe(publicOrigin);
  const restored=await read(member);expect(restored.values).toEqual(existingPreferences.values);expect(restored.revision).toBe(existingPreferences.revision);
  const continuation=await admin.request.get(publicOrigin+'/api/v1/sync/markets/2?limit=1&cursor='+encodeURIComponent(initialSync.cursor),{headers:{Authorization:'Bearer '+device.token}});
  expect(continuation.status()).toBe(200);const sync=await continuation.json();expect(sync.contract_version).toBe(1);expect(sync.synthetic).toBe(false);
  phase='csrf_and_authorization';
  const body={schema_version:1,expected_revision:restored.revision,changes:{item_page_size:100}};
  expect((await member.request.patch(publicOrigin+'/api/v1/me/preferences',{data:body})).status()).toBe(403);
  expect((await member.request.patch(publicOrigin+'/api/v1/me/preferences',{headers:{Origin:preview,'X-CSRF-Token':memberSession.csrf_token},data:body})).status()).toBe(403);
  expect((await member.request.get(publicOrigin+'/api/v1/admin/users')).status()).toBe(403);
  await expect(member.getByRole('button',{name:'Administration',exact:true})).toHaveCount(0);
  phase='public_explorer';
  const markets=(await get(member,publicOrigin,'/markets')).markets;
  expect(markets.filter(m=>m.enabled).map(m=>[m.id,m.house_id,m.interval_seconds])).toEqual([[2,114,300]]);
  const selected=member.locator('select').filter({has:member.locator('option[value="2"]')}).first();await expect(selected).toHaveValue('2');
  const catalogue=member.getByRole('region',{name:'Item catalogue',exact:true});
  await expect(catalogue.getByLabel('Items per page')).toHaveValue('50');
  await expect(member.getByRole('button',{name:'60D',exact:true})).toHaveClass(/selected/);
  const items=await get(member,publicOrigin,'/markets/2/items');expect(items.synthetic).toBe(false);const item=items.items[0];expect(item).toBeTruthy();
  const detail=await get(member,publicOrigin,`/markets/2/items/${item.item_id}/${item.variant_key}`);
  expect(detail.valuation.synthetic).toBe(false);expect(detail.listings_truncated).toBe(false);expect(detail.listings.length).toBeGreaterThan(0);
  expect(BigInt(detail.valuation.supply)).toBe(detail.listings.reduce((sum,l)=>sum+BigInt(l.quantity),0n));
  await member.getByLabel('Search items',{exact:true}).fill(String(item.item_id));await member.getByRole('button',{name:'Search',exact:true}).click();
  await catalogue.getByRole('button',{name:'Select '+detail.name,exact:true}).click();
  await expect(member.locator('.item-heading h2')).toHaveText(detail.name);
  await expect(member.getByText(detail.valuation.supply.toLocaleString()+' units',{exact:true})).toBeVisible();
  await member.locator('.chart-viewport').first().scrollIntoViewIfNeeded();await expect(member.getByRole('img',{name:'Observed asking-price history'})).toBeVisible();
  await member.locator('.chart-viewport').nth(1).scrollIntoViewIfNeeded();await expect(member.getByRole('img',{name:'Current listed supply by price'})).toBeVisible();
  await member.evaluate(()=>scrollTo(0,0));await member.screenshot({path:root+'/production-explorer.png',fullPage:true});
  phase='public_deal_finder';await member.getByRole('button',{name:'Deal Finder',exact:true}).click();
  await expect(member.getByRole('heading',{name:'Deal Finder',exact:true})).toBeVisible();
  await member.getByLabel('Maximum spend (gold)').fill('250');
  await member.getByLabel('Minimum observed days').fill('1');
  await member.getByRole('button',{name:'Apply filters',exact:true}).click();
  const deals=await get(member,publicOrigin,'/markets/2/deals?minimum_discount=15&maximum_spend=2500000&minimum_coverage=1&minimum_confidence=limited');expect(deals.synthetic).toBe(false);
  for(const [tab,kind] of [['Supply changes','supply'],['Price changes','price']]){
   await member.getByRole('tab',{name:tab,exact:true}).click();
   const signals=await get(member,publicOrigin,'/markets/2/signals?kind='+kind+'&minimum_change=15&minimum_coverage=1&minimum_confidence=limited&direction=any');expect(signals.synthetic).toBe(false);
  }
  await saved(member,{market_id:2,explorer_days:60,item_page_size:50,deal_mode:'price',deal_spend_gold:250,deal_coverage:1});
  await member.screenshot({path:root+'/production-deals.png',fullPage:true});
  phase='public_preferences_refresh_and_relogin';
  await member.getByRole('button',{name:'Account & devices',exact:true}).click();
  const personal=member.getByRole('region',{name:'My Preferences',exact:true});
  await personal.getByLabel('Item table page size').selectOption('100');await personal.getByLabel('Explorer chart range').selectOption('365');
  await saved(member,{item_page_size:100,explorer_days:365});const savedBeforeLogout=(await read(member)).values;
  await member.reload();await member.getByRole('button',{name:'Account & devices',exact:true}).click();
  await expect(member.getByRole('region',{name:'My Preferences',exact:true}).getByLabel('Item table page size')).toHaveValue('100');
  await logout(member,publicOrigin);await login(member,publicOrigin,'member');expect((await read(member)).values).toEqual(savedBeforeLogout);
  await member.getByRole('button',{name:'Account & devices',exact:true}).click();
  await expect(member.getByRole('region',{name:'My Preferences',exact:true}).getByLabel('Explorer chart range')).toHaveValue('365');
  const axe=await new AxeBuilder({page:member}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();expect(axe.violations).toEqual([]);
  await member.screenshot({path:root+'/production-preferences.png',fullPage:true});
  phase='administration_and_retention_read_only_inspection';
  await admin.getByRole('button',{name:'Administration',exact:true}).click();
  await expect(admin.getByRole('heading',{name:'Administration',exact:true})).toBeVisible();
  expect((await admin.request.get(publicOrigin+'/api/v1/admin/users')).status()).toBe(200);
  await admin.getByRole('tab',{name:'Markets & schedules',exact:true}).click();await expect(admin.getByRole('heading',{name:'Configure a market',exact:true})).toBeVisible();
  await admin.screenshot({path:root+'/production-markets.png',fullPage:true});
  await admin.getByRole('tab',{name:'Storage & backups',exact:true}).click();
  await expect(admin.getByRole('heading',{name:'Historical retention policy',exact:true})).toBeVisible();
  const retention=await get(admin,publicOrigin,'/admin/retention');expect(retention.application_authorized).toBe(false);expect(retention.backup_restore_ready).toBe(true);
  await admin.getByRole('button',{name:'Preview retention impact',exact:true}).click();
  await expect(admin.getByText('Dry run · estimated logical impact',{exact:false})).toBeVisible();
  await expect(admin.getByRole('button',{name:'Apply confirmed batch',exact:true})).toBeDisabled();
  await admin.screenshot({path:root+'/production-retention.png',fullPage:true});
  phase='account_and_devices';
  await admin.getByRole('button',{name:'Account & devices',exact:true}).click();
  await expect(admin.getByRole('button',{name:'Create device token',exact:true})).toBeEnabled();
  await expect(admin.getByRole('region',{name:'My Preferences',exact:true})).toBeVisible();
  await expect(admin.getByText('Promotion continuity verification',{exact:true})).toBeVisible();
  expect((await admin.request.delete(publicOrigin+'/api/v1/devices/'+device.id,{headers:{Origin:publicOrigin,'X-CSRF-Token':publicSession.csrf_token}})).status()).toBe(204);
  expect((await admin.request.get(publicOrigin+'/api/v1/sync/markets/2',{headers:{Authorization:'Bearer '+device.token}})).status()).toBe(401);
  phase='local_new_frontend_and_preferences';
  await expect(localPage.getByRole('region',{name:'Item catalogue',exact:true})).toBeVisible();
  expect((await get(localPage,local,'/me/preferences')).values).toEqual(savedBeforeLogout);
  await logout(localPage,local);await logout(admin,publicOrigin);await logout(member,publicOrigin);
  const after=(await getAfter()).markets;
  async function getAfter(){await login(admin,publicOrigin,'admin');return get(admin,publicOrigin,'/markets');}
  expect(after.map(m=>[m.id,m.enabled,m.interval_seconds])).toEqual(markets.map(m=>[m.id,m.enabled,m.interval_seconds]));
  expect((await get(admin,publicOrigin,'/admin/retention')).application_authorized).toBe(false);
  expect(errors).toEqual([]);await logout(admin,publicOrigin);
  fs.writeFileSync(root+'/verification.json',JSON.stringify({verified_at:new Date().toISOString(),public_url:publicOrigin,
   public_tls:tls,tls_errors_ignored:false,secure_httponly_strict_cookie:true,existing_public_and_local_sessions_survived:true,
   existing_device_and_cursor_survived:true,existing_preferences_survived:true,csrf_and_origin_rejections_verified:true,
   member_admin_boundary_verified:true,environment_read_only:false,source_synthetic:false,item:{id:item.item_id,name:detail.name,supply:detail.valuation.supply,listings:detail.listings.length,recent_price:detail.valuation.recent_price},
   explorer_charts_verified:true,deal_finder_all_modes_verified:true,preferences_refresh_logout_login_verified:true,
   administration_market_configuration_verified:true,account_devices_and_revocation_verified:true,retention_dry_run_only:true,
   retention_application_authorized:false,market_configuration_unchanged:true,axe_violations:axe.violations.length,page_errors:errors},null,2));
  console.log('Production public/local authentication, session/device continuity, preferences refresh/relogin, Explorer, Deals, administration and retention dry-run verification passed.');
 }catch(error){
  fs.writeFileSync(root+'/failure.json',JSON.stringify({phase,error_type:error.name,
   frames:(error.stack||'').split('\n').filter(line=>/^\s+at .*verify-production-promotion-browser\.cjs:\d+:\d+/.test(line)),at:new Date().toISOString()}));
  await admin.screenshot({path:root+'/failure-admin.png',fullPage:true}).catch(()=>{});
  await member.screenshot({path:root+'/failure-member.png',fullPage:true}).catch(()=>{});
  throw error;
 }finally{await browser.close();servers.forEach(server=>server.close());fs.rmSync(gate,{force:true});}
})().catch(error=>{console.error('Production verification failed at '+phase+' ('+error.name+'); credentials suppressed.');servers.forEach(server=>server.close());process.exitCode=1;});
