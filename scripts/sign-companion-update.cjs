// LOCAL OWNER HOST ONLY. Run with stdout/stderr redirected INSIDE a no-network
// rootless container, Docker --log-driver none, read-only key/input/passphrase
// mounts, bounded writable /signed and pinned Tauri CLI. Never run on GitHub.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
(async()=>{
  process.umask(0o077);
  if(process.env.TWICHUI_OWNER_SIGNING!=='authorized'||process.env.GITHUB_ACTIONS)throw new Error('Local owner signing only');
  const cli=require('/work/desktop/node_modules/@tauri-apps/cli');
  if(require('/work/desktop/node_modules/@tauri-apps/cli/package.json').version!=='2.12.4')throw new Error('Pinned Tauri CLI required');
  const sha=value=>crypto.createHash('sha256').update(value).digest('hex');
  const input='/input/candidate.json';if(fs.lstatSync(input).isSymbolicLink()||fs.statSync(input).size>16384)throw new Error('Invalid signing input');
  const candidate=JSON.parse(fs.readFileSync(input,'utf8'));
  const required=['schema_version','version','payload_source_commit','windows_run_id','backend_run_id','website_run_id','installer_artifact_id','installer_sha256','installer_bytes','executable_sha256','updater_public_key_sha256','ci'];
  if(Object.keys(candidate).sort().join()!==required.sort().join()||candidate.schema_version!==1||!/^2\.(0|[1-9][0-9]{0,3})\.(0|[1-9][0-9]{0,3})-beta\.[1-9][0-9]{0,3}$/.test(candidate.version))throw new Error('Explicit candidate identity required');
  const workflows={windows:'.github/workflows/desktop.yml',backend:'.github/workflows/backend.yml',website:'.github/workflows/web.yml'};
  for(const [name,workflow]of Object.entries(workflows)){
    const ci=candidate.ci?.[name];
    if(!ci||ci.repository!=='Twich-Team/TwichUI-Market'||ci.path!==workflow||ci.source_commit!==candidate.payload_source_commit||ci.status!=='completed'||ci.conclusion!=='success'||ci.id!==candidate[name+'_run_id'])throw new Error('Passed canonical source CI required');
  }
  const publicKey=fs.readFileSync('/keys/updater.key.pub','utf8').trim();
  if(sha(publicKey)!==candidate.updater_public_key_sha256||publicKey!==fs.readFileSync('/work/desktop/src-tauri/updater-public-key.txt','utf8').trim())throw new Error('Owner key differs from source/candidate');
  for(const field of ['installer_sha256','executable_sha256'])if(!/^[a-f0-9]{64}$/.test(candidate[field]))throw new Error('Invalid digest');
  if(!/^[a-f0-9]{40}$/.test(candidate.payload_source_commit)||!Number.isSafeInteger(candidate.installer_artifact_id)||candidate.installer_artifact_id<1)throw new Error('Invalid provenance');
  for(const name of ['/keys/updater.key','/recovery/updater-key.passphrase']){
    const stat=fs.lstatSync(name);if(!stat.isFile()||stat.isSymbolicLink()||(stat.mode&0o077)!==0||stat.uid!==process.getuid())throw new Error('Owner-only private material required');
  }
  const installer='/input/installer.exe';
  if(fs.lstatSync(installer).isSymbolicLink()||!Number.isSafeInteger(candidate.installer_bytes)||candidate.installer_bytes<1024||candidate.installer_bytes>64*1024*1024||fs.statSync(installer).size!==candidate.installer_bytes)throw new Error('Invalid bounded installer');
  const bytes=fs.readFileSync(installer);if(sha(bytes)!==candidate.installer_sha256||bytes.toString('ascii',0,2)!=='MZ')throw new Error('Installer changed');
  const output='/signed/'+candidate.version;
  fs.mkdirSync(output,{mode:0o700}); // Never overwrite a version or signed proof.
  const target=path.join(output,'TwichUI-Market-Companion-'+candidate.version+'-windows-x64.exe');
  fs.writeFileSync(target,bytes,{flag:'wx',mode:0o600});
  let password=fs.readFileSync('/recovery/updater-key.passphrase','utf8').trim();
  await cli.run(['signer','sign','--private-key-path','/keys/updater.key','--password',password,'--app-version',candidate.version,target],'tauri');
  password='';
  const signature=fs.readFileSync(target+'.sig','utf8').trim();
  if(signature.length<32||signature.length>4096||sha(fs.readFileSync(target))!==candidate.installer_sha256)throw new Error('Signing output differs');
  const {ci,...proof}=candidate;
  proof.updater_signature=signature;
  fs.writeFileSync(path.join(output,'signed-candidate.json'),JSON.stringify(proof,null,2)+'\n',{flag:'wx',mode:0o600});
})().catch(()=>{process.exitCode=1;});
