// Invoke the supported pinned Tauri CLI in-process so the password never enters
// process arguments. Run only with stdout/stderr redirected inside the container
// and Docker logging disabled; Tauri's generate command can print private data.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const cli=require('/work/desktop/node_modules/@tauri-apps/cli');
(async()=>{
  if(process.env.TWICHUI_OWNER_KEYGEN!=='authorized'||process.env.GITHUB_ACTIONS==='true')throw new Error('Explicit local owner key operation required');
  process.umask(0o077);
  const key='/keys/updater.key',pub=key+'.pub',passwordPath='/recovery/updater-key.passphrase';
  const complete=[key,pub,passwordPath].every(name=>fs.existsSync(name));
  if(!complete&&[key,pub,passwordPath].some(name=>fs.existsSync(name)))throw new Error('Partial key state retained; never overwrite it');
  let password;
  if(complete){
    for(const name of [key,pub,passwordPath])if(fs.lstatSync(name).isSymbolicLink())throw new Error('Key files must not be symlinks');
    password=fs.readFileSync(passwordPath,'utf8').trim();
  }else{
    password=crypto.randomBytes(48).toString('base64url');
    fs.writeFileSync(passwordPath,password+'\n',{mode:0o600,flag:'wx'});
    await cli.run(['signer','generate','--ci','--password',password,'--write-keys',key],'tauri');
    for(const name of [key,pub,passwordPath])fs.chmodSync(name,0o600);
  }
  const probe='/keys/recovery-check.txt';
  if(!fs.existsSync(probe))fs.writeFileSync(probe,'TwichUI Market updater key recovery check. This is not an installer.\n'.padEnd(1024,'.'),{mode:0o600,flag:'wx'});
  await cli.run(['signer','sign','--private-key-path',key,'--password',password,'--app-version','2.0.0',probe],'tauri');
  const publicKey=fs.readFileSync(pub,'utf8').trim();
  if(!publicKey||publicKey.length>4096||!fs.existsSync(probe+'.sig'))throw new Error('Supported signer did not create the expected key/proof');
  const record={schema_version:1,public_key_sha256:crypto.createHash('sha256').update(publicKey).digest('hex'),
    tool:'@tauri-apps/cli 2.12.4 signer generate/sign',encrypted_private_key:true,password_in_process_memory_only:true,
    private_key_outside_git:true,dedicated_owner_key:true,existing_key_reused:complete,checked_at:new Date().toISOString()};
  fs.writeFileSync('/keys/public-metadata.json',JSON.stringify(record,null,2)+'\n',{mode:0o600});
  for(const name of [key,pub,passwordPath]){const fd=fs.openSync(name,'r');try{fs.fsyncSync(fd);}finally{fs.closeSync(fd);}}
  password='';
})().catch(()=>{process.exitCode=1;});
