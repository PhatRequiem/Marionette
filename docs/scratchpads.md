# Temporary scratchpads

Marionette has three shared working pads in process RAM:

| Pad | Characters | Purpose |
|---|---:|---|
| `focus` | 1,500 | Current task or attention |
| `working_space` | 3,000 | Tentative notes and intermediate conclusions |
| `intentions` | 1,500 | Possible next steps and their conditions |

They start empty each launch, are shared across terminal and Discord conversations, and survive `/clear` and context rollover. `/resetmemory` empties them. Restart discards them; they are not restored from saved conversations. They have no files, backups or revision store. This is temporary working state, not long-term memory or evidence of consciousness. Existing conversation/tool diagnostics may record their contents under normal retention rules.

`read_scratchpads` takes `{}` and returns all three with counts and remaining capacity. `update_scratchpad` takes one pad name and its complete replacement text, for example `{"pad":"focus","content":"Compare the next two test results."}`. Empty content clears that pad. Other pads remain unchanged. Characters use Python Unicode code points including spaces/newlines; limits are not token or byte budgets. Over-limit, invalid or extra arguments fail without changing state. Edits are immediately visible to reads and survive a failed final answer within the current process.

Production startup registers both native Qwen-Agent tools. Each ordinary turn refreshes bindings after contact notes and soul. Current contents are added as labeled data in system context, separately from the soul, and participate in exact token counting and cache preparation. A running tool loop retains its starting prompt and receives changes through tool results; the next turn gets the updated snapshot. Prior tool results in history are historical. The turn lock serializes editing across conversations. Shared notes should identify their task/contact; they are not isolated per user.

Feature guidance lives in `prompts/scratchpads.md`. The [idle thinking cycle](thinking-cycle.md) can review and edit them as well as ordinary turns. Intentions remain plain text; only the explicit cycle decision controls scheduling. Tools remain available alongside soul, contact notes and log queries; docs access stays disconnected. Restart to load the implementation; launch commands and model settings are unchanged.

Tests use synthetic data to check exact limits, Unicode, invalid edits, preservation of other pads, clearing, fresh instances, cross-conversation refresh and real Qwen-Agent orchestration over mocked HTTP. Live owner-reset checks verify RAM clearing with the recorder boundary. These are functional checks, not evidence of model judgment or reliable spontaneous use.

Verification on 2026-11-12: 165 core and 14 mocked Discord checks passed. An isolated live 4B Q4_K_M session called `update_scratchpad` three times and `read_scratchpads` once for an explicit test request. It reported the requested Focus, Working Space and Intentions values and correct character counts/limits, then exited with status zero. This demonstrates prompted tool use, not autonomous maintenance. No real profiles or Discord messages were used; production remained stopped.
