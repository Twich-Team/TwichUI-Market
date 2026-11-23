"""Focused loopback transport experiment; never substitutes for the full benchmark.

Keepalive and announced-close controls share the same native client and bytes.
An expired pooled connection is closed as its next request arrives, before ASGI.
This is deterministic fault injection, distinct from the natural Windows failure.
"""
import argparse
import asyncio
import json
import socket
import subprocess
import threading
import time
from pathlib import Path
import uvicorn
from uvicorn.protocols.http.h11_impl import H11Protocol

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--client',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--cycles',type=int,default=3)
a=p.parse_args()
reports=[]
for close in (False,True):
    idle=[]
    class Protocol(H11Protocol):
        retire=False
        def on_response_complete(self):
            self.retire=self.scope.get('path')=='/summary'
            super().on_response_complete()
        def data_received(self,data):
            if self.retire and not self.transport.is_closing():
                idle.append({'client_port':self.client[1], 'at':time.perf_counter()})
                self.transport.close()
                return
            super().data_received(data)
    async def app(scope,receive,send):
        if scope['type']=='lifespan':
            while True:
                message=await receive()
                if message['type']=='lifespan.startup':await send({'type':'lifespan.startup.complete'})
                else:await send({'type':'lifespan.shutdown.complete'});return
        preparing=scope['path']=='/summary'
        raw=b'{"state":"preparing"}' if preparing else b'{}'
        headers=[(b'content-length',str(len(raw)).encode())]
        if preparing and close:headers.append((b'connection',b'close'))
        await send({'type':'http.response.start','status':202 if preparing else 200,'headers':headers})
        await send({'type':'http.response.body','body':raw})
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,http=Protocol,
                                      access_log=False,log_level='error'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    for _ in range(1000):
        if server.started:break
        time.sleep(.01)
    else:raise RuntimeError('Probe startup deadline')
    try:
        result=subprocess.run([str(a.client.resolve()),f'http://127.0.0.1:{port}',str(a.cycles),'100'],
                              capture_output=True,text=True,timeout=120)
        if result.returncode:raise RuntimeError(result.stderr)
        report=json.loads(result.stdout);report.update(connection_close=close,idle_closes=len(idle))
        reports.append(report)
    finally:
        server.should_exit=True;thread.join(timeout=10)
        if thread.is_alive():raise RuntimeError('HTTP probe server failed to stop')
assert not reports[0]['ok'] and reports[0]['stage']=='next-bootstrap', 'Negative control must reproduce the pre-application request failure'
assert reports[1]['ok'], 'Explicit preparation close must not fail native requests'
a.out.parent.mkdir(parents=True,exist_ok=True)
a.out.write_text(json.dumps({'synthetic':True,'production':False,'fault_injected_expired_pool_connection':True,
                            'keepalive_failure_reproduced':not reports[0]['ok'],'runs':reports},indent=2)+'\n')
print(json.dumps(reports))
