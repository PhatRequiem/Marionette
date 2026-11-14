"""Terminal-owned Discord lifecycle; reuse the existing bot and durable recorder."""
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import threading

import diagnostics


class DiscordControl:
    def __init__(self, data, address, database, session, root=None):
        self.data, self.address = Path(data), address
        self.database, self.session = database, session
        self.root = Path(root) if root else Path(__file__).resolve().parents[2]
        self.bot = self.recorder = self.watcher = None
        self.on_setup_change = None

    def start(self):
        if self.watcher and self.watcher.is_alive():
            return 'Discord is already running or finishing shutdown.'
        python = self.root/'runtime/discord/bin/python'
        if not python.is_file():
            return 'Run ./scripts/native-linux/setup-discord.sh first.'
        if not self.address or not Path(self.address).is_socket() or not self.database or not self.session:
            return 'Discord requires a running chat connection and logging session.'
        directory = self.data/'discord'
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock = (directory/'.connection.lock').open('a')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close()
            return 'Discord is already connected or starting.'
        environment = dict(os.environ, MARIONETTE_DATA_DIR=str(self.data.resolve()))
        bot_command = [str(python), '-u', str(self.root/'src/marionette/discord_bot.py')]
        try:
            checked = subprocess.run(bot_command+['--check-config'], env=environment,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            if checked.returncode:
                lock.close()
                return 'Discord configuration is invalid. Check the active data directory’s discord/.env.'
            self.bot = subprocess.Popen(bot_command, env=environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True, pass_fds=(lock.fileno(),))
            try:
                self.recorder = subprocess.Popen([str(python), '-u', str(self.root/'src/marionette/storage.py'),
                    str(self.database), 'capture', self.session, 'discord'], stdin=self.bot.stdout,
                    stdout=subprocess.DEVNULL, start_new_session=True)
            except BaseException:
                self.bot.terminate()
                try:
                    self.bot.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.bot.kill()
                    self.bot.wait()
                raise
            finally:
                self.bot.stdout.close()
        except subprocess.TimeoutExpired as error:
            lock.close()
            raise RuntimeError('Discord configuration check timed out.') from error
        except BaseException:
            lock.close()
            raise
        bot, recorder = self.bot, self.recorder
        def finished():
            try:
                bot_code = bot.wait()
                recorder_code = recorder.wait()  # Drain final records before releasing the connection lock.
                diagnostics.log(f'Discord background stopped: bot_status={bot_code}; recorder_status={recorder_code}.')
            finally:
                lock.close()
                if self.on_setup_change:
                    self.on_setup_change()
        self.watcher = threading.Thread(target=finished, daemon=True)
        self.watcher.start()
        diagnostics.log('Discord background starting; connection status appears in Connections and requests.')
        return 'Discord is starting. Watch Connections and requests for Discord ready.'

    def stop(self):
        if self.watcher and self.watcher.is_alive():
            if self.bot.poll() is None:
                try:
                    self.bot.send_signal(signal.SIGINT)
                except ProcessLookupError:
                    pass
            self.watcher.join(15)
            if self.watcher.is_alive():
                if self.bot.poll() is None:
                    self.bot.kill()
                self.watcher.join(15)
            if self.watcher.is_alive():
                raise RuntimeError('Discord shutdown is still draining; check connection logs before restarting.')
            if self.recorder.returncode:
                raise RuntimeError('Discord stopped, but its recorder failed; saved logs may be incomplete.')
            return 'Discord stopped. Marionette is still running.'
        # The foreground launcher uses the same bot control endpoint and lock.
        from operator_status import request_stop
        if self.address and request_stop(self.address):
            return 'Discord disconnect requested. Watch Connections and requests for shutdown.'
        return 'Discord is not running, or its control connection is unavailable.'

    def observed_state(self):
        from operator_status import probe
        if self.address and probe(self.address):
            return 'Running'
        if self.bot is not None:
            code = self.bot.poll()
            if code is None:
                return 'Starting (process alive)'
            return 'Stopped' if code == 0 else 'Stopped after process failure'
        return 'Not observed running'

    def close(self):
        if self.watcher and self.watcher.is_alive():
            # After the chat socket closes, the bot watcher lets a final shutdown
            # acknowledgement finish before disconnecting itself.
            self.watcher.join(10)
            if self.watcher.is_alive():
                self.stop()
