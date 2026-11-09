# Native Linux terminal chat

## Requirements and repeatable installation

Run from the Git checkout. This setup targets x86_64 Linux and Python 3.11 or newer with tarfile extraction filters (Python 3.12+ recommended). The verified host uses Python 3.14.8 and Arch Linux. Runtime shared libraries: glibc, GCC runtime, OpenSSL 3, zlib, Brotli, Zstandard, Vulkan loader, and a working Vulkan driver. Logging also requires Bash, util-linux `script` (verified version 2.42.4), GNU coreutils, `xdg-terminal-exec`, and a configured desktop terminal. The verified default terminal is Kitty. Setup checks that the required commands and extraction filters exist. The launcher also uses Python’s standard library to read runtime/model paths from the manifest. The host already provided these; no system packages or services were installed.

```bash
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

The setup downloads upstream llama.cpp's Vulkan binary release b12211 and Unsloth's Qwen3.5-4B Q4_K_M GGUF, derived from Qwen/Qwen3.5-4B. Exact URLs, model revision, and SHA-256 checksums are in `scripts/native-linux/downloads.json`. Downloads are verified before use. Setup verifies existing downloads and installed runtime files against the pinned archive without rewriting them. A new runtime is extracted into a staging directory and moved into place only after validation. Concurrent setup runs in the same checkout are rejected. It requires roughly 3 GB plus runtime/archive space and internet access on first installation. Downloads use temporary files and are published only after checksum verification. A failed download leaves any previous target intact; the next setup run restarts the download. A force-killed setup may leave an unused `.part` file.

The upstream prebuilt release avoids requiring a local compiler toolchain. This is a reproducible installation of pinned binaries, not a claim of reproducible compilation. To verify or complete installation, rerun setup; to recreate on another machine, clone the project, satisfy the documented Linux requirements, and run the same setup. GPU driver compatibility must be checked on that machine. If setup detects altered or missing files in an existing runtime, it stops rather than overwrite potentially running binaries. Close chats, move that version’s directory out of `runtime/llama.cpp/`, and rerun setup to restore it from the verified archive.

## Source layout

Application code lives in `src/marionette/`: `session.py` owns chat and the local server, and `log_router.py` formats and routes diagnostics. The Bash launcher invokes these files by absolute path, so no Python package installation or working-directory change is needed.

`scripts/native-linux/` contains operational entry points: `setup.py`, `chat.sh`, and `view-log.sh`. The pinned `downloads.json` stays beside setup. Tests live in `tests/native-linux/`; runtime binaries and private data remain outside source under `runtime/` and `data/`. Use the same setup and launch commands after moving or cloning the complete checkout.

## Operation

For everyday launch, chat, and exit commands, see [Chat in the terminal](chat.md).

The launcher resolves paths relative to itself and can be invoked from any directory. It runs the util-linux `script` recorder with a Python terminal client and `llama-server` in the foreground. Two separate desktop terminals follow the saved connections/requests and model-processing logs. The client starts its own HTTP server process on `127.0.0.1` at a temporary port. It stops with the chat process; no separate daemon or systemd unit is installed. Other local programs can reach this endpoint while chat is running. It has no API authentication; do not expose it to the network. The address is saved in the connections/requests log.

- No personality file or generated setup report is used. See [context rollover](context.md) for preparation, budgeting, and failure behavior.
- Model context lasts only for this process. Dated transcripts are saved for the user; they are not automatically fed back into the model. No memory database or cross-database migration exists.
- Chat uses `--offline` for model loading; the loopback HTTP connection still operates. No hosted API or login is needed.
- Each session has a shared timestamp and unique suffix with `-chat.txt`, `-server.txt`, and `-model.txt` endings under `data/conversations/`. The chat transcript captures echoed messages, replies, and CLI startup/status output. Terminal color codes, carriage returns, and backspaces may remain.
- Both diagnostic files record session start/end times, exact launch arguments, runtime/recorder versions, and the exit status. llama.cpp runs with `--verbose --log-prefix --log-timestamps`, capturing all diagnostics exposed by this build, including model, device, memory, prompt, token, timing, and error details. Runtime timestamps are elapsed time; session headers give local time and UTC offset.
- The client forwards the runtime stderr stream to one log router outside the recorder, keeping diagnostics out of the chat transcript. The router assigns a session-wide event number to each received line before routing it. No `--log-file` duplication is needed. Bash command arguments are shell-quoted explicitly for the recorder.
- Files use owner-only permissions and unique timestamped names. The chat recorder flushes each write, and each viewer follows its own saved file until the launcher exits. Debug visibility follows the runtime logging flush behavior. Closing the viewer does not stop recording. A viewer launch failure is reported in the launching terminal while chat recording continues.
- `MARIONETTE_LOG_DIR` can select a separate directory for synthetic tests. The default directory is ignored by Git. Copy all matching text files to export or back them up; no special reader or database is required.
- Diagnostic files can include full prompts and replies, local paths, and very large amounts of output. They are private local files, excluded from Git. No automatic deletion or rotation is configured. This enables the runtime’s fullest logging, not automatic crash backtraces. A forced kill or power loss may leave no ending footer.

### Reading the two diagnostic logs

`-server.txt` contains recognized connection, HTTP streaming, request queue, and response-delivery events. `-model.txt` contains recognized model loading, GPU, context, prompt, token, and timing events, including inference performed by server components. Unknown entries and all warning/error records go to both. Unprefixed continuation lines are also shared so they cannot be silently misclassified. Classification is tied to the pinned runtime; unfamiliar formats fall back to both files.

Every received line gets `[event 00000001]` followed by an ISO timestamp with microseconds and UTC offset, then a readable message block retaining the runtime's elapsed timestamp. The added timestamp is receipt time, not the time the runtime generated the event. Identical shared entries carry identical numbers and timestamps. Numbers restart each session; gaps within one file mean events routed only to the other file. Compare the two files by event number to recover their combined receipt order. This is line order, not a claim of exact execution order across runtime threads.

Messages appear below their event header on `    | ` continuation rows, wrapped at 140 characters. JSON punctuation outside strings starts a new row; values are not parsed, rounded, truncated, or deduplicated. Blank input lines are explicitly marked `[blank line]`. Control bytes are displayed as `\xHH` (for example `\x1b` for Escape and `\x08` for backspace), and literal backslashes are doubled. This retains the codes without allowing them to alter the terminal display. To recover an original message, concatenate its continuation rows without their prefixes or added line breaks, decode those escapes, and restore its final newline unless the header says `[no final newline]`. Shared events use identical formatting in both files. Existing session files are not rewritten; the new format applies on the next launch.

The live windows use `log_view.py` and the shared palette in `style.py`:

| Meaning | Color |
|---|---|
| Discord/source labels | Bright cyan |
| User, channel, message IDs | Lavender |
| User message text | Neon green |
| Thinking heading | Bright yellow |
| Thinking and routine processing | White |
| Answer heading | Light pink (`#FF9ACB`) |
| Assistant answer text | Hot pink (`#FF4FA3`) |
| Timestamps and event headers | Light blue |
| Connection/delivery success | Turquoise |
| Queue, processing, delivery timings | Peach |
| Token counts and context usage | Violet |
| Warnings, disconnects, retries | Orange |
| Errors | Bright red |

