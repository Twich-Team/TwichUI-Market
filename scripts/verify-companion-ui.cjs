const {chromium}=require('/tmp/node_modules/playwright');
const http=require('node:http');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const root='/work/desktop/ui';
(async()=>{
  const server=http.createServer((request,response)=>{
    const file={'/':'index.html','/style.css':'style.css','/app.js':'app.js'}[request.url];
    if(!file){response.writeHead(404).end();return;}
    response.setHeader('Content-Type',file.endsWith('.css')?'text/css':file.endsWith('.js')?'text/javascript':'text/html');
    response.end(fs.readFileSync(`${root}/${file}`));
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
  const page=await browser.newPage({viewport:{width:880,height:850}});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(()=>{
    let cursor=0,completed=false;
    window.__TAURI__={core:{invoke:async(command,args)=>{
      if(command==='connection')return null;
      if(command==='connect')return 'https://market.example/';
      if(command==='disconnect')return;
      if(command==='status')return {item_count:completed?2:0,has_completed_cache:completed,downloading:false,observed_at:completed?'2026-11-13T12:00:00Z':null};
      if(command==='sync_page'){cursor++;completed=cursor>=2;return {has_more:!completed};}
      if(command==='export_market')return 'C:\\Users\\Fixture\\AppData\\Local\\team.twich.market\\exports\\twichui-market-v1-1.json';
      if(command==='reset_market'){cursor=0;return;}
      throw new Error(`Unexpected command ${command}`);
    }}};
  });
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  await page.getByLabel('Server address').fill('https://market.example');
  await page.getByLabel('Device token').fill('synthetic-token-not-a-real-credential');
  await page.getByRole('button',{name:'Connect securely'}).click();
  await page.getByText('Connected. Your device token is stored in Windows Credential Manager.').waitFor();
  assert.equal(await page.getByLabel('Device token').inputValue(),'');
  await page.getByRole('button',{name:'Synchronize',exact:true}).click();
  await page.getByText('Downloaded 2 pages. Synchronization complete.').waitFor();
  assert.equal(await page.locator('#count').textContent(),'2 item variants');
  await page.getByRole('button',{name:'Export JSON data'}).click();
  await page.getByText('Data-only JSON exported:',{exact:false}).waitFor();
  await page.screenshot({path:'/work/artifacts/companion-desktop.png',fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.getByRole('button',{name:'Disconnect',exact:true}).click();
  await page.getByText('Local credential removed.',{exact:false}).waitFor();
  assert(await page.getByRole('button',{name:'Synchronize',exact:true}).isDisabled());
  assert.deepEqual(errors,[]);
  await browser.close();
  await new Promise(resolve=>server.close(resolve));
  console.log('Companion UI workflows passed with explicitly mocked native IPC; no page errors.');
})().catch(error=>{console.error(error);process.exit(1)});
