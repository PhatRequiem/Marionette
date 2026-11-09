# Last saved stable baseline — baseline-v2 (2026-11-09)

Recovery checkpoint: **`baseline-v2`** in GitHub repository `PhatRequiem/Marionette`. This tag identifies the exact code and documentation for this baseline. Keep it fixed; create a new tag for a future baseline instead of moving this one.

This is the last deliberately saved stable checkpoint: a simple, working foundation for future scaling, kept as a recovery point if later development becomes cluttered or unreliable. The configuration and verification below describe the program when this checkpoint was saved, not the current setup. New features and reorganizations are not automatically included. This does not imply that newer code is unstable; it means a newer baseline has not yet been deliberately designated.

Return to this checkpoint to resume development without rebuilding the application from scratch. See [README.md](../README.md) for the current program. The [previous baseline document](archive/baseline-2026-11-09.md) is archived; the older `baseline-v1` tag describes a different, direct-inference setup.

## Fixed configuration

| Part | Baseline |
|---|---|
| Runtime | llama.cpp b12211, commit `7d7f02875`, Vulkan `llama-server` |
| Model | Qwen3.5-4B BF16; full 16-bit language weights with some F32 tensors |
| Model source | Unsloth GGUF revision `e87f176479d0855a907a41277aca2f8ee7a09523` |
| Verified hardware | AMD Radeon RX 7900 XT, 20 GB VRAM, Vulkan0; all 33 layers offloaded |
| Context capacity | 65,536 tokens |
| Generation allowance | 32,768 tokens shared by reasoning and final answer; no separate reasoning cap |
| Next-input reserve | 2,048 tokens for between-turn preparation; actual input is counted before generation |
| Sampling | Temperature 1.0; top-p 0.95; top-k 20; min-p 0; presence penalty 1.5; repetition penalty 1.0; repeat-last-n 65,536 |
| Reasoning | Enabled; displayed and logged locally; only final answers retained in model history |
| Server lifetime | Owned by main chat, loopback-only temporary HTTP port, one inference slot; no persistent service |
| Optional Discord | Owner-only text DMs, shared main-chat history, final answers only plus status/error notices |

The pinned URLs and checksums live in [downloads.json](../scripts/native-linux/downloads.json); optional Discord dependencies are hash-locked in [discord-requirements.txt](../scripts/native-linux/discord-requirements.txt). Publisher sampling guidance and host requirements are documented in [setup](setup.md); dependency licenses are in [licenses](licenses.md).

## Behavior to preserve

- Follow [STARTUP.md](../STARTUP.md): launch main chat first, then optionally connect Discord. Main chat opens two diagnostic windows; Discord uses a fourth terminal.
- Terminal and Discord messages share one conversation and generate sequentially. Main chat shows the Discord sender ID, incoming text, reasoning, and answer.
- Oldest complete exchanges are removed when needed. Cache preparation happens after replies, with exact input checks before the next generation. See [context policy](context.md).
- Each main session saves chat, server, and model text logs; each Discord connection adds its own log. Diagnostic events have timestamps and shared event numbers; unknown entries and errors appear in both diagnostic logs. See [log formats and colors](logs.md).
- No personality file, generated setup report, file-reading tools, conversation summaries, or persistent model memory. `/clear` resets shared history; a new main session starts fresh.
- Disconnecting Discord leaves main chat running. Closing main chat stops its server and disconnects Discord. Successful Gateway resume can replay missed events; a stopped bot does not fetch missed history. See [Discord behavior](discord.md).

## Folder map

| Location | Responsibility |
|---|---|
| Root `README.md`, `STARTUP.md`, `AGENTS.md` | Overview, everyday launch instructions, development rules |
| `src/marionette/` | Application code |
| `scripts/native-linux/` | Platform-specific setup/launch scripts and dependency manifests |
| `tests/core/`, `tests/discord/` | Core and optional transport tests |
| `docs/`, `docs/experiments/`, `docs/archive/` | Current guides, experiment evidence, retired documentation |
| `data/` | Private conversations, credentials, models, downloads, session socket and locks |
| `runtime/` | Installed llama.cpp and optional Discord environment |
| `visual design/` | Local untracked visual references |

