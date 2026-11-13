# log-queries: archived guide reports

Extracted from [the active guide](../../../active/current-operation/log-queries.md) on November 12, 2026. These are prior test reports and development notes, not current configuration or newly executed checks. Undated passages retain their original wording; the extraction date is not a test date. Some passages include operational context necessary to interpret the report.

## Verification

`tests/core/test_log_query.py` covers valid/invalid forms, conversation scope,
previous-message anchoring, processing/delivery/error extraction, deduplication,
bounds, live RAM reads without disk event writes, startup-only parsing, and
isolated status probes. Discord status uses synthetic bot state, not credentials.
The handler was also exercised through forms against the saved multi-user archive
for processing, delivery, errors and previous-message retrieval, and against the
local startup sheet. A fresh synthetic main-chat instance returned current health,
registered tools and idle state. The Qwen-Agent adapter is additionally checked by `tests/core/test_log_tool.py`: real
framework dispatch sends the form to the handler and returns facts to a second model
request; extra scope fields and another conversation’s message are rejected.

The tool is rebound after each conversation switch and before prompt counting.
Its description includes short definitions and valid request examples rather than
injecting the entire glossary or startup sheet into every prompt. Facts are fetched
on demand. Restart chat to load the new tool; Discord must reconnect to that chat.
Only current-session messages are accessible. A query about current status will
usually observe processing as busy because it runs during the answering turn.

Live 4B verification (isolated synthetic records, existing Q4 model and normal
65,536 context/sampling): five natural-language questions selected the correct
setup, status, processing, delivery and errors forms. The model used the returned
startup fact, preserved unknown Discord status, reported the fixture’s 120 tokens,
reported recorded delivery and recognized no matching failures. All five finished
with `stop`. These are functional examples, not exhaustive answer-quality or
long-session reliability evidence; the test did not send Discord messages or write
to personal profiles.

The application also loads [log-query instructions](../../../../prompts/log-queries.md)
into the system prompt whenever this tool is enabled. They require evidence
lookup for ordinary self-setup/status questions and remain separate from the
editable soul. Restart chat to load prompt edits. This guides tool selection;
it does not force a tool call or guarantee model compliance.

The current concise guidance replaces the longer prompt used in the initial
35-question evaluation. Guidance for contact notes and soul edits is also loaded
when those tools are registered; see [prompt composition](../../../../prompts/prompt-guide.md).
Those earlier behavior scores do not measure this revised prompt.

---

## Current reliability limits

A small live Discord check on 2026-11-12 with the 4B Q4 model exercised explicit
argument examples and the follow-up instruction in `prompts/log-results.md`.
All four exchanges completed and were delivered. The model queried setup for
model identification and used two log calls for a previous-message report.
It also answered an implementation question from retained context without a new lookup.

Retrieval and delivery worked, but answer quality remained inconsistent:

- A delivery duration was reported correctly in seconds, then mislabeled as milliseconds elsewhere in the same answer.
- The model added unsupported efficiency judgments and a model-size claim.
- Responses remained longer than the brief-answer instruction requested.
- The follow-up reminder applies only after a fresh log result in the current turn; it does not apply when answering solely from retained context.

These are observed failure categories, not a controlled comparison or an accuracy
benchmark. The informal percentage discussed during review is not an evaluation
score. No transcripts, personal identifiers or raw logs are included here. Private
runtime evidence follows the normal retention and memory-reset policy.

Development can continue with these limitations recorded. Before relying on model
interpretations for automated actions, repeat fixed synthetic questions and score
tool selection, valid arguments, factual interpretation and error recovery
separately, including ordinary conversation that needs no tool. That evaluation
is planned, not implemented or passed by the current checks.

---

Restart main chat and reconnect Discord to load these handler changes. Historical results already held in active context retain their original format. This change improves the evidence contract; model interpretation still requires evaluation.
