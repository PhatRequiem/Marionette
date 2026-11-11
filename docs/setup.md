# Native Linux terminal chat

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

Setup creates a missing version from the checksum-verified archive, or verifies an existing installation without overwriting it. The archive cache remains in the checkout's `data/downloads/`. The November 10, 2026 move preserved all 62 installed files/library links; its local record is `llama.cpp/relocation-2026-11-10.json`. No compatibility link is left in `runtime/llama.cpp/`. Historical checkpoints retain their original paths.

To use a different app library, set `MARIONETTE_APPS_DIR` to its absolute root for both setup and chat. It replaces the `AI Apps` folder, not the `llama.cpp` folder:

```bash
export MARIONETTE_APPS_DIR="/path/to/AI Apps"
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

Leave it unset for the default above. Each project pins its runtime version independently; keep versions needed by other applications. Stop all users of a version before moving or repairing it. Sharing the installation does not create a shared running server: Marionette still starts and stops its own loopback server with each chat.

Relocation verification (November 10, 2026): checksums, permissions, and library links matched before and after the move. Setup verified the shared installation and model without downloading replacements. A fresh runtime installation into a temporary app library and a launcher version check also passed, using the retained archive. All 55 automated checks passed (43 core, 12 mocked Discord), along with shell syntax and diff checks. A synthetic-profile GPU chat loaded the relocated runtime with the existing Q4 model at 65,536 context, answered `2 + 2` with `4`, and stopped its server cleanly. Runtime version, model, and sampling settings are unchanged; this is a relocation and functional check, not a new performance or long-session evaluation.

## Shared model storage

Setup and chat both use `~/AI Infrastructure/AI Local Models/Qwen/Qwen3.5/4B/Instruct/Qwen3.5-4B-Q4_K_M.gguf` by default. The home directory belongs to the user running the command; no username is hardcoded. The model's `directory` and `filename` in `scripts/native-linux/downloads.json` select its location within the shared library. Setup creates missing folders and verifies an existing model against the pinned checksum, downloading only when needed. Moving or cloning the checkout does not duplicate the weights.

The library sits beside `~/AI Infrastructure/AI Apps/`. The capitalization of `AI Infrastructure` matters on Linux. The user moved the library into this parent folder after its initial organization; the library's relative catalog paths still apply, while absolute paths in the original migration history describe the earlier location. Setup verification, all 54 automated checks, shell syntax, and an isolated GPU chat with clean shutdown passed again with this parent path on November 10, 2026.

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

The November 10, 2026 migration first moved the models out of their project folders and preserved duplicates. A subsequent checksum-verified cleanup removed four identical Q4 copies (10,963,751,552 bytes of duplicate file content), retained both Q4 and BF16, and applied the provider-based layout above. All embedding support files were preserved. The local `migration-2026-11-10.json` keeps the original move history; `organization-2026-11-10.json` records the later moves and duplicate removals; `catalog.json` lists current model paths, source repositories, known revisions, sizes, and checksums. `README.txt` explains the library layout. Only Marionette's configuration was updated; other projects still need their own path updates. No compatibility links were created.

Migration verification: all 38 moved files (nine weight files plus supporting files) matched their before-move checksums. Marionette setup verified the existing runtime and shared Q4 without downloading replacements. All 54 automated checks passed (42 core, 12 mocked Discord), including default/custom library paths with spaces, along with shell syntax and diff checks. An isolated standard-launcher GPU session loaded the shared Q4, offloaded all 33 layers, used 65,536 context, answered `2 + 2` with `4`, and exited cleanly with its server stopped. It used temporary synthetic profiles and separate logs; this verifies loading and basic generation, not new quality, performance, or long-session claims. Model, runtime, and sampling settings did not change.

After the provider-based reorganization, all retained files were reverified against their original checksums before deleting the four identical copies. Setup, all 54 automated checks, shell syntax, and diff checks passed again. A fresh isolated GPU session used `Qwen/Qwen3.5/4B/Instruct/`, answered `2 + 2 = 4`, and stopped cleanly. This follow-up changed only the manifest's model directory and documentation; launch commands and generation settings remain the same.

Historical reports and the fixed `baseline-v3` tag still describe the previous checkout-local model paths. An old checkpoint's setup will use its old location; follow this guide for the current checkout. The retained BF16 file is not automatically downloaded by current setup. Back it up separately if wanted; moving models on the same disk is not a backup.

## Source layout

Application code lives in `src/marionette/`: `session.py` composes the application and owns the local server. Terminal UI, conversation handling, context policy, and inference requests live in their own modules; see the [code map](../README.md#reviewing-the-code). `diagnostics.py` serializes diagnostic writes, `storage.py` persists records, and `log_router.py` classifies/formats views. The Bash launcher invokes these files by absolute path, so no Python package installation or working-directory change is needed.

`scripts/native-linux/` contains the core `setup.py`, `chat.sh`, and `view-log.sh` scripts, plus optional `setup-discord.sh` and `discord.sh`. The pinned download and Discord dependency manifests stay beside their setup scripts. The [README script inventory](../README.md#reviewing-the-code) describes each script. Core application tests live in `tests/core/`; optional Discord transport tests live in `tests/discord/`. llama.cpp lives in the shared app library; the optional Discord environment stays under `runtime/discord/`, and private data stays under `data/`. Use the same setup and launch commands after moving or cloning the complete checkout.

## Operation

For everyday launch, chat, and exit commands, see [STARTUP.md](../STARTUP.md).

The launcher resolves paths relative to itself and can be invoked from any directory. It uses util-linux `script` to record the terminal and `flock` to prevent duplicate sessions, with a Python terminal client and `llama-server` running in the foreground. Two separate desktop terminals follow connections/requests and model-processing views from SQLite. The client starts its own HTTP server process on `127.0.0.1` at a temporary port. It stops with the chat process; no separate daemon or systemd unit is installed. Other local programs can reach this endpoint while chat is running. It has no API authentication; do not expose it to the network. The address is saved in the connections/requests log.

- No personality file or generated setup report is used. See [context rollover](context.md) for preparation, budgeting, and failure behavior.
- Active model history lasts only for this process; [character notes](characters.md) persist and are supplied per message. Saved SQLite messages do not enable automatic resume or recall.
- Chat uses `--offline` for model loading; loopback HTTP still operates. No hosted API or login is needed.
- `data/conversations/marionette.sqlite3` stores sessions, structured conversation messages, original terminal output, Discord events, and full runtime/client diagnostics. The same two diagnostic windows display routed, colored views; unknown/errors appear in both without duplicate storage.
- The launcher records exact arguments, runtime/recorder versions, start/end and exit status. Runtime `--verbose --log-prefix --log-timestamps` remains unchanged. Terminal control bytes and all original diagnostic bytes are retained.
- Python must provide its standard-library `sqlite3` module (verified SQLite 3.54.0 on this host). Core setup imports it; both environment setup scripts verify it. No pip package or download-manifest change is needed.
- `MARIONETTE_LOG_DIR` selects a separate database directory for synthetic tests. `MARIONETTE_DATA_DIR` selects synthetic identities/characters in direct client tests. No tests should use personal profiles.
- Data remains private and Git-ignored. Diagnostics use [20 MB logical batches with a 500 MB rolling payload budget and protected failure windows](log-retention.md); conversation and terminal/Discord transcript storage remains uncapped. A forced kill can leave an incomplete session. Use [SQLite backup/export](storage.md), not a plain copy of a live database; WAL sidecars may hold committed records.

For log formats, colors, saved-file viewing, and recovery, see [Reading the logs](logs.md).

The default device is Vulkan0, verified as the RX 7900 XT on this machine. Check device ordering after driver/hardware changes:

```bash
./scripts/native-linux/chat.sh --list-devices
```

Select another enumerated GPU with `MARIONETTE_DEVICE=Vulkan1 ./scripts/native-linux/chat.sh`. A CPU alternative is `MARIONETTE_DEVICE=none ./scripts/native-linux/chat.sh --gpu-layers 0`; CPU performance has not been benchmarked.

## Choices and updates

Q4_K_M uses mixed 4-bit quantization (2,740,937,888 bytes) for faster infrastructure testing and lower weight memory use. It trades numerical precision for speed; conversation quality has not been compared systematically against BF16. The full 16-bit BF16 file is retained locally alongside Q4 in `~/AI Infrastructure/AI Local Models/Qwen/Qwen3.5/4B/Instruct/`. The 65,536-token context keeps memory use bounded. Thinking is enabled with a bounded allowance; no model-personality instructions are injected; current-person character notes and the update tool are supplied as described in [character profiles](characters.md). No image projector is installed, so this setup is text-only.

When updating, change the download manifest, launcher paths, setup behavior if needed, license/version records, and these instructions together. Verify upstream checksums, reinstall, and test offline generation and interactive exit before committing. Models, runtime binaries, downloads, logs, and private data must stay out of Git.

## Runtime decision

Use `llama-server` from the same pinned b12211 Vulkan archive, managed by the standard-library Python client in `src/marionette/session.py`. The client uses the pinned Qwen-Agent environment and requires no persistent service. At startup, select a saved terminal profile or add a new one; [identity mapping](identity.md) explains the private UUID registry and Discord link. The client handles typed messages, streams replies, and retains the history that fits for each separate conversation. `commands.py` recognizes `/clear` for terminal and Discord and `/exit` for terminal only. Terminal input beginning with an unknown slash command shows command help; Discord text other than `/clear` continues through normal chat. Authorization remains in `permissions.py`, while terminal printing stays in `terminal.py`. `/clear` affects only the originating conversation. `/clear` and `/exit` are the only commands; file attachments and `/regen` are not part of this base.

The model's native template is used with thinking enabled. No setup report or custom system message is supplied. See [context rollover](context.md) for token budgeting and failure behavior. Context shifting is disabled; rollover prepares a shorter structured conversation between turns while keeping the model loaded.

The context is 65,536 tokens with a 32,768-token combined thinking-and-answer allowance and no separate thinking cap. Runtime and model versions are pinned in the manifest. Restart chat after client updates to use the new code.

Sampling follows [Qwen3.5-4B's general-thinking guidance](https://huggingface.co/Qwen/Qwen3.5-4B#best-practices): temperature 1.0, top-p 0.95, top-k 20, min-p 0, presence penalty 1.5, and repetition penalty 1.0. The launcher sets `--repeat-last-n 65536` so llama.cpp applies the presence penalty across up to 65,536 tokens rather than its default last 64 tokens. These settings can reduce repetition but do not guarantee short reasoning or accurate answers.

## Verification

Run `runtime/agent/bin/python -m unittest discover -s tests/core -v` and `bash -n scripts/native-linux/chat.sh scripts/native-linux/view-log.sh`. The tests use synthetic data and a loopback HTTP server; socket access is required, internet access is not. See the [current baseline](baseline.md) for both test suites and verification boundaries.

The client was checked with isolated real GPU sessions, including repeated context rollover, oversized-input recovery, synthetic word recall, fresh history after `/clear`, full debug logging, loopback-only listening, `/exit` with status zero, and disappearance of both the runtime process and listener. Check the current listener with `ss -lntp` while chatting; only `127.0.0.1:<temporary port>` should belong to this `llama-server` process.

For the current weight format and smoke-test result, see [Q4 return verification](experiments/q4-return.md). [BF16 measurements](experiments/bf16-switch.md) and earlier Q4 experiments are historical.

Current tool-coordination setup and verification are documented in [Qwen-Agent coordination](qwen-agent.md). The shared runtime/model paths and sampling settings are unchanged.
