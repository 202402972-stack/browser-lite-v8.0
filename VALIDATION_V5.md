# v5 validation — 2026-10-25

- 33 automated tests passed. New checks cover Z.ai standard endpoint defaults, text-only default in storage and the actual settings API, encrypted credentials and masked responses, JSON-object request format/schema prompt, image request without the text-only format field, and model lifecycle events. Z.ai HTTP calls use a mocked client: no real Z.ai key was supplied.
- Chromium UI checks passed at 360/390/430/1280px, including previous geometry, input mapping, editing, encrypted settings, and simulated keyboard behavior. Activity now appears as incremental keyed entries inside the conversation; repeated state does not duplicate entries, and previous event nodes remain intact.
- Browser-use integration with the actual ObservedModel wrapper passed: real DOM and vision, read-only find-elements, two deterministic model requests, eight live frames, Arabic input, scrolling and clicking. This is an orchestration check, not a paid-provider inference test.
- Approval-required actions now record an approval entry before execution; the action entry is emitted only after approval. Existing approval/cancellation regression checks pass.
- No new dependencies were added. No new 512MiB runtime or physical iPhone test was performed for v5; v4 memory results are historical. No real Z.ai/free-account compatibility claim is made until the in-app test is run with the owner's key. Invalid JSON fails validation instead of executing guessed actions.
- Preview images use a real browser website plus explicitly synthetic conversation/activity fixtures to illustrate the timeline. They are not real Z.ai inference evidence.

Upgrade with the same persistent volume to retain conversations, proxy and saved provider keys. Existing event history is rendered directly in the chat; no conversation migration or duplicate event storage is required.
