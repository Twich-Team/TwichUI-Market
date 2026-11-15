// Genuine post-switch data. Temporary member only; no schedule or data mutations.
const {chromium,expect}=require('../web/node_modules/@playwright/test');
const net=require('node:net'),fs=require('node:fs');
const root='/work/artifacts/market-switch';fs.mkdirSync(root,{recursive:true});
const servers=[18443,18444].map((port)=>net.createServer(socket=>{
 const remote=net.connect(443,port===18443?'proxy':'twichui-market-modernization-preview');
 socket.pipe(remote);remote.pipe(socket);remote.on('error',()=>socket.destroy());socket.on('error',()=>remote.destroy());
}));
let phase='startup';
(async()=>{
 await Promise.all(servers.map((server,i)=>new Promise(resolve=>server.listen(18443+i,'127.0.0.1',resolve))));
 const browser=await chromium.launch(),reports=[];
 try{
  for(const port of [18443,18444]){
   const origin='https://localhost:'+port;
   phase=port+'_login';
   const context=await browser.newContext({baseURL:origin,ignoreHTTPSErrors:false,viewport:{width:1440,height:1100}});
   const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.name));
   const response=await page.goto('/');expect(response.status()).toBe(200);
   await page.getByLabel('Username',{exact:true}).fill(process.env.MARKET_LIVE_CHECK_USERNAME);
   await page.getByLabel('Password',{exact:true}).fill(process.env.MARKET_LIVE_CHECK_PASSWORD);
   await page.getByRole('button',{name:'Sign in',exact:true}).click();
   await expect(page.getByRole('heading',{name:'Market Explorer',exact:true})).toBeVisible();
   phase=port+'_identity';
   const markets=await(await page.request.get('/api/v1/markets')).json();
   expect(markets.markets.filter(m=>m.enabled).map(m=>m.id)).toEqual([2]);
   const market=markets.markets.find(m=>m.id===2),old=markets.markets.find(m=>m.id===1);
   expect(market.house_id).toBe(114);expect(market.label).toBe('US — Normal — Horde');
   expect(market.verified&&market.player_identity_verified).toBe(true);expect(market.interval_seconds).toBe(300);
   expect(old.house_id).toBe(110);expect(old.enabled).toBe(false);
   const select=page.locator('select').filter({has:page.locator('option[value="2"]')}).first();
   await select.selectOption('2');await expect(select).toHaveValue('2');
   await expect(select.locator('option:checked')).toContainText('US — Normal — Horde');
   expect((await page.request.get('/api/v1/admin/users')).status()).toBe(403);
   phase=port+'_data';
   const items=await(await page.request.get('/api/v1/markets/2/items')).json();
   expect(items.synthetic).toBe(false);
   const item=items.items[0];expect(item).toBeTruthy();
   const detail=await(await page.request.get(`/api/v1/markets/2/items/${item.item_id}/${item.variant_key}`)).json();
   expect(detail.valuation.synthetic).toBe(false);expect(detail.valuation.supply).toBeGreaterThan(0);
   expect(detail.listings.length).toBeGreaterThan(0);expect(detail.listings_truncated).toBe(false);
   expect(String(detail.valuation.supply)).toBe(String(detail.listings.reduce((sum,l)=>sum+BigInt(l.quantity),0n)));
   await page.getByLabel('Search items',{exact:true}).fill(String(item.item_id));
   await page.getByRole('button',{name:'Search',exact:true}).click();
   if(port===18444){
    await page.getByRole('region',{name:'Item catalogue',exact:true}).getByRole('button',{name:'Select '+detail.name,exact:true}).click();
    await expect(page.locator('.item-heading h2')).toHaveText(detail.name);
   }else{
    const itemButton=page.getByRole('button',{name:detail.name,exact:true});
    if(await itemButton.count())await itemButton.first().click();
   }
   await expect(page.getByRole('heading',{name:detail.name,exact:true})).toBeVisible();
   await expect(page.getByText(detail.valuation.supply.toLocaleString()+' units',{exact:true})).toBeVisible();
   await expect(page.getByRole('heading',{name:'Current listings',exact:true})).toBeVisible();
   const history=await(await page.request.get(`/api/v1/markets/2/items/${item.item_id}/${item.variant_key}/history?days=365`)).json();
   expect(history.synthetic).toBe(false);expect(history.points.length).toBeGreaterThan(0);
   const oldItems=await(await page.request.get('/api/v1/markets/1/items')).json();
   expect(oldItems.synthetic).toBe(false);expect(oldItems.items.length).toBeGreaterThan(0);
   if(port===18444){
    await page.locator('.chart-viewport').first().scrollIntoViewIfNeeded();
    await expect(page.getByRole('img',{name:'Observed asking-price history'})).toBeVisible();
    await page.locator('.chart-viewport').nth(1).scrollIntoViewIfNeeded();
    await expect(page.getByRole('img',{name:'Current listed supply by price'})).toBeVisible();
    await page.evaluate(()=>scrollTo(0,0));
   }
   expect(errors).toEqual([]);
   await page.screenshot({path:root+(port===18443?'/production-normal-horde.png':'/preview-normal-horde.png'),fullPage:true});
   reports.push({origin,market,old_market_disabled:!old.enabled,historical_market_queryable:true,
    item_id:item.item_id,item_name:detail.name,variant_key:item.variant_key,supply:detail.valuation.supply,
    recent_price:detail.valuation.recent_price,listing_count:detail.listings.length,
    listing_ids:detail.listings.map(l=>l.auction_id),history_points:history.points.length,
    source_synthetic:false,tls_errors_ignored:false,page_errors:errors});
   await context.close();
  }
  fs.writeFileSync(root+'/browser.json',JSON.stringify({verified_at:new Date().toISOString(),reports},null,2));
  console.log('Verified production and preview Market Explorer: US Normal — Horde, genuine supply/listings/history, old history queryable, trusted TLS.');
 }finally{await browser.close();servers.forEach(s=>s.close());}
})().catch(error=>{console.error('Market switch browser verification failed at '+phase+' ('+error.name+').');if(phase.endsWith('_data'))console.error(error.message);servers.forEach(s=>s.close());process.exitCode=1;});
