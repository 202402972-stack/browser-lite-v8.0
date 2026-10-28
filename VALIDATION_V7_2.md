# v7.2 — durable progress, same background task lifecycle

Changes are limited to recovery and preservation of the existing background execution behavior; the general upgrade roadmap has not been implemented in full.

Each dispatched agent tool records a durable intent before invocation and a reported outcome after invocation. Arguments, typed values and raw tool results are excluded. Cancellation, exceptions and tool errors leave the action uncertain; a restart converts any in-flight action to uncertain. Step number, next goal and last URL are checkpointed together. Resume provides recent reported successes and unresolved actions as historical data, with instructions to inspect the current page before repeating anything. This is a conservative model instruction, not an exactly-once guarantee for third-party websites. Existing tasks need no database migration.

A successful tool call is not labeled site-confirmed. The journal keeps the latest 100 finished actions plus unresolved actions. It does not preserve every prior DOM, screenshot, extracted result or the entire agent memory. Current owner instructions supersede an older next goal. Existing encrypted settings and browser profiles remain unchanged.

Closing Safari continues to disconnect only the live view. The live WebSocket now exits explicitly on WebSocketDisconnect instead of treating that exception as a transient screenshot failure. It never cancels the task. Server restart still pauses the task for explicit resume. Existing task timeout/step/resource limits still apply.

Validation: full automated suite includes durable intent visible before dispatch, interruption recovery, no private input/result leakage into the journal, legacy recovery, preservation of older unresolved actions, and a viewer disconnect that leaves its active task running. Real Chromium + Browser-use deterministic integration completed two steps with five live frames, real DOM/vision, Unicode input, and persisted journal reloaded by a new Engine. No real iPhone, Railway deployment, power-loss filesystem test, or production exactly-once side-effect guarantee was established.
