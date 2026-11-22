"""Bounded wire/lifecycle evidence for disposable performance HTTP fixtures only.

Does not log headers, bodies, query strings or credentials, change responses,
retry requests, or replace the event loop's exception reporting.
"""
import asyncio
import os
import time
from collections import deque


def run_fixture_server(server, sockets):
    """Use a socket-only loop for the disposable Windows HTTP server.

    CPython 3.12 Proactor shutdown can raise WinError10054 before socket close/
    server detach, leaving Server.wait_closed pending. No exceptions are hidden;
    native Windows clients and their connection/retry policies are unchanged.
    """
    if os.name == 'nt':
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            runner.run(server.serve(sockets=sockets))
    else:
        server.run(sockets=sockets)


class TransportTrace:
    def __init__(self, app):
        self.app = app
        self.events = deque(maxlen=2000)
        self.active = {}
        self.loop_errors = deque(maxlen=100)
        self.serial = 0

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            if scope['type'] == 'lifespan':
                loop = asyncio.get_running_loop()
                original = loop.get_exception_handler()

                def record_error(current, context):
                    self.loop_errors.append({'exception': type(context.get('exception')).__name__,
                                             'message': str(context.get('message', ''))[:160]})
                    if original:
                        original(current, context)
                    else:
                        current.default_exception_handler(context)

                loop.set_exception_handler(record_error)
            return await self.app(scope, receive, send)
        self.serial += 1
        key = self.serial
        started = time.perf_counter()
        event = {'id': key, 'path': scope['path'], 'method': scope['method'],
                 'client_port': (scope.get('client') or [None, None])[1],
                 'started': started, 'stage': 'application', 'body_bytes_sent': 0}
        self.active[key] = event

        async def transmit(message):
            if message['type'] == 'http.response.start':
                event['status'] = message['status']
                event['headers_ms'] = 1000 * (time.perf_counter() - started)
                event['stage'] = 'headers_send'
            elif message['type'] == 'http.response.body':
                event['stage'] = 'body_send'
            await send(message)
            if message['type'] == 'http.response.body':
                event['body_bytes_sent'] += len(message.get('body', b''))
                if not message.get('more_body', False):
                    event['stage'] = 'complete'

        try:
            await self.app(scope, receive, transmit)
        except BaseException as error:
            event['exception'] = type(error).__name__
            raise
        finally:
            event['elapsed_ms'] = 1000 * (time.perf_counter() - started)
            self.active.pop(key)
            self.events.append(event)

    def report(self):
        now = time.perf_counter()
        return {'requests': list(self.events), 'loop_errors': list(self.loop_errors),
                'in_flight': [{**event, 'elapsed_ms': 1000 * (now - event['started'])}
                              for event in self.active.copy().values()]}
