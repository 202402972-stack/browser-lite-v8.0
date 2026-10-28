# v7.5 — service stability and the agreed 2GiB target

## Delivered behavior

The app remains one Python service, one user, one task and one browser. There is no external queue, broker, extra AI agent framework or dependency upgrade. Default Compose memory is now 2GiB/one CPU, as requested; Railway resources must be set separately. Runtime RAM, Docker image size and the source ZIP size are different quantities. The tested reference image is about 1.54GB, below the allowed 2GB image size.

- Browser viewer clients share a bounded JPEG cache; low-quality streaming begins at sustained high use. Model screenshots remain independent.
- A five-second watchdog checks actual SQLite write availability, disk space, memory and browser responsiveness. Sustained resource/CDP problems cancel the active worker, preserve available progress and close the browser. Storage failure cannot guarantee a new durable write.
- An unchanged-page mutation loop gets one fresh-reading opportunity after three identical mutations, then pauses if repetition continues. Canvas/verification challenges use separate handling. No universal progress detector or exactly-once site-side guarantee is claimed.
- Browser start/navigation/input/cleanup are bounded. Cleanup fallback targets only the psutil process object owned by this pinned local browser session. A stopped worker cannot issue new tool actions; uncaught worker failures are consumed and recorded safely. Guidance is included in its first persisted message update.
- SQLite archives all new events/messages independently of the bounded task snapshot; transactions roll back completely on failed archive writes. First legacy migration creates an integrity-checked backup before changing schema. Backups and legacy exports never overwrite live data. Previously discarded pre-upgrade history cannot be recreated.
- Authenticated pagination, SSE IDs/header/query-cursor recovery and on-demand UI history preserve recent lightweight views. The UI can load up to 2000 events and 250 messages; older messages are read-only, and full archives remain accessible through pagination and full backup.
- serve.py marks closing before Uvicorn drains transports, so SSE/WebSocket viewers terminate, then lifespan saves a paused task and cleans up. Readiness becomes false on shutdown/storage failure. Compose uses init, required signal-forwarding capability and a 45-second stop window; the application still drops to UID 10001.

## Automated and browser evidence

- **83 automated tests passed**, including database migration/backup, rollback atomicity, archive pagination, SSE gap replay, guidance ordering, safe worker-failure recording, shared capture across eight callers, sustained-memory/CDP failures, loop stopping, bounded cleanup and shutdown signaling.
- Existing mobile/desktop UI regression passed at 360/390/430/1280 widths with real mapped CDP clicks, fit/zoom, simulated keyboard, encrypted settings and zero JS errors. Rich-chat regression passed at 360/390/430/768/1280 widths, including inert malicious markup, code copy, draft restoration, anchored scrolling and transport reconnect.
- UI archive regression: initial 200 events expanded to 240 from SQLite; initial 50 messages expanded to 60; only the recent 50 remained editable; no overflow or JS errors. This uses explicitly labeled test content, not model inference. Screenshot: preview-v75-archive.png.
- Real Chromium process-loss test killed only its owned process tree, preserved the checkpoint, recorded BROWSER_UNRESPONSIVE and explicitly resumed to completion in three total steps. Expected upstream disconnect diagnostics occurred during fault injection.
- Real Browser-use/Chromium integration inside a restricted 2GiB/one-CPU production container completed a deterministic two-step task with actual DOM/vision, Unicode input and nine live frames. A normal production UI smoke opened the real browser with a 1280px frame, no overflow and no JS errors. QA routes were absent from the normal application.

## Timed controlled endurance

Reports under validation/ contain sampled counters, not credentials or page contents.

1. **1GiB, one CPU, no swap: 604.7 seconds elapsed** for a 600-second requested run. Completed 137 steps with two viewer connections, 536 JPEG frames per viewer, 178 SSE snapshots, a simulated provider timeout and a container restart with explicit task resume. Archived 551 events; peak sampled working set 428.7MiB. This run preceded the improved early-drain hook.
2. **2GiB, one CPU, no swap: 183.7 seconds elapsed** for a 180-second requested run with the early-drain hook. Completed 35 steps, 145 frames per viewer, 50 SSE snapshots, provider fault and verified restart/resume. Archived 143 events; peak sampled working set 384.3MiB. Measured Docker restart duration 1.57 seconds.
3. **Normal production entrypoint:** readiness succeeded, real Chromium opened, private QA routes returned 404, an authenticated SSE stream drained on SIGTERM, and application shutdown completed in 1.3 seconds. Exit 143 is expected signal exit after Uvicorn's completed shutdown; there was no OOM kill. Report: validation/production-2g.json.

Docker checks reused the previously verified pinned dependency image with current application source; they were not a fresh dependency-download build. The small final worker/guidance fixes were verified by unit tests, and the latest engine source was loaded for the final normal-entrypoint smoke. No secrets or runtime database/profile are included in the source package.

## Limits and reproduction

These runs use a deterministic model to test lifecycle, I/O, resource behavior and persistence. They do not measure real AI reasoning quality, provider quota/cost or production CAPTCHA solving. A run with a deliberate restart is not an unrestarted leak benchmark. Working-set sampling excludes inactive file cache and can miss short spikes. No physical iPhone/Safari, new Railway deployment or all-sites compatibility claim is established.

A later controlled run recorded **7203.7 seconds overall**, including setup and a deliberate restart: 1700 steps, 6787 frames per viewer, 6803 archived events and 812.0 MiB peak sampled working set. Report: validation/soak-2g-7200s.json. It used a deterministic model; elapsed time includes setup, so it does not establish 7200 seconds of active task execution. The revised harness starts the requested timer after the task reaches running state; a full-duration run with that revision has not been performed. SOAK_TEST.md includes the self-contained controlled harness, which defaults to 7200 seconds and raises step/time limits only for QA. Normal production limits remain 100 steps/3600 seconds per batch, with explicit resume and optional model-usage limits.
