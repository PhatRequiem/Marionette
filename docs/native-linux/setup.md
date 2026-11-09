# Native Linux terminal chat

## Requirements and repeatable installation

Run from the Git checkout. This setup targets x86_64 Linux and Python 3.11 or newer with tarfile extraction filters (Python 3.12+ recommended). The verified host uses Python 3.14.8 and Arch Linux. Runtime shared libraries: glibc, GCC runtime, OpenSSL 3, zlib, Brotli, Zstandard, Vulkan loader, and a working Vulkan driver. Logging also requires Bash, util-linux `script` (verified version 2.42.4), GNU coreutils, `xdg-terminal-exec`, and a configured desktop terminal. The verified default terminal is Kitty. Setup checks that the required commands and extraction filters exist. The launcher also uses Python’s standard library to read runtime/model paths from the manifest. The host already provided these; no system packages or services were installed.

```bash
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

The setup downloads upstream llama.cpp's Vulkan binary release b12211 and Unsloth's Qwen3.5-4B Q4_K_M GGUF, derived from Qwen/Qwen3.5-4B. Exact URLs, model revision, and SHA-256 checksums are in `scripts/native-linux/downloads.json`. Downloads are verified before use. Setup verifies existing downloads and installed runtime files against the pinned archive without rewriting them. A new runtime is extracted into a staging directory and moved into place only after validation. Concurrent setup runs in the same checkout are rejected. It requires roughly 3 GB plus runtime/archive space and internet access on first installation. Downloads use temporary files and are published only after checksum verification. A failed download leaves any previous target intact; the next setup run restarts the download. A force-killed setup may leave an unused `.part` file.

The upstream prebuilt release avoids requiring a local compiler toolchain. This is a reproducible installation of pinned binaries, not a claim of reproducible compilation. To verify or complete installation, rerun setup; to recreate on another machine, clone the project, satisfy the documented Linux requirements, and run the same setup. GPU driver compatibility must be checked on that machine. If setup detects altered or missing files in an existing runtime, it stops rather than overwrite potentially running binaries. Close chats, move that version’s directory out of `runtime/llama.cpp/`, and rerun setup to restore it from the verified archive.

## Operation

For everyday launch, chat, and exit commands, see [Chat in the terminal](chat.md).

The launcher resolves paths relative to itself and can be invoked from any directory. It runs the util-linux `script` recorder with a Python session coordinator and `llama-completion` in the foreground. A separate desktop terminal follows the current full debug log. No daemon, systemd unit, server command, or network listener is launched. The runtime archive also contains server programs, but this launcher uses direct inference in the completion executable.

- No personality file is used. The coordinator builds a factual setup snapshot after loading and supplies it as system context with the first user message. See [startup context](startup-context.md) for evidence, timing, and limitations.
- Model context lasts only for this process. Dated transcripts are saved for the user; they are never fed back into the model. No memory database or cross-database migration exists.
- Chat uses `--offline`; no hosted API or login is needed.
- Each session has a shared timestamp and unique suffix with `-chat.txt`, `-debug.txt`, and (after successful loading) `-setup.json` endings under `data/conversations/`. The chat transcript captures echoed messages, replies, and CLI startup/status output. `--simple-io` preserves terminal input; terminal color codes, carriage returns, and backspaces may remain. Log formatting is unchanged.
- The debug file records session start/end times, exact launch arguments, runtime/recorder versions, and the exit status. llama.cpp runs with `--verbose --log-prefix --log-timestamps`, capturing all diagnostics exposed by this build, including model, device, memory, prompt, token, timing, and error details. Runtime timestamps are elapsed time; session headers give local time and UTC offset.
- The coordinator copies the runtime stderr stream into the debug file inside the recorder, keeping verbose diagnostics out of the chat transcript. No `--log-file` duplication is needed. Bash command arguments are shell-quoted explicitly for the recorder.
- Files use owner-only permissions and unique timestamped names. The chat recorder flushes each write, and the viewer follows the debug file until the launcher exits. Debug visibility follows the runtime logging flush behavior. Closing the viewer does not stop recording. A viewer launch failure is reported in the terminal and debug file while chat recording continues.
- `MARIONETTE_LOG_DIR` can select a separate directory for synthetic tests. The default directory is ignored by Git. Copy all matching text and JSON files to export or back them up; no special reader or database is required.
- Debug files can include full prompts and replies, local paths, and very large amounts of output. They are private local files, excluded from Git. No automatic deletion or rotation is configured. This enables the runtime’s fullest logging, not automatic crash backtraces. A forced kill or power loss may leave no ending footer.

The default device is Vulkan0, verified as the RX 7900 XT on this machine. Check device ordering after driver/hardware changes:

```bash
./scripts/native-linux/chat.sh --list-devices
```

Select another enumerated GPU with `MARIONETTE_DEVICE=Vulkan1 ./scripts/native-linux/chat.sh`. A CPU alternative is `MARIONETTE_DEVICE=none ./scripts/native-linux/chat.sh --gpu-layers 0`; CPU performance has not been benchmarked.

## Log storage and recovery

Keep the existing `data/conversations/` folder when updating or reinstalling. To restore logs, copy the backed-up `.txt` and `-setup.json` files for each session into that directory without overwriting newer files. Restoring files does not restore model context. A byte-for-byte copy and restore of a synthetic transcript is checked separately from inference; no cross-database migration is applicable.

## Choices and updates

Q4_K_M reduces the model download to 2,740,937,888 bytes with a quality tradeoff versus full precision. The 8,192-token context keeps memory use bounded. Reasoning is disabled for straightforward conversational replies; no character instructions are injected. No image projector is installed, so this setup is text-only.

When updating, change the download manifest, launcher paths, setup behavior if needed, license/version records, and these instructions together. Verify upstream checksums, reinstall, and test offline generation and interactive exit before committing. Models, runtime binaries, downloads, logs, and private data must stay out of Git.

## Runtime decision

Use `llama-completion` from the same pinned b12211 Vulkan archive. This executable loads and evaluates the model directly. In contrast, b12211 `llama-cli` starts an HTTP server thread, even with `--offline`; it is no longer launched by this project.

This completion build accepts `--reasoning off` but does not apply that setting in its interactive template call. The session coordinator therefore passes an inline Jinja text template preserving Qwen’s message markers and explicitly closing an empty thinking block before each reply. It also formats the generated setup report as a system message. The report supplies deployment facts, not personality instructions. It supports text conversation only, not tools, image inputs, or structured reasoning history.

Exit with Ctrl+D on an empty prompt. This runtime does not interpret `/exit` or `/clear`; restart for a new context. The launch command and paired log paths stay the same. Any chat already open during an upgrade continues using its old executable until exited and relaunched.

The download archive and its checksum are unchanged. The manifest identifies the selected completion executable, and setup verifies it after extraction. Rebuild by rerunning the setup command above.

## Verification

See [Baseline 1](baseline.md) for the authoritative checklist, repeatable test commands, and known limits.
