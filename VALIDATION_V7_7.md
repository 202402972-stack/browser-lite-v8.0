# dot v7.7 — chat, recovery and material validation

## Changes

- Introduced three dark glass materials with a backing that remains readable over light backgrounds, restrained inset highlights, stronger text, and explicit left/right safe-area padding. Black AMOLED remains the base. Reduced-transparency uses solid surfaces, including the user's message bubble; the no-backdrop-filter fallback remains.
- Reconnected SSE replay is merged into both the activity log and chat, deduplicated by event sequence. If the initial replay has more pages, the frontend retrieves the newest bounded window from the existing authenticated archive. The log retains at most 2,000 events in memory and the chat renders at most the latest 500 event rows. Older archive data remains available through the existing API; no wire format or backend task behavior changed.
- The activity log now retains keyed rows across updates instead of rebuilding every row. Loading older history does not increment the unseen badge. A separate screen-reader status announces a bounded live update rather than attaching a live region to hundreds of historic rows; this has not been validated with VoiceOver on a physical device.
- Model/proxy settings and browser viewport semantics are unchanged. After a server restart the task still requires explicit resume.

## Verification

- 105 existing automated tests passed. Browser UI tests passed for 360/390/430/768/1280 widths, real mapped CDP clicks at fit and zoom, simulated 420px/500px visual viewport, draft restoration, markdown sanitization, connection teardown/reconnect, expired session, editing, and 44px primary targets. Tests use Chromium, not iOS Safari.
- Synthetic replay tests filled a gap of 800 events, kept the latest 2,000 for a 3,000-event gap, retained at most 500 chat rows, preserved existing activity DOM nodes, switched tasks during an in-flight replay without mixing results, retried a failed archive read, and verified that loading older history doesn't increase the new-event badge. A fresh event was announced once in the separate status region.
- Synthetic material fixtures tested black, white, a color gradient, and two positions of a striped pattern. At sampled pixels, text contrast ranged 12.30–13.73:1, placeholder 6.35–7.09:1, icon 7.89–8.81:1, subtle material text 13.46–14.72:1, and strong material text 12.15–12.60:1. These are sampled fixture checks, not a complete WCAG audit or a device performance measurement. Chromium emulation confirmed reduced-motion and reduced-transparency behavior for the tested surfaces.
- The normal local `serve.py` entrypoint opened the actual Chromium viewer at a mobile-sized viewport with a 1280px browser frame, no JavaScript errors and no horizontal overflow; shutdown completed after the test. This is a local source run, not a Railway deployment or a freshly built production image.
- Controlled verification UI retained its one local checkbox attempt, manual interaction while waiting and no event flood. This is not a production CAPTCHA test. Archive pagination, settings/usage UI, running/paused and disconnection fixtures also passed with no JavaScript errors.
- The previews `preview-v77-chat.png`, `preview-v77-running.png`, `preview-v77-paused.png`, `preview-v77-reconnecting.png`, and `preview-v77-verification-fixture.png` contain labeled synthetic task or verification content. `preview-v77-keyboard-simulated.png` is a simulated viewport, not a real keyboard. `preview-v77-materials-fixture.png` shows synthetic background tests.

## Limits

No physical iPhone/Safari or VoiceOver test, production Railway deployment, live provider inference, production CAPTCHA evaluation, browser-level battery/FPS benchmark, or new production Docker image build was performed. The requested two-hour test was not run. Existing historical validation reports remain separate; their results should not be interpreted as tests of these frontend changes.
