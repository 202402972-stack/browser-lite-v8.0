# v7.4 — consistent glass UI, safe rich chat and draft stability

Phase three of the incremental upgrade. Backend task/usage/recovery behavior is retained; the later system-hardening/endurance phase remains pending. No new model inference or production CAPTCHA benchmark was performed.

## Changes

- A single readable workspace stylesheet replaces accumulated conflicting layout overrides. Shared tokens cover warm AMOLED colors, three surface tiers, border/shadow/blur, typography, spacing, radii, touch targets, layers and motion. Portfolio glass source and pinned vendor provenance are in SOURCES.md and licenses/frontend-vendor.json.
- Marked 18.1.1 parses assistant Markdown; DOMPurify 3.4.17 sanitizes a restricted allowlist. Only absolute HTTP/HTTPS links without embedded credentials survive the second check; links open with noopener/noreferrer. No image, iframe, SVG, form, style or event-handler markup from the answer is allowed. Trusted copy controls are constructed through DOM APIs afterward. Code is never executed.
- Keyed chat rows and cached rich-text rendering preserve existing nodes. Reading older messages preserves the scroll anchor and shows a jump-to-latest button for new rows. Edit cancellation restores the prior unsent text. Native dialog sections keep proxy/advanced/budget detail collapsed until needed.
- Composer-only drafts use tab-local sessionStorage with an eight-hour TTL; malformed/expired data is discarded. Known API-key/private-key/password-label/proxy patterns are excluded. This is not a universal detector of secrets in free text. Settings and credential fields are never used as draft inputs. A successful send/logout clears the draft; a closed tab may lose it.
- Normal keyboard opening keeps the server Desktop viewport and mapped coordinates unchanged. Under 480px of visual height, the viewer track shrinks temporarily, leaving at least a usable chat/composer area in the tested geometry. Dialogs fit the visual viewport. Core icon hit targets are 44x44.
- Viewer disconnection retains the last image and shows a compact reconnect indicator. Hiding the document closes SSE/WebSocket viewing transports only; visibility restoration reconnects them without pausing the task. Reduced motion and reduced transparency have explicit CSS alternatives.

## Evidence

- Full Python/optional frontend-unit suite: **68 passed** (65 existing plus three draft expiry/corruption/privacy/storage-unavailable checks). Node is optional for these unit tests and not required in production.
- JS syntax checks passed for app.js, chat.js and drafts.js.
- Existing real UI regression passed at 360/390/430/1280 widths, full-width 1280 Desktop image, correct native CDP hit mapping at fit and zoom, simulated keyboard stability, chronological non-fabricated activity, encrypted model/proxy settings, no JavaScript errors.
- New ui_chat.py passed at 360/390/430/768/1280 widths: draft survives refresh; known key shape is not saved; malicious image/SVG/iframe/form/javascript-link content is removed; literal script text remains inert inside code; clipboard copy works; long code scrolls without page overflow; edit cancel restores draft; earlier rows retain identity; new events do not yank scroll; jump button returns to latest; short 420px visual-viewport simulation preserves usable chat and composer; dialog fits that height; reduced motion disables row animation; core icon targets measure at least 44x44. The same script checks last-image retention, viewer transport teardown/reconnect, and absence of task-control POSTs when hiding/showing the document.
- Usage-settings regression passed: prices/context and optional limits save through real APIs; unknown cost stays unknown; stale model-price metadata clears on model-ID edit; no overflow or JavaScript errors.
- Verification UI regression passed on the controlled fixture: single native checkbox attempt, no event flood, blind approval does not mark success, manual input during wait works, no JavaScript errors. This fixture is not a production CAPTCHA.
- Known text tokens were checked numerically against the palette backgrounds; this is not a full accessibility certification. Native dialog provides modal/focus semantics, but no VoiceOver audit was performed.

## Preview and limits

preview-v74-chat.png shows a real browser image with explicitly labeled synthetic chat messages. preview-v74-settings.png shows the actual settings UI. preview-v74-keyboard.png is clipped to a **simulated** 390x420 visual viewport; it is not a physical iPhone screenshot or a picture of the system keyboard. Historical preview files remain for previous versions.

No physical Safari/iPhone, screen-reader audit, native iOS Liquid Glass rendering, new Railway deployment, 1GiB endurance/OOM benchmark, or measured frame-rate/battery claim is established. UI assets add about 76KiB of uncompressed vendored JavaScript, with no runtime CDN, npm installation or React framework. Existing server limits and one-task behavior remain unchanged.
