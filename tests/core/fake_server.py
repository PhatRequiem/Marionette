"""Synthetic HTTP runtime for launcher tests; never loads a model."""
import json
import signal
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

if '--version' in sys.argv:
    print('version: synthetic runtime')
    raise SystemExit
if '--test-fail' in sys.argv:
    print('synthetic startup failure', file=sys.stderr)
    raise SystemExit(7)
for arg in sys.argv[1:]:
    print(arg, file=sys.stderr, flush=True)
print('synthetic diagnostic', file=sys.stderr, flush=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, value):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(value).encode())

    def do_GET(self):
        self.respond({'default_generation_settings': {'n_ctx': 8192}} if self.path == '/props' else {'status': 'ok'})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path == '/apply-template':
            self.respond({'prompt': json.dumps(body['messages'])})
        elif self.path == '/tokenize':
            self.respond({'tokens': list(range(len(body['content'].split())))})
        elif self.path == '/v1/chat/completions':
            self.send_response(200)
            self.end_headers()
            event = {'choices': [{'delta': {'content': 'Synthetic reply.'}, 'finish_reason': 'stop'}]}
            self.wfile.write(('data: ' + json.dumps(event) + '\n\ndata: [DONE]\n\n').encode())
        else:
            self.send_error(404)


server = HTTPServer(('127.0.0.1', 0), Handler)
print('0.0 I llama_context: n_ctx_seq = 8192', file=sys.stderr, flush=True)
print(f'0.0 I srv server_on_li: listening on http://127.0.0.1:{server.server_port}', file=sys.stderr, flush=True)
print('0.0 I srv update_slots: all slots are idle', file=sys.stderr, flush=True)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
server.serve_forever()
