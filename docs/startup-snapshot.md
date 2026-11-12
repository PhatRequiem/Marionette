# Snapshot setup section

This is a standalone design prototype, **not connected to main chat, prompts, Qwen-Agent, or Discord**. It prints the `setup` section inside the [unified snapshot](snapshots.md) envelope. It does not launch a model, send requests, read private memories or credentials, write a report file, or change launch behavior. Baseline V4 remains fixed.

## Try it

From the checkout, preview the report with unknown runtime facts:

```bash
./scripts/native-linux/startup-snapshot.sh
```

To see a populated example:

```bash
./scripts/native-linux/startup-snapshot.sh --evidence tests/fixtures/startup-observations.json
```

The example is synthetic, modeled on the current configuration. Its GPU, settings, tool list and Discord status are **not live observations**. The script works while Marionette is stopped. Output goes only to stdout unless the operator redirects it.

## Contents and evidence

| Section | Fields |
|---|---|
| Application | Marionette; whether inference is local |
| Model | Name, precision, reasoning enabled |
| Runtime | Version, loaded device |
| Limits | Context capacity, combined reasoning/answer allowance; explicitly not token usage |
| Interfaces | Terminal availability, Discord connection status |
| Tools | Explicit supplied registered-tool list and each known tool's purpose |
| Application policy | Separate histories, contact notes, shared soul, persistence/reset behavior, access boundaries |
| Provenance | Report creation time, observation time, source, synthetic flag and limitations |

Runtime fields are `null` with status `unverified` when absent. A supplied `false` or empty tool list is distinct from missing evidence. Synthetic fields say `synthetic_example`; other supplied fields say `caller_reported`, never independently verified. Known application behavior is separately labeled as design information. No sender identities, ownership IDs, soul text or contact-note content is included.

The optional JSON input uses four evidence keys (plus optional `session` for the unified interface): `source` (nonempty description), `observed_at` (timezone-bearing ISO timestamp), `synthetic` (boolean), and `values` (the fields demonstrated by the fixture). Partial observations are allowed. Unknown fields/tools, invalid types and impossible capacity/allowance pairs fail rather than silently inventing values. Evidence input is limited to 64 KiB. Tool names are explicit; the formatter does not inspect live registrations or discover tools.

This is a report formatter, not yet an evidence collector. It does not infer a GPU from a requested device flag, connection health from a socket file, or runtime identity from a filename. Source descriptions are caller-supplied, not authentication. Do not feed arbitrary external input into a future system prompt as trusted evidence.

## Future connection — not implemented

A future authorized change would collect confirmed startup facts from runtime output/API responses and registered tools, refresh interface status when it changes, and supply this report separately from the editable soul on every request. This prototype neither collects those facts nor injects the report. Observation time is preserved so an old input file cannot masquerade as a fresh probe merely because the report was regenerated.

The [message log snapshot](log-snapshots.md) is the other section of the same report: it concerns processing, token usage, delivery and errors for one message. Neither utility currently gives the model log access.

## Verification

Six synthetic tests cover missing versus false values, provenance, input validation, tool lists, capacity checks, and standalone CLI behavior. They require no GPU or private data. No model-understanding or live-runtime validation is claimed.

```bash
python -m unittest discover -s tests/core -p test_startup_snapshot.py -v
```
