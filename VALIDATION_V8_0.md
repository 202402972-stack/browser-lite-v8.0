# v8.0 validation

- Browser frame stream decodes one frame while retaining only the newest waiting blob, preventing decode starvation when frames arrive rapidly. Synthetic slow-decode regression covers bounded object URLs, newest queued frame, corrupt frame retention and cancellation.
- Resume recovers the prior in-memory state when persistence fails, allowing retry while keeping the task stopped. Tests inject failure at each save. Page inspection is agent guidance, not deterministic prevention of a repeated action.
- Reconnect messaging now distinguishes a visible previous frame from no frame and does not assert task execution while state is unavailable.
- Python tests: 110 passed. No two-hour endurance test. No physical iPhone, VoiceOver, Railway deployment, live model or real proxy verification.

- UI fixtures passed: ui_minimal, ui_chat, ui_materials, ui_states, ui_verification, ui_replay, ui_archive and ui_usage; no JavaScript errors. Chromium fixtures; task data synthetic, keyboard simulated and verification is not production CAPTCHA.
- Preview files: preview-v80-chat.png, preview-v80-running.png, preview-v80-reconnecting.png, preview-v80-keyboard-simulated.png and preview-v80-settings.png.