Diagnostic colors follow recognizable fields and client records; unknown rows remain white. Message words such as “error” inside a normal reply do not change its color. Source control codes stay visible as escaped text. This is a display layer: saved server/model files retain their complete reversible format and shared event numbers. Main chat keeps its normal terminal transcript, including its color codes. No extra files or windows are created.

To read an existing saved file with the same presentation, run from the project directory (replace `PATH_TO_LOG` with its path):

```bash
python src/marionette/log_view.py diagnostic < PATH_TO_LOG
python src/marionette/log_view.py discord < PATH_TO_DISCORD_LOG
```

The Discord view expands JSON message text into readable blocks and shows every metadata field separately. Saved Discord records remain structured and uncolored for tracing and future tools. Colors are enabled only when output goes to a terminal; redirected output is readable plain text. Existing saved files are never rewritten.

There is no third raw debug file or filtered temporary log. The launcher waits for the router to finish writing before exiting. Older `-debug.txt` files remain untouched. Export all three matching session files together; nothing automatically deletes or rotates them.

The default device is Vulkan0, verified as the RX 7900 XT on this machine. Check device ordering after driver/hardware changes:

```bash
./scripts/native-linux/chat.sh --list-devices
```

Select another enumerated GPU with `MARIONETTE_DEVICE=Vulkan1 ./scripts/native-linux/chat.sh`. A CPU alternative is `MARIONETTE_DEVICE=none ./scripts/native-linux/chat.sh --gpu-layers 0`; CPU performance has not been benchmarked.

