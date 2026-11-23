"""Test-only adapter to the native ignored-test publisher; never a release bypass.

The executable is a cargo --lib test binary. Unix executable identity is supplied
by the pre-existing cfg(test) synthetic Forever hook; all download, ownership,
validation, artifact generation, readback and atomic publication code is production.
"""
import json,os,shutil,subprocess
from pathlib import Path

CAP_FIELDS=('prepared_current_version','prepared_current_partitions','prepared_current_part_bytes','prepared_current_total_bytes')

def installation(base,addon,count,containers=False):
    assert base.name.startswith('prepared-fixture-') and not (base/'game').exists()
    game=base/'game';addons=game/'Interface/AddOns';addons.mkdir(parents=True,mode=0o700)
    for name,files in {'!!!TwichUI':['!!!TwichUI.toc'],'TwichUI_Workshop':['TwichUI_Workshop.toc','MarketDelivery.json','Summary.lua','Bridge.lua','Prepared.lua']}.items():
        destination=addons/name;destination.mkdir()
        for file in files:shutil.copyfile(addon/name/file,destination/file)
    if (addon/'TwichUI_Workshop/Containers.lua').exists():shutil.copyfile(addon/'TwichUI_Workshop/Containers.lua',addons/'TwichUI_Workshop/Containers.lua')
    cap=addons/'TwichUI_Workshop/MarketDelivery.json';value=json.loads(cap.read_text())
    assert value['prepared_current_version']==1
    if not containers:
        for key in ('container_packaging_version','container_codec','container_block_bytes','current_containers','history_containers'):value.pop(key,None)
    else:assert count==32 and value['container_packaging_version']==1
    if count is None:
        for key in CAP_FIELDS:value.pop(key)
    else:value['prepared_current_partitions']=count
    cap.write_text(json.dumps(value))
    (game/'Wow.exe').write_bytes(b'TWICHUI SYNTHETIC FOREVER 1.60.1')
    saved=game/'WTF/Account/SyntheticOnly/SavedVariables';saved.mkdir(parents=True)
    (saved/'TwichUI.lua').write_bytes(b'unchanged synthetic player data')
    return game

def run(binary,base,config,env=None):
    path=base/'driver.json';path.write_text(json.dumps(config))
    environment=dict(os.environ,**(env or {}),TWICHUI_PREPARED_TEST_CONFIG=str(path))
    proc=subprocess.run([str(binary.resolve()),'workshop_summary::tests::prepared_pipeline_offline_driver','--exact','--ignored','--nocapture'],env=environment,text=True,capture_output=True,timeout=300)
    if proc.returncode:raise RuntimeError('Native disposable publisher failed: '+proc.stderr[:1800])
    return json.loads((base/'result.json').read_text())
