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
                 b'0.02 D Parsed message: {"a":1,"a":2,"text":"' + b'long '*100 + b'"}\n', b'final partial line']
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

    def test_two_viewers_read_saved_files_and_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            owner = subprocess.Popen(['sleep', '0.4'])
            viewers = []
            try:
                for view in ['server', 'model']:
                    path = Path(directory) / (view + '.txt')
                    path.write_text('[event 00000001] initial\n')
                    viewers.append(subprocess.Popen(['bash', str(ROOT / 'scripts/native-linux/view-log.sh'), str(path), str(owner.pid), view], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
                    with path.open('a') as out:
                        out.write('[event 00000002] appended\n')
                owner.wait(timeout=3)
                for process in viewers:
                    stdout, stderr = process.communicate('\n', timeout=3)
                    self.assertEqual(process.returncode, 0, stderr)
                    self.assertIn('initial', stdout)
                    self.assertIn('appended', stdout)
                    self.assertIn('Chat ended.', stdout)
                self.assertEqual(len(list(Path(directory).iterdir())), 2)
            finally:
                if owner.poll() is None:
                    owner.kill(); owner.wait()
                for process in viewers:
                    if process.poll() is None:
                        process.kill(); process.wait()
