# Failed experiment: structured logs and active-log retrieval

Decision date: 2026-11-09. Status: rejected as the current base; retained for reference, not scheduled for implementation.

Preservation branch: `failed-experiment/2026-11-09-log-system`.
Last implementation commit: `245e588138b8858fcd53175e5799ad89a7da6688`.
Recovery target: `baseline-v3`, commit `7ee4965c51b794fab63f1c96e10afa7e4d16c11f`.

## Scope

This branch preserves JSONL logging with lossless Base64 raw capture, batched records, normal/debug launch modes, and the read-only active-session `read_logs` tool. Retrieval selected recent evidence by topic and returned bounded results. The final version removed the two-lookups-per-turn cap while retaining context and generation budgets.

## Why this experiment was rejected

Tool execution and Discord delivery worked, but the model's interpretation was not reliable enough for the desired base. Observed errors included invented lookup counts, treating earlier token measurements as current, describing limited records as a complete review, and incorrect claims about logged identity information. The token reader deliberately reduced results to the latest context and usage records, preventing requests for broader token history. Repeated lookups could not retrieve older pages because pagination was not implemented.

An earlier two-call cap caused a failed answer when the model requested another lookup. Removing that cap allowed a live five-lookup review to finish and deliver, but did not correct inaccurate reporting. The failure designation applies to the overall experiment's suitability as the base; it is not evidence that JSONL or structured logging is inherently unsuitable.

## Verification and limits

Before restoration, 67 core and 12 mocked Discord checks passed. A live review completed five tool calls and delivered its answer in about 19.5 seconds. These establish functional behavior, not factual answer accuracy or long-session reliability. Private logs and identifiers are intentionally excluded from this report and Git.

## Restoration decision

The user approved stopping Marionette and Discord, preserving this branch, and restoring main's tracked tree to baseline V3 with a new commit rather than rewriting history. Baseline V3 retains terminal/Discord chat, profiles, permissions, rollover, reasoning display, Q4 weights and existing sampling/context settings. It predates every logging/retrieval change listed above and restores the earlier verbose text logs.

Private profiles, credentials, models, runtime files, visual references, and existing conversation logs must remain untouched. JSONL logs remain on disk as historical evidence; baseline V3's viewer does not gain JSONL support from this preservation. Leave the application stopped after verification. Any future reuse of this experiment requires a new explicit decision.
