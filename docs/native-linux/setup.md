# Native Linux terminal chat

## Requirements and repeatable installation

Run from the Git checkout. This setup targets x86_64 Linux and Python 3.11 or newer with tarfile extraction filters (Python 3.12+ recommended). The verified host uses Python 3.14.8 and Arch Linux. Runtime shared libraries: glibc, GCC runtime, OpenSSL 3, zlib, Brotli, Zstandard, Vulkan loader, and a working Vulkan driver. Logging also requires Bash, util-linux `script` and `flock` (verified version 2.42.4), GNU coreutils, `xdg-terminal-exec`, and a configured desktop terminal. The verified default terminal is Kitty. Setup checks that the required commands and extraction filters exist. The launcher also uses Python’s standard library to read runtime/model paths from the manifest. The host already provided these; no system packages or services were installed.

```bash
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

The setup downloads upstream llama.cpp's Vulkan binary release b12211 and Unsloth's Qwen3.5-4B BF16 GGUF, derived from Qwen/Qwen3.5-4B. Exact URLs, model revision, and SHA-256 checksums are in `scripts/native-linux/downloads.json`. Downloads are verified before use. Setup verifies existing downloads and installed runtime files against the pinned archive without rewriting them. A new runtime is extracted into a staging directory and moved into place only after validation. Concurrent setup runs in the same checkout are rejected. It requires roughly 9 GB plus runtime/archive space and internet access on first installation. Downloads use temporary files and are published only after checksum verification. A failed download leaves any previous target intact; the next setup run restarts the download. A force-killed setup may leave an unused `.part` file.

The upstream prebuilt release avoids requiring a local compiler toolchain. This is a reproducible installation of pinned binaries, not a claim of reproducible compilation. To verify or complete installation, rerun setup; to recreate on another machine, clone the project, satisfy the documented Linux requirements, and run the same setup. GPU driver compatibility must be checked on that machine. If setup detects altered or missing files in an existing runtime, it stops rather than overwrite potentially running binaries. Close chats, move that version’s directory out of `runtime/llama.cpp/`, and rerun setup to restore it from the verified archive.

## Source layout

Application code lives in `src/marionette/`: `session.py` owns chat and the local server, and `log_router.py` formats and routes diagnostics. The Bash launcher invokes these files by absolute path, so no Python package installation or working-directory change is needed.

`scripts/native-linux/` contains the core `setup.py`, `chat.sh`, and `view-log.sh` scripts, plus optional `setup-discord.sh` and `discord.sh`. The pinned download and Discord dependency manifests stay beside their setup scripts. The [README script inventory](../../README.md#reviewing-the-code) describes each script. Core application tests live in `tests/native-linux/`; optional Discord transport tests live in `tests/discord/`. Runtime binaries and private data remain outside source under `runtime/` and `data/`. Use the same setup and launch commands after moving or cloning the complete checkout.

## Operation

For everyday launch, chat, and exit commands, see [STARTUP.md](../../STARTUP.md).

The launcher resolves paths relative to itself and can be invoked from any directory. It uses util-linux `script` to record the terminal and `flock` to prevent duplicate sessions, with a Python terminal client and `llama-server` running in the foreground. Two separate desktop terminals follow the saved connections/requests and model-processing logs. The client starts its own HTTP server process on `127.0.0.1` at a temporary port. It stops with the chat process; no separate daemon or systemd unit is installed. Other local programs can reach this endpoint while chat is running. It has no API authentication; do not expose it to the network. The address is saved in the connections/requests log.

- No personality file or generated setup report is used. See [context rollover](context.md) for preparation, budgeting, and failure behavior.
- Model context lasts only for this process. Dated transcripts are saved for the user; they are not automatically fed back into the model. No memory database or cross-database migration exists.
- Chat uses `--offline` for model loading; the loopback HTTP connection still operates. No hosted API or login is needed.
- Each session has a shared timestamp and unique suffix with `-chat.txt`, `-server.txt`, and `-model.txt` endings under `data/conversations/`. The chat transcript captures echoed messages, replies, and CLI startup/status output. Terminal color codes, carriage returns, and backspaces may remain.
- Both diagnostic files record session start/end times, exact launch arguments, runtime/recorder versions, and the exit status. llama.cpp runs with `--verbose --log-prefix --log-timestamps`, capturing all diagnostics exposed by this build, including model, device, memory, prompt, token, timing, and error details. Runtime timestamps are elapsed time; session headers give local time and UTC offset.
- The client forwards the runtime stderr stream to one log router outside the recorder, keeping diagnostics out of the chat transcript. The router assigns a session-wide event number to each received line before routing it. No `--log-file` duplication is needed. Bash command arguments are shell-quoted explicitly for the recorder.
- Files use owner-only permissions and unique timestamped names. The chat recorder flushes each write, and each viewer follows its own saved file until the launcher exits. Debug visibility follows the runtime logging flush behavior. Closing the viewer does not stop recording. A viewer launch failure is reported in the launching terminal while chat recording continues.
- `MARIONETTE_LOG_DIR` can select a separate directory for synthetic tests. The default directory is ignored by Git. Copy all matching text files to export or back them up; no special reader or database is required.
- Diagnostic files can include full prompts and replies, local paths, and very large amounts of output. They are private local files, excluded from Git. No automatic deletion or rotation is configured. This enables the runtime’s fullest logging, not automatic crash backtraces. A forced kill or power loss may leave no ending footer.

For log formats, colors, saved-file viewing, and recovery, see [Reading the logs](logs.md).

The default device is Vulkan0, verified as the RX 7900 XT on this machine. Check device ordering after driver/hardware changes:

```bash
./scripts/native-linux/chat.sh --list-devices
```

Select another enumerated GPU with `MARIONETTE_DEVICE=Vulkan1 ./scripts/native-linux/chat.sh`. A CPU alternative is `MARIONETTE_DEVICE=none ./scripts/native-linux/chat.sh --gpu-layers 0`; CPU performance has not been benchmarked.

## Choices and updates

BF16 uses full 16-bit language-model weights (8,424,393,632 bytes), replacing the earlier 4-bit quantization. Some small tensors remain F32 as packaged upstream. This increases memory use and can reduce generation speed; it does not guarantee factual accuracy. The 65,536-token context keeps memory use bounded. Thinking is enabled with a bounded allowance; no character instructions are injected. No image projector is installed, so this setup is text-only.

When updating, change the download manifest, launcher paths, setup behavior if needed, license/version records, and these instructions together. Verify upstream checksums, reinstall, and test offline generation and interactive exit before committing. Models, runtime binaries, downloads, logs, and private data must stay out of Git.

## Runtime decision

Use `llama-server` from the same pinned b12211 Vulkan archive, managed by the standard-library Python client in `src/marionette/session.py`. The client requires no third-party Python packages or persistent service. The client handles typed messages, streams replies, and retains only the conversation that fits. `/clear` and `/exit` are the only commands; file attachments and `/regen` are not part of this base.

The model's native template is used with thinking enabled. No setup report or custom system message is supplied. See [context rollover](context.md) for token budgeting and failure behavior. Context shifting is disabled; rollover prepares a shorter structured conversation between turns while keeping the model loaded.

The context is 65,536 tokens with a 32,768-token combined thinking-and-answer allowance and no separate thinking cap. Runtime and model versions are pinned in the manifest. Restart chat after client updates to use the new code.

Sampling follows [Qwen3.5-4B's general-thinking guidance](https://huggingface.co/Qwen/Qwen3.5-4B#best-practices): temperature 1.0, top-p 0.95, top-k 20, min-p 0, presence penalty 1.5, and repetition penalty 1.0. The launcher sets `--repeat-last-n 65536` so llama.cpp applies the presence penalty across up to 65,536 tokens rather than its default last 64 tokens. These settings can reduce repetition but do not guarantee short reasoning or accurate answers.

## Verification

Run `python -m unittest discover -s tests/native-linux -v` and `bash -n scripts/native-linux/chat.sh scripts/native-linux/view-log.sh`. The tests use synthetic data and a loopback HTTP server; socket access is required, internet access is not. See the [current baseline](baseline.md) for both test suites and verification boundaries.

The client was checked with isolated real GPU sessions, including repeated context rollover, oversized-input recovery, synthetic word recall, fresh history after `/clear`, full debug logging, loopback-only listening, `/exit` with status zero, and disappearance of both the runtime process and listener. Check the current listener with `ss -lntp` while chatting; only `127.0.0.1:<temporary port>` should belong to this `llama-server` process.

For the current weight format, GPU allocation, and smoke-test result, see [BF16 verification](experiments/bf16-switch.md). Earlier Q4 experiments remain historical.
