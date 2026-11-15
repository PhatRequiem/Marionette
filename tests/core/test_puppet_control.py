"""Puppet commands call only a synthetic launcher with an isolated data root."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src/marionette'))
from puppet_control import PuppetControl


class PuppetControlTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)/'checkout with spaces'
        self.data = self.root/'alternate data'
        self.data.mkdir(parents=True)
        self.launcher = self.root/'scripts/native-linux/desktop-puppet.sh'
        self.launcher.parent.mkdir(parents=True)
        self.launcher.write_text('#!/bin/sh\nprintf "%s\\n%s\\n" "$1" "$MARIONETTE_DATA_DIR" > "$MARIONETTE_DATA_DIR/request.txt"\n')
        self.launcher.chmod(0o700)
        self.binary = self.root/'runtime/desktop-puppet/marionette-puppet'
        self.binary.parent.mkdir(parents=True)
        self.binary.touch()
        self.control = PuppetControl(self.data, self.root)
        self.enterContext(patch('diagnostics.log'))

    def test_launcher_receives_action_and_current_data_root(self):
        for method, action, answer in ((self.control.start, 'background', 'launch requested'),
                                       (self.control.stop, 'stop', 'Main chat is still running')):
            self.assertIn(answer, method())
            self.assertEqual((self.data/'request.txt').read_text().splitlines(), [action, str(self.data)])

    def test_missing_build_explains_setup_without_launching(self):
        self.binary.unlink()
        self.assertIn(str(self.launcher)+' build', self.control.start())
        self.assertFalse((self.data/'request.txt').exists())

    def test_launch_errors_do_not_claim_success(self):
        self.launcher.write_text('#!/bin/sh\nexit 1\n')
        self.assertIn('did not complete', self.control.start())
        for error in (subprocess.TimeoutExpired('synthetic', 30), OSError('synthetic')):
            with patch('puppet_control.subprocess.run', side_effect=error):
                self.assertIn('failed or timed out', self.control.start())
