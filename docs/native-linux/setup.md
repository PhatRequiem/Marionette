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

The launcher resolves paths relative to itself and can be invoked from any directory. It runs the util-linux `script` recorder with a Python session coordinator and `llama-cli` in the foreground. Two separate desktop terminals follow the saved connections/requests and model-processing logs. The CLI starts an embedded HTTP server on `127.0.0.1` at a temporary port. It stops with the chat process; no separate daemon or systemd unit is installed. Other local programs can reach this endpoint while chat is running. It has no API authentication; do not expose it to the network. The address is saved in the connections/requests log and setup snapshot.

- No personality file is used. The coordinator builds a factual setup snapshot after loading and supplies it as system context with the first user message and again after `/clear`. See [startup context](startup-context.md) for evidence, timing, and limitations.
- Model context lasts only for this process. Dated transcripts are saved for the user; they are not automatically fed back into the model. No memory database or cross-database migration exists.
- Chat uses `--offline` for model loading; the loopback HTTP connection still operates. No hosted API or login is needed.
- Each session has a shared timestamp and unique suffix with `-chat.txt`, `-server.txt`, `-model.txt`, and (after successful loading) `-setup.json` endings under `data/conversations/`. The chat transcript captures echoed messages, replies, and CLI startup/status output. `--simple-io` preserves terminal input; terminal color codes, carriage returns, and backspaces may remain. The chat transcript format is unchanged.
- Both diagnostic files record session start/end times, exact launch arguments, runtime/recorder versions, and the exit status. llama.cpp runs with `--verbose --log-prefix --log-timestamps`, capturing all diagnostics exposed by this build, including model, device, memory, prompt, token, timing, and error details. Runtime timestamps are elapsed time; session headers give local time and UTC offset.
- The coordinator forwards the runtime stderr stream to one log router outside the recorder, keeping diagnostics out of the chat transcript. The router assigns a session-wide event number to each received line before routing it. No `--log-file` duplication is needed. Bash command arguments are shell-quoted explicitly for the recorder.
- Files use owner-only permissions and unique timestamped names. The chat recorder flushes each write, and each viewer follows its own saved file until the launcher exits. Debug visibility follows the runtime logging flush behavior. Closing the viewer does not stop recording. A viewer launch failure is reported in the launching terminal while chat recording continues.
- `MARIONETTE_LOG_DIR` can select a separate directory for synthetic tests. The default directory is ignored by Git. Copy all matching text and JSON files to export or back them up; no special reader or database is required.
- Diagnostic files can include full prompts and replies, local paths, and very large amounts of output. They are private local files, excluded from Git. No automatic deletion or rotation is configured. This enables the runtime’s fullest logging, not automatic crash backtraces. A forced kill or power loss may leave no ending footer.

### Reading the two diagnostic logs

`-server.txt` contains recognized connection, HTTP streaming, request queue, and response-delivery events. `-model.txt` contains recognized model loading, GPU, context, prompt, token, and timing events, including inference performed by server components. Unknown entries and all warning/error records go to both. Unprefixed continuation lines are also shared so they cannot be silently misclassified. Classification is tied to the pinned runtime; unfamiliar formats fall back to both files.

Every received line gets `[event 00000001]` followed by an ISO timestamp with microseconds and UTC offset, then a readable message block retaining the runtime's elapsed timestamp. The added timestamp is receipt time, not the time the runtime generated the event. Identical shared entries carry identical numbers and timestamps. Numbers restart each session; gaps within one file mean events routed only to the other file. Compare the two files by event number to recover their combined receipt order. This is line order, not a claim of exact execution order across runtime threads.

Messages appear below their event header on `    | ` continuation rows, wrapped at 140 characters. JSON punctuation outside strings starts a new row; values are not parsed, rounded, truncated, or deduplicated. Blank input lines are explicitly marked `[blank line]`. Control bytes are displayed as `\xHH` (for example `\x1b` for Escape and `\x08` for backspace), and literal backslashes are doubled. This retains the codes without allowing them to alter the terminal display. To recover an original message, concatenate its continuation rows without their prefixes or added line breaks, decode those escapes, and restore its final newline unless the header says `[no final newline]`. Shared events use identical formatting in both files. Existing session files are not rewritten; the new format applies on the next launch.

There is no third raw debug file or filtered temporary log. The launcher waits for the router to finish writing before exiting. Older `-debug.txt` files remain untouched. Export all four matching session files together; nothing automatically deletes or rotates them.

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

Use `llama-cli` from the same pinned b12211 Vulkan archive. It manages terminal chat and starts the llama.cpp server in a thread in the same process. The prior direct-inference choice was based on excluding HTTP listeners; the intended requirement is now local operation with nothing left serving after chat exits.

The existing session coordinator supplies its observed setup report through the first-turn text-only Qwen template. It retains the empty closed thinking block and does not add a personality file. Native `/exit`, `/clear`, `/regen`, `/read`, and `/glob` commands remain available; after `/clear`, the next message receives the startup report again. The model itself has no tools to open files.

The context remains 8,192 tokens. Switching to the server does not implement automatic history trimming or guarantee preservation at context exhaustion. The proposed extra 500 tokens and requested-versus-loaded comparison remain unimplemented; these are separate changes.

The archive, model, and checksums are unchanged. The manifest now selects `llama-cli`, and setup verifies it after extraction. Rebuild using the same setup command. Existing chats continue using the old executable until exited and relaunched.

## Verification

Run `python -m unittest discover -s tests/native-linux -v` and `bash -n scripts/native-linux/chat.sh scripts/native-linux/view-log.sh`. The tests use synthetic data. Baseline 1 remains a historical direct-inference checkpoint.

The local-server switch was checked with an isolated real GPU session: synthetic word recall, setup context after `/clear`, full debug logging, loopback-only listening, `/exit` with status zero, and disappearance of both the runtime process and listener. Check the current listener with `ss -lntp` while chatting; only `127.0.0.1:<temporary port>` should belong to this `llama-cli` process.
