# Return to Q4 for infrastructure testing

November 9, 2026. The user chose faster infrastructure testing over full weight precision. The active model is again `Qwen3.5-4B-Q4_K_M.gguf`; BF16 is preserved in `data/models/archive/`. Main chat and Discord were stopped before the switch and left stopped after verification. The fixed `baseline-v2` checkpoint still describes BF16 and was not moved.

The existing 2,740,937,888-byte Q4 file matched the [published pinned artifact](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/blob/e87f176479d0855a907a41277aca2f8ee7a09523/Qwen3.5-4B-Q4_K_M.gguf): SHA-256 `00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4`. The download manifest was updated so fresh setup installs this same file. Running setup verified the runtime and active weights without downloading replacements.

[Qwen's official guidance](https://huggingface.co/Qwen/Qwen3.5-4B#best-practices) was rechecked. General-thinking sampling remains temperature 1.0, top-p 0.95, top-k 20, min-p 0, presence penalty 1.5, repetition penalty 1.0. Context remains 65,536 tokens, with 32,768 shared by reasoning and answer. Runtime, reasoning mode, identity mapping, launch commands, and rollover code are unchanged.

## Verification

An isolated real GPU check used the standard launcher, temporary synthetic profiles/logs, and a stub terminal opener. It did not connect Discord or add a conversation to real profiles. The b12211 Vulkan runtime reported all 33 layers offloaded, 2,603.50 MiB GPU model buffer, 2,048 MiB KV buffer, and 143.02 MiB compute buffer. These are individual allocations, not a complete VRAM measurement. Logs confirmed the sampling settings and context capacity above.

The arithmetic prompt produced separate reasoning and final answer `2 + 2 = 4.`. Generation took 4,331.19 ms for 572 tokens: **131.83 tokens/second**. Prompt processing took 92.67 ms. `/exit` returned zero and stopped the owned server. This is a short functional smoke test, not a quality comparison, sustained speed guarantee, or new long-session rollover test. Q4 sacrifices weight precision; the practical quality difference from BF16 remains unmeasured.

All 47 automated checks passed (35 core, 12 mocked Discord), along with shell syntax and diff checks. Historical BF16 measurements remain in [the BF16 report](bf16-switch.md); earlier Q4 rollover checks remain in [idle rollover](idle-rollover.md).