Manual archives exist under models, conversations, documentation, and visual references. The old Q4 model is in `data/models/archive/`; BF16 remains selected. Source history stays in Git. See the [README archive policy](../README.md#archives).

## Verification and limits

- All 42 automated checks (30 core, 12 mocked Discord) pass at this checkpoint. They cover setup, lifecycle, budgets, rollover, shared conversation, owner filtering, delivery, and log preservation/presentation. Documentation links and shell syntax were also checked.
- The BF16 GPU smoke test verified loading at 64K context, effective sampling, separate reasoning/final answer, and clean exit. Reported GPU buffers total about 10.02 GiB, excluding other overhead. See [BF16 measurements](experiments/bf16-switch.md).
- A subsequent real BF16 session delivered all 12 observed Discord answers and replied after more than four hours. One disconnect resumed in 126 ms. Recent generation was approximately 66 tokens/second. These are observations of one session, not a sustained-load benchmark or delivery guarantee. Private conversation contents are not included in this checkpoint.
- Real GPU rollover/cache reuse was verified with the earlier Q4 weights; it has not been remeasured with BF16. Automated rollover checks still pass. See [historical rollover results](experiments/idle-rollover.md).
- More users, heavier concurrent load, crash recovery, and long-term answer quality are not established by these checks. The model can give incorrect claims about its own identity and deployment.
- Context remains finite. Early submission can wait for preparation; old exchanges are omitted, not summarized. Debug logs can grow large and have no automatic retention policy. The local HTTP server has no API key and must remain loopback-only.

Repeat the automated checks from the checkout:

```bash
python -m unittest discover -s tests/core -v
runtime/discord/bin/python -m unittest discover -s tests/discord -v
bash -n scripts/native-linux/*.sh
```

## Return to this checkpoint

Stop main chat and Discord first. Preserve the current checkout and separately back up private data before changing versions. Do not use a hard reset or clean command to discard later work.

A separate clone lets you recover the code without overwriting the current project. Use an unused destination folder:

```bash
cd /home/phatkitty/Projects
git clone --branch baseline-v2 https://github.com/PhatRequiem/Marionette.git Marionette-baseline-v2
cd Marionette-baseline-v2
git switch -c restart-from-baseline-v2
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

The tag checkout initially has no development branch; `git switch -c` creates one for new work. Setup requires the host dependencies listed in [setup](setup.md), then downloads and verifies the pinned model/runtime. Inside this recovered checkout, use its local launch scripts.

For optional Discord, stop any other copy of the bot, run `./scripts/native-linux/setup-discord.sh` in the recovered checkout, restore or fill in `data/discord/.env` locally, and keep it permission `600`. Once main chat is ready, run `./scripts/native-linux/discord.sh` in another terminal opened in that same checkout.

## What Git does and does not restore

The tag restores tracked code, guides, safe configuration examples, and dependency manifests. It does **not** contain:

- `data/discord/.env`: restore privately or enter the bot token and allowed user ID again.
- Conversation logs and archived sessions: copy from a separate backup to `data/conversations/` if wanted. Restoring these does not restore model memory.
- Model weights or runtime binaries: recreate through setup, or retain verified model/download files from a private backup. Rebuild the Discord environment with its setup script rather than moving a virtual environment between paths.
- Visual references: back up and restore `visual design/` separately.

Do not restore an old session socket; launch recreates it. An archive on the same disk is not a backup. This checkpoint pins application files and downloads, not the operating system or GPU driver. A complete fresh-machine restoration has not been exercised for this checkpoint; verified setup routines and GPU checks are documented above.