## Log storage and recovery

Keep the existing `data/conversations/` folder when updating or reinstalling. To restore logs, copy the backed-up `.txt` files (and any historical `-setup.json` files) for each session into that directory without overwriting newer files. Restoring files does not restore model context. A byte-for-byte copy and restore of a synthetic transcript is checked separately from inference; no cross-database migration is applicable.

## Choices and updates

Q4_K_M reduces the model download to 2,740,937,888 bytes with a quality tradeoff versus full precision. The 65,536-token context keeps memory use bounded. Thinking is enabled with a bounded allowance; no character instructions are injected. No image projector is installed, so this setup is text-only.

When updating, change the download manifest, launcher paths, setup behavior if needed, license/version records, and these instructions together. Verify upstream checksums, reinstall, and test offline generation and interactive exit before committing. Models, runtime binaries, downloads, logs, and private data must stay out of Git.

## Runtime decision

Use `llama-server` from the same pinned b12211 Vulkan archive, managed by the standard-library Python client in `src/marionette/session.py`. The client requires no third-party Python packages or persistent service. The client handles typed messages, streams replies, and retains only the conversation that fits. `/clear` and `/exit` are the only commands; file attachments and `/regen` are not part of this base.

The model's native template is used with thinking enabled. No setup report or custom system message is supplied. See [context rollover](context.md) for token budgeting and failure behavior. Context shifting is disabled; rollover prepares a shorter structured conversation between turns while keeping the model loaded.

The context is 65,536 tokens with a 32,768-token combined thinking-and-answer allowance and no separate thinking cap. Runtime and model versions are pinned in the manifest. Restart chat after client updates to use the new code.

Sampling follows [Qwen3.5-4B's general-thinking guidance](https://huggingface.co/Qwen/Qwen3.5-4B#best-practices): temperature 1.0, top-p 0.95, top-k 20, min-p 0, presence penalty 1.5, and repetition penalty 1.0. The launcher sets `--repeat-last-n 65536` so llama.cpp applies the presence penalty across up to 65,536 tokens rather than its default last 64 tokens. These settings can reduce repetition but do not guarantee short reasoning or accurate answers.

## Verification

Run `python -m unittest discover -s tests/native-linux -v` and `bash -n scripts/native-linux/chat.sh scripts/native-linux/view-log.sh`. The tests use synthetic data and a loopback HTTP server; socket access is required, internet access is not. Baseline 1 remains a historical direct-inference checkpoint.

The client was checked with isolated real GPU sessions, including repeated context rollover, oversized-input recovery, synthetic word recall, fresh history after `/clear`, full debug logging, loopback-only listening, `/exit` with status zero, and disappearance of both the runtime process and listener. Check the current listener with `ss -lntp` while chatting; only `127.0.0.1:<temporary port>` should belong to this `llama-server` process.
