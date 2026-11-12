# Native Linux terminal chat

See the [setup datasheet](setup-datasheet.md) for audited configuration facts, evidence limits and refresh rules. Each startup automatically updates its marked observations section; the rest remains operator-maintained.

## Requirements and repeatable installation

Run from the Git checkout. This setup targets x86_64 Linux and Python 3.11 or newer with the standard-library `sqlite3` module and tarfile extraction filters (Python 3.12+ recommended). The verified host uses Python 3.14.8 and Arch Linux. Runtime shared libraries: glibc, GCC runtime, OpenSSL 3, zlib, Brotli, Zstandard, Vulkan loader, and a working Vulkan driver. Setup also requires `uv` to install the hash-locked Qwen-Agent environment under `runtime/agent/`. Logging also requires Bash, util-linux `script` and `flock` (verified version 2.42.4), GNU coreutils, `xdg-terminal-exec`, and a configured desktop terminal. The verified default terminal is Kitty. Setup checks that the required commands and extraction filters exist. The launcher also uses Python’s standard library to read runtime/model paths from the manifest. The host already provided these; no system packages or services were installed.

```bash
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

The setup downloads upstream llama.cpp's Vulkan binary release b12211 and Unsloth's Qwen3.5-4B Q4_K_M GGUF, derived from Qwen/Qwen3.5-4B. Exact URLs, model revision, and SHA-256 checksums are in `scripts/native-linux/downloads.json`. Downloads are verified before use. Setup verifies existing downloads and installed runtime files against the pinned archive without rewriting them. A new runtime is extracted into a staging directory and moved into place only after validation. Concurrent setup runs in the same checkout are rejected. It requires roughly 3 GB plus runtime/archive space and internet access on first installation. Downloads use temporary files and are published only after checksum verification. A failed download leaves any previous target intact; the next setup run restarts the download. A force-killed setup may leave an unused `.part` file.

The upstream prebuilt release avoids requiring a local compiler toolchain. This is a reproducible installation of pinned binaries, not a claim of reproducible compilation. To verify or complete installation, rerun setup; to recreate on another machine, clone the project, satisfy the documented Linux requirements, and run the same setup. GPU driver compatibility must be checked on that machine. If setup detects altered or missing files in an existing runtime, it stops rather than overwrite potentially running binaries. Close chats, move that version’s directory out of the [shared runtime folder](#shared-inference-runtime), and rerun setup to restore it from the verified archive.

## Shared inference runtime

Setup and chat use `~/AI Infrastructure/AI Apps/Inference Engines/Language Models/llama.cpp/` for the inference engine. The manifest's runtime `directory`, `version`, and `executable` select `b12211/llama-b12211/llama-server` inside that folder. Keep the whole version directory together: it includes the executables, bundled Vulkan backend libraries, library links, and licenses. System Vulkan and GPU driver packages remain managed by Linux.

Setup creates a missing version from the checksum-verified archive, or verifies an existing installation without overwriting it. The archive cache remains in the checkout's `data/downloads/`. See the [relocation report](experiments/shared-infrastructure-relocation-2026-11-10.md) for the completed move and its verification.

To use a different app library, set `MARIONETTE_APPS_DIR` to its absolute root for both setup and chat. It replaces the `AI Apps` folder, not the `llama.cpp` folder:

```bash
export MARIONETTE_APPS_DIR="/path/to/AI Apps"
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

Leave it unset for the default above. Each project pins its runtime version independently; keep versions needed by other applications. Stop all users of a version before moving or repairing it. Sharing the installation does not create a shared running server: Marionette still starts and stops its own loopback server with each chat.

## Shared model storage

Setup and chat both use `~/AI Infrastructure/AI Local Models/Qwen/Qwen3.5/4B/Instruct/Qwen3.5-4B-Q4_K_M.gguf` by default. The home directory belongs to the user running the command; no username is hardcoded. The model's `directory` and `filename` in `scripts/native-linux/downloads.json` select its location within the shared library. Setup creates missing folders and verifies an existing model against the pinned checksum, downloading only when needed. Moving or cloning the checkout does not duplicate the weights.

The library sits beside `~/AI Infrastructure/AI Apps/`. The capitalization of `AI Infrastructure` matters on Linux.

To use a different library, set `MARIONETTE_MODELS_DIR` to its absolute root path for **both** setup and chat. Quote paths containing spaces:

