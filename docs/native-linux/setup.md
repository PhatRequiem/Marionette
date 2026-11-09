# Native Linux terminal chat

## Requirements and repeatable installation

Run from the Git checkout. This setup targets x86_64 Linux and Python 3.11 or newer (with tarfile extraction filters). The verified host uses Python 3.14.8 and Arch Linux. Runtime shared libraries: glibc, GCC runtime, OpenSSL 3, zlib, Brotli, Zstandard, Vulkan loader, and a working Vulkan driver. Logging also requires Bash, util-linux `script` (verified version 2.42.4), GNU coreutils, `xdg-terminal-exec`, and a configured desktop terminal. The verified default terminal is Kitty. Setup checks that the required commands exist. The host already provided these; no system packages or services were installed.

```bash
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

The setup downloads upstream llama.cpp's Vulkan binary release b12211 and Unsloth's Qwen3.5-4B Q4_K_M GGUF, derived from Qwen/Qwen3.5-4B. Exact URLs, model revision, and SHA-256 checksums are in `scripts/native-linux/downloads.json`. Downloads are verified before use. Setup verifies existing downloads and can recreate the runtime from its cached archive. It requires roughly 3 GB plus runtime/archive space and internet access on first installation. An interrupted model download is restarted on the next setup run.

The upstream prebuilt release avoids requiring a local compiler toolchain. This is a reproducible installation of pinned binaries, not a claim of reproducible compilation. To reinstall, rerun setup; to recreate on another machine, clone the project, satisfy the documented Linux requirements, and run the same setup. GPU driver compatibility must be checked on that machine.

## Operation

For everyday launch, chat, and exit commands, see [Chat in the terminal](chat.md).

The launcher resolves paths relative to itself and can be invoked from any directory. It runs the util-linux `script` recorder with `llama-completion` as its foreground child. A separate desktop terminal follows the current full debug log. No daemon, systemd unit, server command, or network listener is launched. The runtime archive also contains server programs, but this launcher uses direct inference in the completion executable.

- No personality file or custom system prompt is used; an inline text-only Qwen template formats role markers and an empty, closed thinking block. It adds no system message.
- Model context lasts only for this process. Dated transcripts are saved for the user; they are never fed back into the model. No memory database or cross-database migration exists.
- Chat uses `--offline`; no hosted API or login is needed.
- Each session has a shared timestamp and unique suffix with `-chat.txt` and `-debug.txt` endings under `data/conversations/`. The chat transcript captures echoed messages, replies, and CLI startup/status output. `--simple-io` preserves terminal input; terminal color codes, carriage returns, and backspaces may remain. Log formatting is unchanged.
- The debug file records session start/end times, exact launch arguments, runtime/recorder versions, and the exit status. llama.cpp runs with `--verbose --log-prefix --log-timestamps`, capturing all diagnostics exposed by this build, including model, device, memory, prompt, token, timing, and error details. Runtime timestamps are elapsed time; session headers give local time and UTC offset.
- The CLI stderr stream goes directly to the debug file inside the recorder, keeping verbose diagnostics out of the chat transcript. No `--log-file` duplication is needed. Bash command arguments are shell-quoted explicitly for the recorder; no new dependencies are added.
- Files use owner-only permissions and unique timestamped names. The chat recorder flushes each write, and the viewer follows the debug file until the launcher exits. Debug visibility follows the runtime logging flush behavior. Closing the viewer does not stop recording.
- `MARIONETTE_LOG_DIR` can select a separate directory for synthetic tests. The default directory is ignored by Git. Copy both matching text files to export or back them up; no special reader or database is required.
- Debug files can include full prompts and replies, local paths, and very large amounts of output. They are private local files, excluded from Git. No automatic deletion or rotation is configured. This enables the runtime’s fullest logging, not automatic crash backtraces. A forced kill or power loss may leave no ending footer.

The default device is Vulkan0, verified as the RX 7900 XT on this machine. Check device ordering after driver/hardware changes:

```bash
./scripts/native-linux/chat.sh --list-devices
```

Select another enumerated GPU with `MARIONETTE_DEVICE=Vulkan1 ./scripts/native-linux/chat.sh`. A CPU alternative is `MARIONETTE_DEVICE=none ./scripts/native-linux/chat.sh --gpu-layers 0`; CPU performance has not been benchmarked.

## Log storage and recovery

Keep the existing `data/conversations/` folder when updating or reinstalling. To restore logs, copy both backed-up `.txt` files for each session into that directory without overwriting newer files. Restoring files does not restore model context. A byte-for-byte copy and restore of a synthetic transcript is checked separately from inference; no cross-database migration is applicable.

## Choices and updates

Q4_K_M reduces the model download to 2,740,937,888 bytes with a quality tradeoff versus full precision. The 8,192-token context keeps memory use bounded. Reasoning is disabled for straightforward conversational replies; no character instructions are injected. No image projector is installed, so this setup is text-only.

When updating, change the download manifest, launcher paths, setup behavior if needed, license/version records, and these instructions together. Verify upstream checksums, reinstall, and test offline generation and interactive exit before committing. Models, runtime binaries, downloads, logs, and private data must stay out of Git.

## Runtime decision

Use `llama-completion` from the same pinned b12211 Vulkan archive. This executable loads and evaluates the model directly. In contrast, b12211 `llama-cli` starts an HTTP server thread, even with `--offline`; it is no longer launched by this project.

This completion build accepts `--reasoning off` but does not apply that setting in its interactive template call. The launcher therefore passes an inline Jinja text template preserving Qwen’s message markers and explicitly closing an empty thinking block before each reply. This is message formatting, not a personality or system prompt. It supports text conversation only, not tools, image inputs, or structured reasoning history.

Exit with Ctrl+D on an empty prompt. This runtime does not interpret `/exit` or `/clear`; restart for a new context. The launch command and paired log paths stay the same. Any chat already open during an upgrade continues using its old executable until exited and relaunched.

The download archive and its checksum are unchanged. The manifest identifies the selected completion executable, and setup verifies it after extraction. Rebuild by rerunning the setup command above.

## Verification

Verified using a separate temporary log directory and synthetic conversation: a request to remember “violet” returned “OK”, then a follow-up correctly returned “violet”. The actual input tokens contain the empty closed thinking block and no injected system message. Both replies were direct, with no reasoning text. Ctrl+D exited with status zero. Full GPU offload and an 8,192-token context were confirmed in the debug log.

While the completion process was running, host socket inspection showed no listener owned by it. The previously open user session still used the older CLI and its own listener; it was not interrupted by the test.

Paired chat/debug content, private permissions, log separation, and byte-identical copy/restore were checked. Same-format text restoration is verified; no database migration or persistent model memory is implemented. Setup was rerun using checksum-verified cached downloads, and shell syntax and the diff were checked.
