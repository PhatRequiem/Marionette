# Baseline 1

Historical checkpoint: `baseline-v1`. The current setup uses a small terminal client with an owned loopback `llama-server` process and [between-turn context preparation](context.md). This entire document describes the older direct-inference checkpoint; use [current operation](setup.md) for present behavior and checks.

A local, text-only terminal chat with reproducible installation and diagnostic logs. This is the base for future work, reviewed on November 8, 2026.

## Fixed scope

| Part | Baseline |
|---|---|
| Launch | `./scripts/native-linux/chat.sh` |
| Runtime | llama.cpp b12211, `llama-completion`, direct inference |
| Model | Qwen3.5 4B, Unsloth Q4_K_M; pinned revision and SHA-256 in the download manifest |
| Hardware | Verified on Radeon RX 7900 XT through Vulkan0 |
| Context | 8,192 tokens; current session only |
| Message format | Inline text-only Qwen role markers and empty closed thinking block |
| Personality | No system message or personality file |
| Logs | Two dated local text files per session, plus a live debug terminal |
| Exit | Ctrl+D at an empty prompt; relaunch to start fresh |
| Network | No listener observed during direct-inference tests; downloaded local weights, no hosted API |

Runtime and model paths come from one manifest. Download checksums are checked during setup; existing runtime files are compared against the verified archive and left untouched. The launcher does not rehash the model before every conversation. Rerun setup to verify installed artifacts.

## Verified checks

- Real GPU conversation: remember a synthetic word, then recall it on the next turn.
- Actual formatted input: user role and empty closed thinking block, with no added system message.
- Clean Ctrl+D exit with status zero; debug follower stops when chat ends.
- No TCP/UDP listener owned by the new runtime during the test.
- Live debug terminal follows the matching debug file.
- Synthetic isolated checks: manifest-driven paths, working directories containing spaces, literal shell metacharacters, unique paired filenames, owner-only permissions, chat/debug separation, returned error status, viewer failure without loss of recording, and inspection commands without new session files.
- Download checksum rejection preserves the prior file; verified downloads are reused.
- Runtime installation works from an empty directory; rerunning preserves executable identity, and altered runtime files are rejected.
- Text-file backup and restoration preserve bytes. This is same-format restoration, not database migration or restored model memory.

## Repeat the checks

From the checkout:

```bash
python -m unittest discover -s tests/native-linux -v
bash -n scripts/native-linux/chat.sh scripts/native-linux/view-log.sh
python scripts/native-linux/setup.py
```

The automated tests use temporary directories, a synthetic runtime, and a fake terminal launcher. They require Linux pseudo-terminal access, but do not use the real model, open desktop windows, or read real conversations.

For a real GPU check, use a separate test directory:

```bash
MARIONETTE_LOG_DIR="$(mktemp -d /tmp/marionette-check-XXXXXX)" ./scripts/native-linux/chat.sh
```

Ask her to remember a made-up word, ask for it again, then exit with Ctrl+D. Confirm both files contain the expected output, the debug file ends with status zero, and the debug terminal stops following. While chat is open, `ss -lntup` should show no listener owned by `llama-completion`. Test conversations stay out of real profiles and Git.

## Known limits

- The model can give incorrect answers, including incorrect claims about its own deployment. Generated text is not evidence of which hardware or network is used.
- No saved memory or automatic history reload. Context is finite; long-session behavior near the limit has not been stress-tested for this baseline.
- The inline formatting is for text conversation only. Tools, image inputs, and structured reasoning history are not supported.
- Full debug output can be large and sensitive. There is no automatic log rotation or deletion. Terminal editing characters are intentionally retained.
- SIGKILL, power loss, disk-full conditions, and GPU/driver crashes may prevent complete logs or the exit footer. Crash backtraces are not collected automatically; these failure modes have not been exhaustively tested.
- Dependencies and GPU drivers are host packages, not a frozen operating-system image. Only the documented host has been verified; downloaded binaries are pinned, but compilation from source is not reproduced here.
- The default GPU identifier can change after hardware/driver changes. Check with `./scripts/native-linux/chat.sh --list-devices`.
- Raw runtime arguments are an advanced override; custom arguments can change baseline behavior. Normal use requires no additional arguments.

## Change discipline

Keep the short [launch guide](chat.md) focused on daily use. Put technical changes in [setup and operation](setup.md), update the manifest and license inventory when dependencies change, and rerun the relevant checks before committing. Use this baseline document to distinguish verified behavior from proposed features.
