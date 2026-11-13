# Scarecrow verification — 2026-11-13

Scarecrow 0.1.0 replaces the retired Cyanheads connection with a local HTTP listener inside Obsidian. No model weights, runtime, sampling or diagnostic RAM policy changed.

Synthetic tests cover listing/search/sections/tags/metadata/links/opening, rejected mutation/path/hidden/symlink requests, authentication and browser-origin rejection, large results without a payload budget, reset-marker rejection and listener unload/reload. Python tests exercise the real HTTP server using synthetic Obsidian API fixtures, vault identity checks, repeatable installation and native Qwen-Agent tool dispatch with a mocked model response. They do not measure generated model answer quality or large-vault/long-session performance.

Verification results:

- 176 core regression checks and 16 mocked Discord checks passed with local sockets enabled. Five Node plugin tests passed. The four focused adapter/setup tests were repeated after the single-file packaging fix, including an isolated loader that rejects external relative imports.
- Obsidian 1.15.1 (installer 1.14.4) discovered and loaded Scarecrow. All seven actions succeeded against the actual existing vault; a full Welcome read matched the file, heading-section reads succeeded, and search found the mirrored Scarecrow guide. No synthetic notes were added to real data. Mutation and hidden credential-path requests were rejected.
- Disabling Scarecrow closed its HTTP listener; enabling it restored authenticated access. The final state is enabled. The existing mirror was refreshed.
- The first live load exposed Obsidian's inability to resolve sibling relative CommonJS imports. Setup now assembles a single main.js with a fixed internal module table and no external build dependencies. Synthetic tests now verify this packaging.
- The host wrapper's pre-existing `-disable-gpu` argument was interpreted as a CLI command. Verification used the installed Electron runtime directly, with `--disable-gpu` before the app path. No desktop settings were changed. The CLI reported the actual target vault; GUI launch tooling could not confirm a window.

No new real-model generation, retrieval-quality benchmark, large-vault performance test or long-session reliability test was run. Qwen-Agent dispatch used a mocked model; real Obsidian retrieval was exercised separately. The app will register the enabled tool on its next launch. Existing conversation/contact-note/soul data and model configuration were preserved.
