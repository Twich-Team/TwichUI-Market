const {chromium,expect}=require('../web/node_modules/@playwright/test');
const net=require('node:net'),fs=require('node:fs');
// Container-local TCP bridge preserves actual HTTPS origin/SNI without host changes.
let phase='startup';
const server=net.createServer(s=>{const t=net.connect(443,'proxy');s.pipe(t);t.pipe(s);t.on('error',()=>s.destroy());s.on('error',()=>t.destroy());});
(async()=>{
 await new Promise(r=>server.listen(18443,'127.0.0.1',r));const browser=await chromium.launch();
 try{
  // UI behavior only; Python/Rust verify certificate trust independently.
  const context=await browser.newContext({ignoreHTTPSErrors:true,baseURL:'https://localhost:18443',viewport:{width:1440,height:1100}}),page=await context.newPage(),errors=[];
  phase='member_sign_in';page.on('pageerror',e=>errors.push(e.message));await page.goto('/');
  await page.getByLabel('Username',{exact:true}).fill(process.env.MARKET_LIVE_CHECK_USERNAME);
  await page.getByLabel('Password',{exact:true}).fill(process.env.MARKET_LIVE_CHECK_PASSWORD);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Market Explorer',exact:true})).toBeVisible();
  phase='live_explorer';const markets=await (await page.request.get('/api/v1/markets')).json();expect(markets.markets.filter(m=>m.enabled)).toHaveLength(1);
  expect(markets.markets.find(m=>m.id===1).verified).toBe(true);expect((await page.request.get('/api/v1/admin/users')).status()).toBe(403);
  const items=await (await page.request.get('/api/v1/markets/1/items')).json();expect(items.synthetic).toBe(false);expect(items.items.length).toBeGreaterThan(0);
  const item=items.items[0],detail=await (await page.request.get(`/api/v1/markets/1/items/${item.item_id}/${item.variant_key}`)).json();
  expect(detail.valuation.synthetic).toBe(false);expect(detail.valuation.supply).toBeGreaterThan(0);expect(detail.listings.length).toBeGreaterThan(0);
  expect(detail.listings_truncated).toBe(false);
  const total=detail.listings.reduce((n,l)=>n+(l.buyout===null?0n:BigInt(l.buyout)),0n);
  const priced=detail.listings.reduce((n,l)=>n+(l.buyout===null?0n:BigInt(l.quantity)),0n);
  expect(String(detail.valuation.supply)).toBe(String(detail.listings.reduce((n,l)=>n+BigInt(l.quantity),0n)));
  expect(detail.valuation.recent_price).toBe(String((2n*total+priced)/(2n*priced)));

  await page.getByLabel('Search items',{exact:true}).fill(String(item.item_id));
  await Promise.all([page.waitForResponse(r=>r.url().includes('/items?q='+item.item_id)&&r.status()===200),page.getByRole('button',{name:'Search',exact:true}).click()]);
  await expect(page.getByRole('heading',{name:detail.name,exact:true})).toBeVisible();
  await expect(page.getByRole('img',{name:'Observed asking-price history'})).toBeVisible();
  await expect(page.getByText(detail.valuation.supply.toLocaleString()+' units',{exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Current listings',exact:true})).toBeVisible();
  await expect(page.getByRole('cell',{name:detail.listings[0].auction_id,exact:true})).toBeVisible();
  await expect(page.getByText('Synthetic fixture data · not live Auction House observations.')).toHaveCount(0);
  const history=await (await page.request.get(`/api/v1/markets/1/items/${item.item_id}/${item.variant_key}/history?days=365`)).json();
  expect(history.synthetic).toBe(false);expect(history.points.length).toBeGreaterThan(0);
  fs.mkdirSync('/work/artifacts/live-browser',{recursive:true});await page.screenshot({path:'/work/artifacts/live-browser/explorer.png',fullPage:true});
  phase='live_deal_finder';await page.getByRole('button',{name:'Deal Finder',exact:true}).click();await expect(page.getByText('Still building market history:',{exact:false})).toBeVisible();
  const deals=await (await page.request.get('/api/v1/markets/1/deals')).json();expect(deals.synthetic).toBe(false);expect(deals.history_coverage.status).toBe('insufficient');expect(deals.deals).toHaveLength(0);
  const limited=await (await page.request.get('/api/v1/markets/1/deals?minimum_coverage=1&minimum_discount=1')).json();
  expect(limited.synthetic).toBe(false);expect(limited.deals.length).toBeGreaterThan(0);
  expect(limited.deals.every(d=>d.confidence==='limited'&&d.coverage_days===1)).toBe(true);
  for(const name of ['Supply changes','Price changes']){await page.getByRole('tab',{name,exact:true}).click();await expect(page.getByText('Still building market history: 0 observed prior UTC days',{exact:false})).toBeVisible();}
  await page.screenshot({path:'/work/artifacts/live-browser/deals.png',fullPage:true});expect(errors).toEqual([]);
  console.log(JSON.stringify({live_browser_verified:true,market_id:1,item_id:item.item_id,variant_key:item.variant_key,supply:detail.valuation.supply,recent_price:detail.valuation.recent_price,listing_sample_count:detail.listings.length,history_points:history.points.length,deal_coverage:deals.history_coverage,limited_coverage_candidates:limited.deals.length,source_synthetic:false}));
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error('Live browser verification failed at '+phase+'; details suppressed to protect temporary credentials.');server.close();process.exitCode=1;});
