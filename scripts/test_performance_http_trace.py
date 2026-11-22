"""Fast fixture-observability invariants; no database or network required."""
import unittest
from performance_http_trace import TransportTrace


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
