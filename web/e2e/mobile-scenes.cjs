const {chromium}=require('playwright');const fs=require('node:fs');const {createHash}=require('node:crypto');
(async()=>{
 const b=await chromium.launch({executablePath:process.env.CHROMIUM_PATH});const p=await b.newPage({viewport:{width:390,height:844},hasTouch:true});const out=require('node:path').resolve(__dirname,'../../artifacts/mobile-experience');
 await p.goto('http://127.0.0.1:5173');await p.getByLabel('Username',{exact:true}).fill('owner');await p.getByLabel('Password',{exact:true}).fill('synthetic browser owner password');await p.getByRole('button',{name:'Sign in',exact:true}).click();await p.locator('main h1').waitFor();
 const result=await p.request.get('http://127.0.0.1:5173/api/v1/markets/1/catalogue/20000/variants');const key=(await result.json()).variants[0].variant_key;
 const auth=await p.request.post('http://127.0.0.1:5173/api/v1/companion/authorizations',{data:{client_id:'twichui-market-companion',redirect_uri:'http://127.0.0.1:43123/companion/callback',state:'S'.repeat(43),code_challenge:createHash('sha256').update('V'.repeat(43)).digest('base64url'),code_challenge_method:'S256',device_name:'Synthetic review computer',platform:'Windows',app_version:'2.0.0-beta.1'}});const approval=await auth.json();
 for(const [phase,port] of [['before',5176],['after',5173]]){
 const base=`http://127.0.0.1:${port}`;const shot=async name=>p.screenshot({path:`${out}/${phase}-${name}.png`,fullPage:true});
 await p.goto(base+'/?market=1&page_size=25');await p.locator('main h1').waitFor();await p.waitForTimeout(400);
 if(phase==='after'){await p.getByRole('button',{name:'Menu',exact:true}).click();await shot('navigation-390');await p.keyboard.press('Escape');}else await shot('navigation-390');
 const expand=p.getByRole('button',{name:phase==='after'?/Show \d+ exact variants/:/Expand \d+ variants/}).first();await expand.click();await p.getByRole('link',{name:/Inspect .*:/}).first().waitFor();await shot('variants-390');
 await p.getByRole('button',{name:'Next items',exact:true}).scrollIntoViewIfNeeded();await p.screenshot({path:`${out}/${phase}-pagination-390.png`,fullPage:false});
 await p.goto(base+`/markets/1/items/20000?variant=${key}`);await p.locator('main h1').waitFor();await p.waitForTimeout(400);await shot('exact-item-390');
 const history=p.getByRole('region',{name:'Price history',exact:true});await history.scrollIntoViewIfNeeded();await p.waitForTimeout(600);await p.screenshot({path:`${out}/${phase}-price-history-390.png`,fullPage:false});
 await p.getByRole('heading',{name:'Current listings',exact:true}).scrollIntoViewIfNeeded();await p.screenshot({path:`${out}/${phase}-current-listings-390.png`,fullPage:false});
 if(approval.request_id){await p.goto(base+`/companion/authorize?request=${approval.request_id}`);await p.getByRole('heading',{level:1}).waitFor();await shot('authorization-390');}
 }
 await b.close();
})();
