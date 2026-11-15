"""Disposable real Python chat/recorder fixture for the native socket client tests."""
import json
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO/'src/marionette'))
import diagnostics
from clock_tool import GetCurrentTime
from connection import LocalConnection
from contacts import ContactProfiles
from contact_notes import ContactNotes
from conversation import Conversation
from soul import Soul
from storage import Store
import terminal


class SyntheticAPI:
    def __init__(self):
        self.closing = threading.Event()
        self.tools = ()
    def count(self, messages):
        return 10
    def prepare(self, messages):
        pass
    def reply(self, messages, reserve, on_delta=None):
        if on_delta:
            on_delta('reasoning', 'Synthetic private reasoning')
            on_delta('answer', 'Synthetic local reply.')
        return 'Synthetic local reply.', 'stop'


class CaptureOutput:
    def __init__(self, stream):
        self.buffer = stream
    def write(self, text):
        self.buffer.write(text.encode())
        return len(text)
    def flush(self):
        self.buffer.flush()
    def isatty(self):
        return False


def main():
    # Require a newly created disposable root; never open an existing profile.
    root = Path(sys.argv[1]).resolve()
    if not root.is_dir() or any(root.iterdir()):
        raise ValueError('The fixture needs an empty temporary directory.')
    (root/'session').mkdir()
    profiles = ContactProfiles(root/'contacts/profiles.json')
    soul = Soul(root/'soul/profile.json')
    notes = ContactNotes(root/'contact_notes')
    database = root/'conversations/marionette.sqlite3'
    store = Store(database)
    session = store.start()
    (root/'session/log-session.json').write_text(json.dumps({'session':session,'database':str(database),'generation':''}))
    api = SyntheticAPI()
    api.tools = (soul.bind(api),GetCurrentTime())
    conversation = Conversation(api,8192,profiles,profiles.profiles[0],notes,store,session,soul)
    children = []
    original_stdout, original_write = sys.stdout, diagnostics.write
    try:
        for stream in ('diagnostic','terminal'):
            children.append(subprocess.Popen([sys.executable,str(REPO/'src/marionette/storage.py'),str(database),
                'capture',session,stream],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE))
        diag, transcript = children
        diagnostics.write = lambda raw: (diag.stdin.write(raw),diag.stdin.flush())
        with LocalConnection(root/'session/chat.sock',conversation.submit_discord,diagnostics.log,
                             desktop_turn=conversation.submit_desktop):
            original_stdout.write('ready\n'); original_stdout.flush()
            sys.stdout = CaptureOutput(transcript.stdin)
            try:
                while True:
                    if not terminal.display_external(conversation):
                        time.sleep(.01)
            finally:
                api.closing.set()
                conversation.finish_preparation()
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.flush()
        sys.stdout, diagnostics.write = original_stdout, original_write
        for child in children:
            child.stdin.close()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait()
            child.stderr.close()
        store.close()


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    main()
