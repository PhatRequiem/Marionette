# Full 16-bit model verification

November 9, 2026. Switched the default language weights from Q4_K_M to BF16 at the same pinned Unsloth revision, `e87f176479d0855a907a41277aca2f8ee7a09523`. The [published BF16 file](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/blob/e87f176479d0855a907a41277aca2f8ee7a09523/Qwen3.5-4B-BF16.gguf) is 8,424,393,632 bytes. Setup downloaded it and verified SHA-256 `9e6e2841a75f503ccb330831832fd7861266e187e0dbf149a954219ccb8c197a`.

BF16 is a 16-bit floating-point weight format, not 4-bit quantization. Runtime metadata reports 4.21 billion language-model parameters, 249 BF16 tensors and 177 F32 tensors. The model remains text-only here; no vision projector was added. The previous Q4 file is retained locally in `data/models/archive/` and is no longer selected by the manifest.

## Verified on RX 7900 XT

The unchanged launcher ran with temporary logs and a stub desktop-terminal opener. No real conversation or Discord account was used. The pinned b12211 Vulkan runtime reported:

| Allocation | MiB |
|---|---:|
| GPU model weights | 8,023.67 |
| GPU KV cache | 2,048.00 |
| GPU recurrent state | 50.25 |
| GPU compute buffer | 143.02 |

These are individual runtime buffers, not total process VRAM. All 33 layers were offloaded. Context capacity was 65,536; combined reasoning/answer allowance was 32,768. Effective sampling logs confirmed temperature 1.0, top-p 0.95, top-k 20, min-p 0, presence penalty 1.5, repetition penalty 1.0, and repeat-last-n 65,536. This continues to match [Qwen's general-thinking guidance](https://huggingface.co/Qwen/Qwen3.5-4B#best-practices).

A synthetic arithmetic prompt produced separate reasoning and final answer `4`, stopping naturally. The runtime measured 135 generation tokens in 1,992.79 ms (67.24 tokens/second). This short smoke test is not a controlled comparison against Q4, a quality benchmark, or a long-session stability test. Full precision does not guarantee factual accuracy.

`/exit` returned status zero, diagnostic files recorded the ending, and the owned model process and local session socket disappeared. All 42 regression checks passed (30 core, 12 mocked Discord), along with shell syntax and diff checks. Rollover algorithms are unchanged; prior Q4 rollover measurements are historical, not BF16 timings.
