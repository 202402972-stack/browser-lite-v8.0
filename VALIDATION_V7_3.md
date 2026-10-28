# v7.3 — model usage, optional limits and context management

This is phase two of the agreed incremental upgrade. It preserves v7.2 background execution/recovery and the current visual identity. It does not claim completion of the entire general upgrade roadmap.

## Implemented
- Durable aggregate provider-reported prompt/completion/cache usage across resumes; last 30 logical request records for diagnostics. Unknown or interrupted calls remain unknown, including across restart. Legacy tasks with no measurements are not assigned a zero cost.
- Z.ai completion usage and Codex turn.completed usage are normalized to Browser-use ChatInvokeUsage. Structured-output validation failures preserve received usage when available. Google and OpenAI-compatible adapters retain their upstream usage. Raw prompts, outputs, typed values and API keys are not added to the ledger.
- Optional token and estimated-dollar limits are checked before the next logical model call; the current request can overshoot. Missing usage with an active limit stops subsequent calls instead of guessing. Changing limits while active returns 409; settings apply to new and paused/failed tasks.
- Explicit user-provided input/output/cache pricing with source/date per profile. Zero-priced profiles remain distinct from unpriced ones. Partial cost is labeled as partial. UI clears stale pricing/context metadata when the model ID is edited.
- Native Browser-use history compaction uses the same metered model, keeps eight recent history items and allows 30 items before trimming. The trigger is a character heuristic at about 70% of the configured context window; it excludes some multimodal/context overhead and is not a precise tokenizer.
- Structured probe now requires an inspect_page action and correct blue-image recognition when images are enabled. Probe usage is separate from task usage and probe events do not pollute task progress. A successful probe is not a full browser task benchmark.
- Compose target is 1GiB/one CPU. Railway resources must be selected in Railway separately. No dependency upgrades or additional services.

## Evidence
- Full suite: 65 automated tests passed. Follow-up targeted model/usage tests passed after the final metadata guard change.
- Real Chromium/Browser-use deterministic task: two model calls, actual DOM/vision, nine live frames, Unicode input, and persisted execution checkpoint.
- Real Chromium budget integration: first logical request reported 120 tokens; a 50-token cap paused the task before any second inference. Raising the cap to 500 and resuming completed it; persisted total 240 tokens. This tests lifecycle/accounting with deterministic inference, not real model quality or provider billing.
- Mobile/desktop UI regression passed at 360/390/430/1280 widths, real mapped clicks, simulated keyboard geometry, stable incremental events, encrypted settings, and no JavaScript errors. New usage UI regression saved prices/context and optional limits through real APIs, cleared limits, and verified unknown usage and stale-price reset. Screenshot preview-usage-settings.png uses non-production fixture settings.

## Limits
No new live paid-provider inference, physical iPhone/Safari test, Railway deployment, 1GiB endurance/OOM benchmark, or production CAPTCHA benchmark was run for this revision. Provider SDKs may retry internally, and failed requests may be billable without returning usage. The ledger counts logical calls and only received usage; costs and limits are not a billing guarantee. Prices are user supplied, not automatically refreshed. Existing task time/step limits remain. The later full UI/design-system and comprehensive system-hardening phases remain on the roadmap.
