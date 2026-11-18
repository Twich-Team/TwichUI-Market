// Minimal installed native IPC/frontend smoke; no server, credentials or game writes.
const fs = require('node:fs');
async function main() {
  let targets;
  for (let n=0;n<100;n++) {
    try { targets=await (await fetch(`http://127.0.0.1:${process.env.DEV_CDP_PORT}/json/list`)).json(); if(targets.some(t=>t.type==='page')) break; } catch {}
    await new Promise(r=>setTimeout(r,200));
  }
  const target=targets?.find(t=>t.type==='page'); if(!target)throw Error('Installed WebView frontend did not start');
  const ws=new WebSocket(target.webSocketDebuggerUrl); await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  let id=0;const pending=new Map();
  ws.onmessage=({data})=>{const v=JSON.parse(String(data));if(v.id){const p=pending.get(v.id);pending.delete(v.id);v.error?p.reject(Error(v.error.message)):p.resolve(v.result);}};
  const call=(method,params)=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params}));});
  try {
    const response=await call('Runtime.evaluate',{awaitPromise:true,returnByValue:true,expression:`(async()=>{
      if(!document.querySelector('h1')?.textContent.includes('DEV'))throw Error('Real DEV frontend missing');
      if(!document.querySelector('#workshop-connect'))throw Error('Workshop control missing');
      const invoke=window.__TAURI__.core.invoke;
      const state=await invoke('app_state');
      if(!state.version.includes('DEV '+${JSON.stringify(process.env.COMPANION_DEV_SHA)}))throw Error('Native source identity mismatch');
      let failure;try{await invoke('prepare_workshop');throw Error('Fresh DEV unexpectedly connected');}catch(e){failure=JSON.parse(String(e));}
      if(failure.code!=='context_changed')throw Error('Workshop native command missing or unexpected result');
      const updates=await invoke('check_update');if(updates.status!=='unavailable'||!updates.message.includes('disabled'))throw Error('DEV updater not disabled');
      let installDisabled=false;try{await invoke('install_update',{version:'999.0.0'});}catch(e){installDisabled=String(e).includes('disabled');}
      if(!installDisabled)throw Error('DEV update installation not disabled');
      const diagnostic=await invoke('save_diagnostics');
      return {version:state.version,diagnostic,frontend:true,native:true,workshop_command:true,updater_disabled:true};
    })()`});
    if(response.exceptionDetails)throw Error(JSON.stringify(response.exceptionDetails));
    const value=response.result.value;
    if(!value.diagnostic.replaceAll('\\','/').includes('/team.twich.market.dev/'))throw Error('DEV storage is not isolated');
    const diagnostic=JSON.parse(fs.readFileSync(value.diagnostic,'utf8'));
    if(diagnostic.workshop_setup?.code!=='context_changed')throw Error('Native diagnostics dropped the setup failure');
    delete value.diagnostic; fs.writeFileSync('artifacts/companion-dev/smoke.json',JSON.stringify(value,null,2));
    console.log('Installed DEV frontend, native IPC, Workshop command, isolated diagnostics and disabled updater passed.');
  } finally {ws.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
