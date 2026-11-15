import json
import unittest
import threading
from http.server import BaseHTTPRequestHandler,HTTPServer
from market.probe import summarize, targets


class ProbeTests(unittest.TestCase):
    def test_authorized_requests_do_not_follow_redirects(self):
        from market.probe import request
        visited=[]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                visited.append(self.path)
                self.send_response(302)
                self.send_header('Location','/target')
                self.end_headers()
            def log_message(self,*args): pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            result,_=request(f'http://127.0.0.1:{server.server_port}/source',token='synthetic-secret')
            self.assertEqual(result['status'],302)
            self.assertEqual(visited,['/source'])
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)

    def test_trailing_slash_and_scoped_commodities(self):
        paths = targets(2, 113)
        self.assertIn('/data/wow/ruleset/2/auctions/', paths)
        self.assertEqual(paths[-1], '/data/wow/ruleset/2/auctions/113/commodities')

    def test_synthetic_summary(self):
        body = json.dumps({'auctions': [{'id': 1, 'item': {'id': 2}, 'quantity': 4, 'unit_price': 90}]}).encode()
        result = summarize(body)
        self.assertEqual(result['auctions_count'], 1)
        self.assertEqual(result['auction_fields'], ['id', 'item', 'quantity', 'unit_price'])
        self.assertNotIn('90', json.dumps(result))

    def test_empty_house_and_invalid_payload(self):
        self.assertEqual(summarize(b'{"id":112}'), {'keys': ['id']})
        with self.assertRaises(ValueError):
            summarize(b'[]')
