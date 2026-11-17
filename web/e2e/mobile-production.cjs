// Read-only real-production acceptance. No fixture routes or provider campaigns.
const {chromium,expect}=require('@playwright/test');
const fs=require('node:fs'),crypto=require('node:crypto');
const origin='https://market.twich.gg',out='/evidence';
const digest=x=>crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');
const wait=ms=>new Promise(r=>setTimeout(r,ms));
let phase='startup',browser,page;
const result={source:'Actual public HTTPS production; browser emulation, not physical iPhone acceptance',errors:[],httpFailures:[],checks:[],screenshots:[]};
async function shot(name){await page.screenshot({path:`${out}/${name}.png`,fullPage:true});result.screenshots.push(name+'.png');}
async function get(path){const r=await page.request.get(origin+'/api/v1'+path);expect(r.status(),path).toBe(200);return r.json();}
async function geometry(label){await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth),{timeout:10000}).toBe(page.viewportSize().width);result.checks.push(label);}
async function ready(){await expect(page.locator('main h1')).toBeVisible({timeout:30000});await page.waitForTimeout(450);}
(async()=>{
 browser=await chromium.launch();const context=await browser.newContext({viewport:{width:1440,height:1000},ignoreHTTPSErrors:false});
 await context.addCookies([{name:process.env.MOBILE_COOKIE_NAME,value:process.env.MOBILE_SESSION_TOKEN,url:origin,secure:true,httpOnly:true,sameSite:'Strict'}]);
 page=await context.newPage();page.on('pageerror',e=>result.errors.push(e.message));
 page.on('response',r=>{if(r.url().startsWith(origin+'/api/')&&r.status()>=500)result.httpFailures.push({url:r.url(),status:r.status()});});
 phase='predeployment HTTPS and session';let response=await page.goto(origin+'/?market=2');expect(response.status()).toBe(200);result.tls=await response.securityDetails();await ready();
 const session=await get('/auth/session'),preferences=await get('/me/preferences');result.before={user_id:session.user.id,preferences_sha256:digest(preferences)};
 const baseline=await get('/markets/2/catalogue?page_size=25&sort=name&direction=asc');result.before.catalogue_snapshot=baseline.snapshot_id;
 result.before.catalogue_sha256=digest(baseline);
 fs.writeFileSync(out+'/ready.json',JSON.stringify({ready:true,public_session_established:true,preferences_sha256:digest(preferences)}));
 phase='waiting for verified frontend deployment';const deadline=Date.now()+45*60*1000;
 while(!fs.existsSync(out+'/deployed')){if(Date.now()>deadline)throw Error('Deployment gate timed out');await wait(1000);}
 phase='session continuity';await page.reload();await ready();expect((await get('/auth/session')).user.id).toBe(session.user.id);expect(await get('/me/preferences')).toEqual(preferences);result.checks.push('Existing public session and exact saved preference revision survive frontend replacement');
 result.environment=await get('/environment');expect(result.environment.read_only).toBe(false);
 phase='login form';const anonymous=await browser.newContext({viewport:{width:320,height:740}});const login=await anonymous.newPage();await login.goto(origin);await expect(login.getByLabel('Username',{exact:true})).toBeVisible();
 expect(await login.evaluate(()=>document.documentElement.scrollWidth)).toBe(320);await expect(login.getByLabel('Password',{exact:true})).toBeVisible();await expect(login.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();expect((await login.request.get(origin+'/api/v1/markets')).status()).toBe(401);result.checks.push('320px login controls reachable; unauthenticated protected API denied');result.password_login='Operator bootstrap password was already rejected before deployment; authenticated acceptance uses an audited short-lived existing-account session. Actual owner password entry remains a phone acceptance step.';
 await anonymous.close();
 phase='Explorer viewport matrix';
 for(const width of [320,344,360,375,390,430,600,768,1024,1440]){
  await page.setViewportSize({width,height:900});await page.goto(origin+'/?market=2&page_size=25');await ready();
  await expect(page.locator(width<=700?'.mobile-item':'.catalogue-table').first()).toBeVisible({timeout:30000});await geometry('Explorer '+width+'px: no page overflow');
  const market=await page.getByRole('combobox',{name:'Market',exact:true}).boundingBox(),search=await page.getByLabel('Search items',{exact:true}).boundingBox();
  expect(market.x+market.width<=search.x||search.x+search.width<=market.x||market.y+market.height<=search.y||search.y+search.height<=market.y).toBe(true);
  if(width<=700){const row=page.locator('.mobile-item').first();await expect(row.locator('dt').filter({hasText:'Supply'})).toBeVisible();await expect(row.locator('.mobile-item-prices')).toBeVisible();expect(await row.evaluate(e=>e.scrollWidth<=e.clientWidth+1)).toBe(true);}
  if(width<=800){await page.getByRole('button',{name:'Menu',exact:true}).click();for(const name of ['Market Explorer','Deal Finder','Administration','Account & devices','Get Desktop Companion','Sign out'])await expect(page.getByRole('button',{name,exact:true})).toBeVisible();await page.keyboard.press('Escape');await expect(page.getByRole('button',{name:'Menu',exact:true})).toBeFocused();}
  if([320,344,390,768,1440].includes(width))await shot('explorer-'+width);
 }
 phase='search sorting pagination variants';await page.setViewportSize({width:344,height:820});await page.goto(origin+'/?market=2&page_size=25&sort=name&direction=asc');await ready();
 await page.getByLabel('Search items',{exact:true}).fill('Linen');await page.getByRole('button',{name:'Search',exact:true}).click();await expect(page.locator('.mobile-item').first()).toContainText(/Linen/i,{timeout:30000});await geometry('Actual Linen search');await shot('search-344');
 // URL sorting exercises the live server and shared state without rewriting owner preferences.
 await page.goto(origin+'/?market=2&page_size=25&sort=supply&direction=desc');await ready();await expect(page.getByRole('combobox',{name:'Sort items',exact:true})).toHaveValue('supply');
 const next=page.getByRole('button',{name:'Next items',exact:true});await next.scrollIntoViewIfNeeded();await expect(next).toBeEnabled();await next.click();await expect(page).toHaveURL(/page=1/);await geometry('Narrow pagination next');await page.getByRole('button',{name:'Previous items',exact:true}).click();await expect(page).toHaveURL(/page=0/);
 await page.goto(origin+'/?market=2&page_size=100&sort=name&direction=asc');await ready();const expansion=page.getByRole('button',{name:/Show \d+ exact variants/}).first();await expect(expansion).toBeVisible({timeout:30000});await expansion.click();const exact=page.getByRole('link',{name:/Inspect .*:/}).first();await expect(exact).toBeVisible();const target=await exact.getAttribute('href');expect(target).toContain('variant=');await shot('variants-344');await exact.click();await ready();expect(new URL(page.url()).pathname+new URL(page.url()).search).toBe(target);await geometry('Exact Item Details');
 phase='actual history chart';const history=page.getByRole('region',{name:'Price history',exact:true});await history.scrollIntoViewIfNeeded();await expect(history.locator('canvas').first()).toBeVisible({timeout:30000});await shot('history-344');result.exact_item_url=page.url();
 await page.goBack();await ready();await expect(page.getByRole('button',{name:/Hide \d+ exact variants/}).first()).toBeVisible();
 phase='pages and administration';
 for(const width of [320,344,390,768,1440]){
  await page.setViewportSize({width,height:900});
  for(const route of ['/deals','/account','/companion','/administration']){await page.goto(origin+route);await ready();await geometry(route+' '+width+'px');if(width===390)await shot(route.slice(1)+'-390');}
  const select=page.getByRole('combobox',{name:'Administration section',exact:true}),tabs=page.getByRole('tab');const count=width<=700?await select.locator('option').count():await tabs.count();expect(count).toBe(9);
  for(let i=0;i<count;i++){if(width<=700)await select.selectOption({index:i});else await tabs.nth(i).click();await wait(500);await geometry('Administration section '+i+' '+width+'px');if(width===390&&[7,8].includes(i))await shot('administration-'+i+'-390');}
 }
 phase='Companion download and approval route';await page.setViewportSize({width:320,height:740});await page.goto(origin+'/companion');await ready();const release=await get('/companion/private-beta/current');expect(release.version).toBe('2.0.0-beta.5');
 const download=await page.request.get(origin+release.download_url);expect(download.status()).toBe(200);const bytes=await download.body();expect(crypto.createHash('sha256').update(bytes).digest('hex')).toBe(release.sha256);result.companion={version:release.version,bytes:bytes.length,sha256:release.sha256,unchanged_publication:true};
 const liveSession=await get('/auth/session');const request=await page.request.post(origin+'/api/v1/companion/authorizations',{headers:{Origin:origin,'X-CSRF-Token':liveSession.csrf_token},data:{client_id:'twichui-market-companion',redirect_uri:'http://127.0.0.1:43123/companion/callback',state:crypto.randomBytes(32).toString('base64url'),code_challenge:crypto.createHash('sha256').update('V'.repeat(43)).digest('base64url'),code_challenge_method:'S256',device_name:'Mobile release acceptance (deny)',platform:'Windows',app_version:'2.0.0-beta.5'}});expect(request.status()).toBe(201);const approval=await request.json();
 await page.goto(origin+'/companion/authorize?request='+encodeURIComponent(approval.request_id));await expect(page.getByRole('button',{name:'Approve this device',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Deny',exact:true})).toBeVisible();await geometry('Actual pending device approval 320px');await shot('device-approval-320');await page.route('http://127.0.0.1:43123/**',route=>route.abort());const decisionResponse=page.waitForResponse(r=>r.url().endsWith('/decision'));await page.getByRole('button',{name:'Deny',exact:true}).click();const decision=await decisionResponse;expect(decision.status()).toBe(200);expect((await get('/companion/authorizations/'+encodeURIComponent(approval.request_id))).status).toBe('denied');await page.goto(origin+'/companion');await ready();result.device_approval='Actual pending public consent has reachable Approve/Deny controls; request denied, no real device admitted';
 phase='final preservation';expect(await get('/me/preferences')).toEqual(preferences);result.checks.push('Exact owner preference values and revision remain unchanged');expect(result.errors).toEqual([]);expect(result.httpFailures).toEqual([]);result.success=true;result.completed_at=new Date().toISOString();
 fs.writeFileSync(out+'/acceptance.json',JSON.stringify(result,null,2)+'\n');console.log('Public HTTPS production mobile/desktop acceptance passed');await browser.close();
})().catch(async e=>{result.success=false;result.phase=phase;result.failure=e.message;fs.writeFileSync(out+'/failure.json',JSON.stringify(result,null,2)+'\n');if(page)await shot('failure').catch(()=>{});if(browser)await browser.close();console.error(phase+': '+e.message);process.exit(1);});