```bash
export MARIONETTE_MODELS_DIR="/path/to/AI Infrastructure/AI Local Models"
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

Leave the variable unset to use the default home folder. The llama.cpp runtime uses the [shared app library](#shared-inference-runtime); its verified download archive remains in `data/downloads/`. Models and shared runtime binaries are outside Git. Each project chooses its own model and settings even when sharing weights. Do not replace or move shared files while applications are using them.

The shared library is organized as `Provider/Family/Size/Variant/`, keeping original filenames. Provider means the original developer; conversion publishers are recorded separately in the library's `catalog.json`. The current layout is:

```text
Qwen/Qwen3.5/4B/Instruct/            Q4_K_M and BF16
Qwen/Qwen3.5/9B/Instruct/            Q4_K_M
Qwen/Qwen3-Embedding/0.6B/Embedding/ Q8_0
BAAI/bge-en-v1.5/33.4M/Embedding/    BGE small ONNX and supporting files
```

`Instruct` is the local category for Qwen's post-trained chat/reasoning models, as described in the official [4B](https://huggingface.co/Qwen/Qwen3.5-4B) and [9B](https://huggingface.co/Qwen/Qwen3.5-9B) model cards; the official model names have no Instruct suffix. BGE's provider and size follow its [model card](https://huggingface.co/BAAI/bge-small-en-v1.5). No Base or Heretic variants are installed. Future variants can use those folders under the appropriate size, with modified models further separated by derivative author/model name. Keep distinct revisions and precision formats separate; BF16 and Q4 are different representations of the same post-trained model, not Base versus Instruct.

Historical reports and the fixed `baseline-v3` tag still describe the previous checkout-local model paths. An old checkpoint's setup will use its old location; follow this guide for the current checkout. The retained BF16 file is not automatically downloaded by current setup. Back it up separately if wanted; moving models on the same disk is not a backup.

## Source layout

Application code lives in `src/marionette/`: `session.py` composes the application and owns the local server. Terminal UI, conversation handling, context policy, and inference requests live in their own modules; see the [code map](../README.md#reviewing-the-code). `diagnostics.py` serializes diagnostic writes, `storage.py` persists records, `ram_logs.py` keeps routine diagnostics in the existing recorder’s RAM until shutdown, and `log_router.py` classifies/formats views. The Bash launcher invokes these files by absolute path, so no Python package installation or working-directory change is needed.

`scripts/native-linux/` contains the core `setup.py`, `chat.sh`, and `view-log.sh` scripts, plus optional `setup-discord.sh` and `discord.sh`. The pinned download and Discord dependency manifests stay beside their setup scripts. The [README script inventory](../README.md#reviewing-the-code) describes each script. Core application tests live in `tests/core/`; optional Discord transport tests live in `tests/discord/`. llama.cpp lives in the shared app library; the optional Discord environment stays under `runtime/discord/`, and private data stays under `data/`. Use the same setup and launch commands after moving or cloning the complete checkout.

## Log queries

The production log-query tool is connected, and its operator CLI is also available.

## Operation

For everyday launch, chat, and exit commands, see [STARTUP.md](../STARTUP.md).

The launcher resolves paths relative to itself and can be invoked from any directory. It uses util-linux `script` to record the terminal and `flock` to prevent duplicate sessions, with a Python terminal client and `llama-server` running in the foreground. Two separate desktop terminals follow connections/requests and model-processing views from the existing recorder’s RAM, with saved SQLite fallback. The client starts its own HTTP server process on `127.0.0.1` at a temporary port. It stops with the chat process; no separate daemon or systemd unit is installed. Other local programs can reach this endpoint while chat is running. It has no API authentication; do not expose it to the network. The address is saved in the connections/requests log.

- The [soul](soul.md) is supplied as the system prompt; no generated setup report is used. See [context rollover](context.md) for preparation, budgeting, and failure behavior.
- Active model history lasts only for this process; [contact notes](contact-notes.md) persist and are supplied per message. Saved SQLite messages do not enable automatic resume or recall.
- Chat uses `--offline` for model loading; loopback HTTP still operates. No hosted API or login is needed.
- `data/conversations/marionette.sqlite3` stores sessions, structured conversation messages, original terminal output, Discord events, and the runtime/client diagnostic buffer saved at shutdown. The same two diagnostic windows display routed, colored views; unknown/errors appear in both without duplicate storage.
- The launcher records exact arguments, runtime/recorder versions, start/end and exit status. Runtime `--verbose --log-prefix --log-timestamps` remains unchanged. Terminal control bytes are retained; original diagnostic bytes remain within the rolling RAM buffer until expired or saved at shutdown.
- Python must provide its standard-library `sqlite3` module (verified SQLite 3.54.0 on this host). Core setup imports it; both environment setup scripts verify it. No pip package or download-manifest change is needed.
- `MARIONETTE_LOG_DIR` selects a separate database directory for synthetic tests. `MARIONETTE_DATA_DIR` selects synthetic contact profiles/notes in direct client tests. No tests should use personal profiles.
- Data remains private and Git-ignored. Diagnostics use [RAM-backed 20 MB logical batches with a 500 MB rolling payload budget and protected failure windows](log-retention.md); conversation and terminal/Discord transcript storage remains uncapped. A forced kill can leave an incomplete session. Use [SQLite backup/export](storage.md), not a plain copy of a live database; WAL sidecars may hold committed records.

For log formats, colors, saved-file viewing, and recovery, see [Reading the logs](logs.md).

The default device is Vulkan0, verified as the RX 7900 XT on this machine. Check device ordering after driver/hardware changes:

```bash
./scripts/native-linux/chat.sh --list-devices
```

Select another enumerated GPU with `MARIONETTE_DEVICE=Vulkan1 ./scripts/native-linux/chat.sh`. A CPU alternative is `MARIONETTE_DEVICE=none ./scripts/native-linux/chat.sh --gpu-layers 0`; CPU performance has not been benchmarked.

## Choices and updates

The selected 4B Q4_K_M uses mixed 4-bit quantization (2,740,937,888 bytes), returning to the previous model for further testing. It uses less weight memory than 9B Q4 (5,680,522,464 bytes); speed and answer quality have not been compared systematically. Quantization trades numerical precision for lower memory use. The 9B Q4 and 4B BF16 files remain in the shared library. The 65,536-token context keeps memory use bounded. Thinking is enabled with a bounded allowance; the soul supplies identity context; current-contact contact notes and their update tool are supplied as described in [contact notes](contact-notes.md). No image projector is installed, so this setup is text-only.

When updating, change the download manifest, launcher paths, setup behavior if needed, license/version records, and these instructions together. Verify upstream checksums, reinstall, and test offline generation and interactive exit before committing. Models, runtime binaries, downloads, logs, and private data must stay out of Git.

## Runtime decision

Use `llama-server` from the same pinned b12211 Vulkan archive, managed by the standard-library Python client in `src/marionette/session.py`. The client uses the pinned Qwen-Agent environment and requires no persistent service. At startup, select a saved terminal profile or add a new one; [identity mapping](contacts.md) explains the private UUID registry and Discord link. The client handles typed messages, streams replies, and retains the history that fits for each separate conversation. `commands.py` recognizes `/clear` and owner-only `/resetmemory` for terminal and Discord, plus `/exit` for terminal only. Unknown terminal slash commands show help; other Discord text continues through normal chat. Authorization remains in `permissions.py`, while terminal printing stays in `terminal.py`. `/clear` affects only the originating conversation; `/resetmemory` follows the documented [personal-data reset scope](reset-memory.md). File attachments and `/regen` are not supported.

The model's native template is used with thinking enabled. Enabled [tool guidance](../prompts/README.md) and the saved [soul](soul.md) compose the system prompt. Startup refreshes the setup datasheet; the model retrieves its recorded facts through `query_logs` when needed. See [context rollover](context.md) for token budgeting and failure behavior. Context shifting is disabled; rollover prepares a shorter structured conversation between turns while keeping the model loaded.

The context is 65,536 tokens with a 32,768-token combined thinking-and-answer allowance and no separate thinking cap. Runtime and model versions are pinned in the manifest. Restart chat after client updates to use the new code.

Sampling follows [Qwen3.5-4B's general-thinking guidance](https://huggingface.co/Qwen/Qwen3.5-4B#best-practices): temperature 1.0, top-p 0.95, top-k 20, min-p 0, presence penalty 1.5, and repetition penalty 1.0. The launcher sets `--repeat-last-n 65536` so llama.cpp applies the presence penalty across up to 65,536 tokens rather than its default last 64 tokens. These settings can reduce repetition but do not guarantee short reasoning or accurate answers.

## Verification

Run `runtime/agent/bin/python -m unittest discover -s tests/core -v` and `bash -n scripts/native-linux/chat.sh scripts/native-linux/view-log.sh`. The tests use synthetic data and a loopback HTTP server; socket access is required, internet access is not. See the [current baseline](baseline.md) for both test suites and verification boundaries.

The client was checked with isolated real GPU sessions, including repeated context rollover, oversized-input recovery, synthetic word recall, fresh history after `/clear`, full debug logging, loopback-only listening, `/exit` with status zero, and disappearance of both the runtime process and listener. Check the current listener with `ss -lntp` while chatting; only `127.0.0.1:<temporary port>` should belong to this `llama-server` process.

For the current weight format and smoke-test result, see [4B return verification](experiments/4b-return-2026-11-12.md). [BF16 measurements](experiments/bf16-switch.md) and earlier Q4 experiments are historical.

Current tool-coordination setup and verification are documented in [Qwen-Agent coordination](qwen-agent.md). The runtime and sampling settings remain unchanged by the return to 4B; the manifest now selects the 4B model path.
