# v7.9 validation

- Recover in-flight journal entries before resuming a stopped worker, including without a process restart. Page inspection remains agent guidance, not a deterministic guarantee that an uncertain action cannot be repeated.
- Browser stream retains the last decoded frame and bounds blob URLs to displayed and pending frames. A synthetic 300-frame burst and a corrupt frame passed in ui_replay.
- Refined the compact reconnect indicator, event error presentation, mixed-direction text and input ergonomics.
- Python test suite: 108 passed. See browser fixture results below.
- No physical iPhone, VoiceOver, Railway, live provider or real proxy verification. No two-hour endurance test was run.

- Browser fixture scripts passed: ui_minimal, ui_chat, ui_materials, ui_states, ui_verification, ui_replay, ui_archive and ui_usage. All Chromium; no JS errors. Material sample contrast text 12.16–13.04:1, placeholder 6.28–6.74:1. Verification is a local fixture and not production CAPTCHA. Keyboard simulated.
- Screenshots: preview-v79-chat.png, preview-v79-running.png, preview-v79-reconnecting.png, preview-v79-keyboard-simulated.png and preview-v79-settings.png; tasks are synthetic.
