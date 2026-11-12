# Qwen3.5 9B switch — 2026-11-12

Marionette now selects Qwen3.5-9B Q4_K_M through the shared download manifest. Both setup and chat read that manifest; launch commands are unchanged. The existing shared file was reused after SHA-256 verification. The previous 4B files remain available and the saved baseline tags are unchanged.

## Provenance and configuration

- Original developer: [Qwen](https://huggingface.co/Qwen/Qwen3.5-9B); Apache-2.0 license text verified.
- GGUF publisher: [Unsloth](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/tree/3885219b6810b007914f3a7950a8d1b469d598a5), revision `3885219b6810b007914f3a7950a8d1b469d598a5`.
- File: `Qwen3.5-9B-Q4_K_M.gguf`, 5,680,522,464 bytes; SHA-256 `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8`.
- Runtime: existing llama.cpp b12211, Vulkan0 / RX 7900 XT. Text-only, native embedded chat template, thinking enabled with separate reasoning output; prior reasoning is excluded from conversation history.
- Context: 65,536; reply allowance: 32,768. The context deliberately stays below the published 262,144 native limit to bound memory use.
- Reviewed [9B general-thinking guidance](https://huggingface.co/Qwen/Qwen3.5-9B#best-practices): temperature 1.0, top-p 0.95, top-k 20, min-p 0, presence penalty 1.5, repetition penalty 1.0. These match the existing explicit launcher values. Repeat-last-n remains 65,536. The recommended ordinary output allowance is 32,768.

The larger weights consume more memory than 4B Q4 and may run more slowly. Better task performance is a possibility, not an established result of this switch. No controlled quality comparison was performed.

## Verification

Setup verified the existing runtime against its pinned archive, verified the 9B weights, and checked the agent environment. Fourteen setup/launcher regression tests passed, and launcher shell syntax passed.

A direct application-session smoke test used isolated data under `/tmp`, the actual manifest paths, and the launcher's runtime arguments. Two synthetic inputs produced final answers, including `7 + 5 = 12`; `/exit` returned zero and the session stopped its server. Runtime logs confirmed 9B metadata, 33/33 layers offloaded, 65,536 context, native tool-aware template, thinking output, and effective sampling values matching the settings above. Actual allocations included 4,861.28 MiB GPU model buffer, 2,048 MiB GPU KV buffer, and 176.02 MiB GPU compute buffer; these are component allocations, not total process or peak VRAM usage.

This verifies loading and basic application generation. It does not establish tool-selection quality, full-context performance, Discord delivery, or long-session reliability on 9B. Startup observations in the normal setup datasheet refresh on the next normal launch; synthetic tests do not replace that report.
