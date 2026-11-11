"""Check that routing preserves evidence and viewers finish with the chat."""
import importlib.util
import io
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('router', ROOT / 'src/marionette/log_router.py')
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)


class LogTests(unittest.TestCase):
    def test_no_lines_lost_and_shared_events_identical(self):
        lines = [b'0.01.253.519 I srv server_on_li: listening on http://127.0.0.1:1234\n',
                 b'0.01.253.520 D srv decode: processing tokens\n',
                 b'0.01.253.521 E srv send_error: context full\n',
                 b'0.01.253.522 W llama_context: warning\n',
                 b'0.01.253.523 I future_component: new message\n',
                 b'continuation with \xff original byte\n', b'\n', b'\x1b[32mcolored\x1b[0m backspace\b slash\\\n',
                 b'0.02 D Parsed message: {"a":1,"a":2,"text":"' + b'long '*100 + b'"}\n', b'Client: [message discord:1234] [request 01] ---------- MODEL REQUEST START ----------\n',
                 b'Client: [message discord:1234] [request 01] [tool 01] ---------- TOOL CALL END | returned ----------\n',
                 b'final partial line']
        server, model = io.BytesIO(), io.BytesIO()
        router.route(io.BytesIO(b''.join(lines)), server, model)
        def events(output):
            result = {}
            blocks = re.split(rb'(?=^\[event )', output.getvalue(), flags=re.M)
            for block in blocks:
                if not block:
                    continue
                header, *rows = block.splitlines(keepends=True)
                match = re.match(rb'\[event (\d+)\]', header)
                self.assertIsNotNone(match)
                if b'[blank line]' in header:
                    original = b'\n'
                else:
                    visible = b''.join(row.removeprefix(b'    | ').removesuffix(b'\n') for row in rows)
                    original = re.sub(rb'\\(\\|x[0-9a-f]{2})', lambda m: b'\\' if m[1] == b'\\' else bytes([int(m[1][1:], 16)]), visible)
                    if b'[no final newline]' not in header:
                        original += b'\n'
                result[int(match[1])] = (block, original)
            return result
        a, b = events(server), events(model)
        self.assertEqual(set(a) | set(b), set(range(1, len(lines)+1)))
        self.assertNotIn(1, b)
        self.assertNotIn(2, a)
        for number in range(3, 9):
            self.assertEqual(a[number], b[number])
        for number, (_, text) in (a | b).items():
            self.assertEqual(text, lines[number-1])

    def test_two_database_viewers_stop_when_session_ends(self):
        import sys
        sys.path.insert(0, str(ROOT / 'src/marionette'))
        from storage import Store
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'logs.sqlite3'
            store = Store(path)
            session = store.start()
            store.event(session, 'diagnostic', b'initial\n')
            viewers = []
            try:
                for view in ['server', 'model']:
                    viewers.append(subprocess.Popen(['bash', str(ROOT / 'scripts/native-linux/view-log.sh'), str(path), session, view], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
                store.event(session, 'diagnostic', b'appended\n')
                store.end(session)
                for process in viewers:
                    stdout, stderr = process.communicate('\n', timeout=5)
                    self.assertEqual(process.returncode, 0, stderr)
                    self.assertIn('initial', stdout)
                    self.assertIn('appended', stdout)
                    self.assertIn('Chat ended.', stdout)
            finally:
                store.close()
                for process in viewers:
                    if process.poll() is None:
                        process.kill(); process.wait()


if __name__ == '__main__':
    unittest.main()
