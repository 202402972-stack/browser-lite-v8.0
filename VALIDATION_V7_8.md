# v7.8 validation

- Smoked crystal surfaces, brighter edges and opaque fallback on header, composer and controls; app browser geometry retained.
- Chat unseen counter uses archived message cursor where available and row identity/ordering for equal timestamps. Replay, scroll anchoring and task switching have regression coverage.
- Interrupted in-flight actions are marked uncertain together with paused state during recovery; older paused snapshots with in-flight actions are repaired. The agent is instructed to check the page before proceeding; this is not a deterministic guarantee against repeated actions.
- Python test suite: 107 passed. Browser fixture results and screenshots are documented below when available.
- Not verified on physical iPhone, VoiceOver, Railway, live provider inference or real proxy endpoints. Synthetic screenshots are not live task evidence. The requested two-hour test was not run.

- Browser fixtures passed: ui_minimal, ui_chat, ui_materials, ui_states, ui_archive, ui_usage, ui_verification and ui_replay. Chromium used the environment proxy for external access; initial verification failed without it. Captured content is synthetic; keyboard is simulated. Verification fixture is not a production CAPTCHA test.
- Screenshots: preview-v78-chat.png, preview-v78-running.png, preview-v78-keyboard-simulated.png, preview-v78-settings.png and preview-v78-reconnecting.png.
