"""Local puppet controls reuse the checkout's existing desktop launcher."""
import os
from pathlib import Path
import subprocess

import diagnostics


class PuppetControl:
    def __init__(self, data, root=None):
        self.data = Path(data).resolve()
        self.root = Path(root) if root else Path(__file__).resolve().parents[2]

    def start(self):
        if not (self.root/'runtime/desktop-puppet/marionette-puppet').is_file():
            return 'Build the desktop puppet first: ' + str(self.root/'scripts/native-linux/desktop-puppet.sh') + ' build'
        return self._run('background')

    def stop(self):
        return self._run('stop')

    def _run(self, action):
        launcher = self.root/'scripts/native-linux/desktop-puppet.sh'
        try:
            result = subprocess.run([str(launcher), action],
                env=dict(os.environ, MARIONETTE_DATA_DIR=str(self.data)),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as error:
            diagnostics.log(f'Desktop puppet {action} failed: {type(error).__name__}.')
            return 'Desktop puppet control failed or timed out. Check ' + str(launcher) + ' status before retrying.'
        diagnostics.log(f'Desktop puppet {action}: launcher_status={result.returncode}.')
        if result.returncode:
            return 'Desktop puppet control did not complete; it may already be running or stopped. Check ' + str(launcher) + ' status.'
        if action == 'background':
            return 'Desktop puppet launch requested. Keep main chat running for replies.'
        return 'Desktop puppet stopped. Main chat is still running.'
