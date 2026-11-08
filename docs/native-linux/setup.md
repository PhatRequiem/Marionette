# Native Linux terminal chat

## Requirements and repeatable installation

Run from the Git checkout. This setup targets x86_64 Linux and Python 3.11 or newer (with tarfile extraction filters). The verified host uses Python 3.14.8 and Arch Linux. Runtime shared libraries: glibc, GCC runtime, OpenSSL 3, zlib, Brotli, Zstandard, Vulkan loader, and a working Vulkan driver. Logging also requires Bash, util-linux `script` with direct command argument support (verified version 2.42.4), GNU coreutils, `xdg-terminal-exec`, and a configured desktop terminal. The verified default terminal is Kitty. Setup checks that the required commands exist; the recorder must support direct command arguments (`script file -- command`). The host already provided these; no system packages or services were installed.

```bash
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

The setup downloads upstream llama.cpp's Vulkan binary release b12211 and Unsloth's Qwen3.5-4B Q4_K_M GGUF, derived from Qwen/Qwen3.5-4B. Exact URLs, model revision, and SHA-256 checksums are in `scripts/native-linux/downloads.json`. Downloads are verified before use. Setup verifies existing downloads and can recreate the runtime from its cached archive. It requires roughly 3 GB plus runtime/archive space and internet access on first installation. An interrupted model download is restarted on the next setup run.

The upstream prebuilt release avoids requiring a local compiler toolchain. This is a reproducible installation of pinned binaries, not a claim of reproducible compilation. To reinstall, rerun setup; to recreate on another machine, clone the project, satisfy the documented Linux requirements, and run the same setup. GPU driver compatibility must be checked on that machine.

## Operation

For everyday launch, chat, and exit commands, see [Chat in the terminal](chat.md).

The launcher resolves paths relative to itself and can be invoked from any directory. It runs the util-linux `script` recorder with `llama-cli` as its foreground child. A separate desktop terminal follows the current transcript. No daemon, systemd unit, server command, or network listener is launched. The release bundles shared server implementation code, but the selected entry point is the foreground CLI.

- No personality file or custom system prompt is used; the model's embedded chat template formats messages.
- Model context lasts only for this process. Dated transcripts are saved for the user; they are never fed back into the model. No memory database or cross-database migration exists.
- Chat uses `--offline`; no hosted API or login is needed.
- Transcripts are UTF-8 terminal text under `data/conversations/`, including echoed messages, replies, startup information, and session timestamps/command provenance. `--simple-io` and disabled log colors keep them readable; normal terminal carriage returns may remain.
- Files use owner-only permissions and unique timestamped names. The recorder flushes each write, and the viewer stops following when the chat process ends. Closing the viewer does not stop recording.
- `MARIONETTE_LOG_DIR` can select a separate directory for synthetic tests. The default directory is ignored by Git. Copy the text files to export or back them up; no special reader or database is required.

The default device is Vulkan0, verified as the RX 7900 XT on this machine. Check device ordering after driver/hardware changes:

```bash
./scripts/native-linux/chat.sh --list-devices
```

Select another enumerated GPU with `MARIONETTE_DEVICE=Vulkan1 ./scripts/native-linux/chat.sh`. A CPU alternative is `MARIONETTE_DEVICE=none ./scripts/native-linux/chat.sh --gpu-layers 0`; CPU performance has not been benchmarked.

## Log storage and recovery

Keep the existing `data/conversations/` folder when updating or reinstalling. To restore logs, copy backed-up `.txt` files into that directory without overwriting newer files. Restoring files does not restore model context. A byte-for-byte copy and restore of a synthetic transcript is checked separately from inference; no cross-database migration is applicable.

## Choices and updates

Q4_K_M reduces the model download to 2,740,937,888 bytes with a quality tradeoff versus full precision. The 8,192-token context keeps memory use bounded. Reasoning is disabled for straightforward conversational replies; no character instructions are injected. No image projector is installed, so this setup is text-only.

When updating, change the download manifest, launcher paths, setup behavior if needed, license/version records, and these instructions together. Verify upstream checksums, reinstall, and test offline generation and interactive exit before committing. Models, runtime binaries, downloads, logs, and private data must stay out of Git.

## Verification

On the initial installation, both published checksums matched and the launcher answered a synthetic greeting prompt with `Hello!`, reporting about 60 generated tokens/second for that very short response. This is a smoke check, not a representative speed benchmark. Setup was rerun against cached downloads. Shell syntax and the staged diff were checked. No real conversation data was used.

An interactive terminal session also accepted a typed synthetic greeting, streamed its reply, and exited successfully with `/exit`.

Logging was verified with a synthetic interactive GPU conversation in a separate temporary directory: live viewer window and follower process, both sides of the conversation in the transcript, clean `/exit`, owner-only file permissions, and byte-identical text-file backup restoration. No real conversation data was used.
