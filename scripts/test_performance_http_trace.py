"""Fast fixture-observability invariants; no database or network required."""
import unittest
import asyncio
import os
import socket
import struct
import threading
import time
from performance_http_trace import TransportTrace, run_fixture_server


class WireTraceTest(unittest.IsolatedAsyncioTestCase):
    async def test_response_not_complete_until_last_body_send(self):
        holder = {}
        async def app(scope, receive, send):
            await send({'type': 'http.response.start', 'status': 202, 'headers': []})
            self.assertNotEqual(next(iter(holder['trace'].active.values()))['stage'], 'complete')
            await send({'type': 'http.response.body', 'body': b'private', 'more_body': True})
            await send({'type': 'http.response.body', 'body': b'data', 'more_body': False})
        trace = holder['trace'] = TransportTrace(app)
        sent = []
        async def send(message):
            sent.append(message)
        await trace({'type': 'http', 'method': 'GET', 'path': '/fixture',
                     'headers': [(b'authorization', b'private-token')]}, None, send)
        event = trace.report()['requests'][0]
        self.assertEqual(event['stage'], 'complete')
        self.assertEqual(event['body_bytes_sent'], 11)
        self.assertEqual(len(sent), 3)
        self.assertFalse(trace.active)
        self.assertNotIn('private', str(trace.report()))


class FixtureLifecycleTest(unittest.IsolatedAsyncioTestCase):
    def test_abrupt_client_resets_still_close_server_and_detach_sockets(self):
        import uvicorn
        async def app(scope, receive, send):
            if scope['type']=='lifespan':
                while True:
                    message=await receive()
                    if message['type']=='lifespan.startup':
                        await send({'type':'lifespan.startup.complete'})
                    else:
                        await send({'type':'lifespan.shutdown.complete'});return
            await send({'type':'http.response.start','status':200,'headers':[(b'content-length',b'8192')]})
            await asyncio.sleep(.01)
            await send({'type':'http.response.body','body':b'x'*8192})
        trace=TransportTrace(app)
        listener=socket.socket();listener.bind(('127.0.0.1',0))
        server=uvicorn.Server(uvicorn.Config(trace,access_log=False,log_level='error'))
        thread=threading.Thread(target=run_fixture_server,args=(server,[listener]),daemon=True)
        thread.start()
        try:
            deadline=time.monotonic()+5
            while not server.started and time.monotonic()<deadline:time.sleep(.005)
            self.assertTrue(server.started)
            for _ in range(20):
                with socket.create_connection(listener.getsockname(),timeout=2) as client:
                    client.sendall(b'GET /reset HTTP/1.1\r\nHost: localhost\r\n\r\n')
                    self.assertTrue(client.recv(128).startswith(b'HTTP/1.1 200'))
                    client.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('HH' if os.name=='nt' else 'ii',1,0))
        finally:
            server.should_exit=True;thread.join(timeout=5)
        self.assertFalse(thread.is_alive(),'reset sockets leaked the HTTP server lifecycle')
        self.assertFalse(trace.active)
        self.assertFalse(trace.loop_errors,'background transport exceptions must remain visible')

    async def test_send_exception_is_preserved_and_recorded(self):
        async def app(scope, receive, send):
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        async def send(message):
            raise ConnectionResetError('fixture reset')
        trace = TransportTrace(app)
        with self.assertRaises(ConnectionResetError):
            await trace({'type': 'http', 'method': 'GET', 'path': '/fixture'}, None, send)
        self.assertEqual(trace.events[0]['exception'], 'ConnectionResetError')
        self.assertFalse(trace.active)


if __name__ == '__main__':
    unittest.main()
