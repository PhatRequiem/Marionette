# HauhauCS 9B switch — 2026-11-15

Selected HauhauCS Qwen3.5-9B Uncensored Aggressive Q4_K_M through the manifest used by setup and chat. Launch commands, runtime, context policy, tools and personal data remain unchanged. Previous model files remain available. No application process is left running by this verification.

## Provenance and decision

- Original developer: [Qwen](https://huggingface.co/Qwen/Qwen3.5-9B); actual Apache-2.0 license text reviewed. Derivative publisher: [HauhauCS](https://huggingface.co/HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive), whose model card declares Apache-2.0 (no separate LICENSE file).
- Revision: `0a41c68809d375475f954be12ba7c40efa56c2a9`.
- File: `Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf`, 5,627,044,224 bytes.
- SHA-256, obtained from Hugging Face LFS metadata and verified locally: `2ca636d9e81d3d23ca9b60c234fe185d30ec082eeba69ce770fdb0c76559a4f5`.
- Shared path: `Qwen/Qwen3.5/9B/Uncensored/HauhauCS-Aggressive/<revision>/` beneath the existing model library. Catalog records original developer, publisher, revision, download URL, precision and checksum. No compatible copy existed before download.
- Q4 preserves context/runtime headroom on the 20 GB GPU compared with Q8 or BF16, at reduced numerical precision. No controlled precision or speed comparison was performed.
- Reviewed both publisher cards. Deliberately selected original Qwen general-thinking sampling (temperature 1.0, top-p 0.95, top-k 20, min-p 0, presence penalty 1.5, repetition penalty 1.0), rather than the derivative card's temperature 0.6. Retained 65,536 context and 32,768 combined output allowance, deviating from the derivative's 128K recommendation to bound memory use. See the authoritative [setup decision](../../active/setup-and-maintenance/setup.md#hauhaucs-guidance-decision).

## Verification

Setup downloaded and checksum-verified the new weights, verified the existing b12211 runtime against its pinned archive, and checked 68 pinned agent packages. A second setup run verified and reused all existing artifacts. Shared catalog entries for previous models were preserved.

All 20 existing setup/launcher regression tests passed with local socket access; launcher shell syntax and diff whitespace checks passed. The initial sandboxed test run could not exercise local sockets. An initial smoke harness incorrectly expected a new-profile prompt; it was cleanly exited and corrected to select the automatically created synthetic owner.

The corrected direct application-session test used the actual manifest paths and launcher runtime arguments, isolated synthetic personal data, and a separate setup datasheet. Local evidence is ignored under `data/conversations/model-check-hauhaucs-2026-11-15/`; no real profiles or conversations were used. Runtime observations confirmed:

- RX 7900 XT through Vulkan; 33/33 layers offloaded.
- GPU model buffer 4,810.28 MiB, GPU KV buffer 2,048 MiB, GPU compute buffer 176.02 MiB (component allocations, not peak or total process VRAM).
- Context 65,536 and effective sampling matching the explicit settings above, including repeat-last-n 65,536.
- Native embedded tool-aware template, reasoning output and final-answer output.
- Arithmetic response: `7 + 5 = 12`.
- Requested clock call actually executed `get_current_time`, returned success, and produced the matching UTC date.
- `/exit` returned status zero and stopped the owned server.

This verifies loading, basic generation, one actual tool exchange and orderly session exit. It does not establish comparative answer quality, refusal rate, maximum-context behavior, Discord delivery, general tool reliability, performance or long-session reliability. Existing user changes in the normal setup datasheet were preserved; it refreshes on the next normal launch.
