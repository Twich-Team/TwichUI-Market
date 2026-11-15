"""Compile trusted repository JSON schemas to a fixed Lua validation plan; never server input."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'contracts/bridge/v1'
def quoted(value):
    return '"'+''.join(chr(b) if 32<=b<127 and b not in (34,92) else '\\%03d'%b for b in value.encode())+'"'
def lua(value):
    if value is None:return 'J.NULL'
    if isinstance(value,bool):return 'true' if value else 'false'
    if isinstance(value,int):return str(value)
    if isinstance(value,str):return quoted(value)
    if isinstance(value,list):return 'setmetatable({'+','.join(lua(x) for x in value)+'},J.ARRAY)'
    return 'setmetatable({'+','.join('['+quoted(k)+']='+lua(v) for k,v in sorted(value.items()))+'},J.OBJECT)'
def generate(root=ROOT):
    names=['generation.schema.json','generation-schema2.schema.json']
    lines=['-- Generated from pinned trusted Market schemas. Regenerate; never edit independently.',
           'local W=TwichUI.Workshop','local J=W.BridgeCodec','W.BridgeSchemas={']
    for version,name in enumerate(names,1):
        raw=(root/name).read_bytes()
        lines+=['-- '+name+' SHA256 '+hashlib.sha256(raw).hexdigest(),'['+str(version)+']='+lua(json.loads(raw))+',']
    return '\n'.join(lines+['}',''])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.write_text(generate())
