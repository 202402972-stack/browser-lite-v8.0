# Implementation sources

- Portfolio theme: https://github.com/abbn7/glass-morphic-brilliance/blob/d1dab0ab8cf0e3f463c1a2faa7a8f21a06e94aa6/src/styles.css — exact dark tokens, gradients, glass borders/shadows, mobile blur values. Adapted at the repository owner's explicit request. No portfolio content, identity monogram, or WebGL scene copied.
- Local font: IBM Plex Sans Arabic, @fontsource package 5.2.7 — SIL Open Font License in static/fonts/OFL.txt.
- Agent Router Codex setup: https://agentrouter.org/docs/codex.html — custom provider, API key env variable, Responses API.
- Agent Router Claude Code setup: https://agentrouter.org/docs/claude-code.html — Anthropic route (documented, not used in this release).
- Agent Router Roo Code setup: https://agentrouter.org/docs/roocode.html — OpenAI-compatible /v1 route matching the user's screenshot.
- Official Codex: https://github.com/openai/codex — binary 0.163.0 from npm's official @openai/codex architecture package, npm SHA-512 verified during Docker build. Code mode host, voice components, Node.js and ripgrep are not installed because browser-model calls do not use them. Apache-2.0 license included.

## Minimal v3 redesign

The user's latest screenshots are the visual source for this revision: black AMOLED canvas (`#000000`), warm ivory (`#e8e2d4`), charcoal (`#302c27`) and restrained terracotta (`#ce785e`). The runtime stylesheet is `static/workspace.css`. It adapts the portfolio's glass borders, inner highlights and local Arabic type to a much thinner interface. The previous teal/pink and champagne card layouts are no longer loaded.

The full-width desktop browser, floating chat, compact domain field, icon-only tools and small live activity line are specific to this application. No text, illustration, identity or chart was copied from the reference images. Icons are inline SVG paths; animations use CSS and the Web Animations API, without an animation library or decorative continuous rendering loop.

## v4 interaction references (2026-10-25)

Read repository READMEs: https://github.com/assistant-ui/assistant-ui (MIT; thread, composer, auto-scroll and streaming patterns), https://github.com/ibelick/prompt-kit (MIT; AI input/component composition). No React dependency or source component was added. https://github.com/emilkowalski/vaul currently declares itself unmaintained in its README and was excluded as a dependency. These are pattern references, not device testing or motion measurements.

Provider reference routes: https://openrouter.ai/api/v1/models (free-price entries inspected during planning), https://docs.api.nvidia.com/nim/reference/llm-apis and https://opencode.ai/docs/zen/. No guarantee of permanent free access or universal model compatibility is made. NVIDIA and custom providers use the existing OpenAI-compatible transport; actual account/model compatibility requires the in-app probe.

## v5 Z.ai protocol (2026-10-25)

https://docs.z.ai/guides/overview/quick-start — standard OpenAI-compatible endpoint `https://api.z.ai/api/paas/v4/chat/completions`, bearer authentication.
https://docs.z.ai/api-reference/llm/chat-completion — `response_format` text/json_object for text models; no json_schema assumption for Z.ai. Image requests omit that text-only field.
https://docs.z.ai/guides/llm/glm-4.5 — text input and optional thinking mode. Retained for older text profiles. User screenshot establishes that their key page is standard model API, separate from Coding Plan.

https://docs.z.ai/guides/vlm/glm-4.6v and https://docs.z.ai/guides/overview/pricing — GLM-4.6V-Flash supports visual input and is listed as free as reviewed on 2026-10-25. It is the new Z.ai profile preset; existing profiles are not silently changed. Availability and pricing remain provider-controlled. Real image recognition and a two-step local visual selection task passed using the application's Z.ai adapter. This is not a production CAPTCHA success claim.

## v6 engine and proxy references

- browser-use/browser-use — https://raw.githubusercontent.com/browser-use/browser-use/ef62b60e6fdc5f96e6fa16866aa64fd665e999a7/browser_use/agent/service.py; inspected symbols: max_actions_per_step, use_thinking.
- browser-use/browser-use — https://raw.githubusercontent.com/browser-use/browser-use/d828d83d7aa2becaa231de400f1a4ff77cb490a5/browser_use/tools/service.py; inspected symbols: Element index, async def input.
- microsoft/vscode — https://raw.githubusercontent.com/microsoft/vscode/f751ef9cca5bc624334bfbad075ef116d73d43a1/src/vs/editor/standalone/browser/standaloneEditor.ts; inspected symbols: getEditors.
- ajaxorg/ace — https://raw.githubusercontent.com/ajaxorg/ace/cf883e36a399cae1491a87d60d86e4d9be9fcf8e/src/editor.js; inspected symbols: setValue.
- codemirror/codemirror5 — https://raw.githubusercontent.com/codemirror/codemirror5/bcd36cb3f545a679a868519c7152e1378a573d87/src/model/Doc.js; inspected symbols: setValue.

- Playwright browser proxies: https://playwright.dev/python/docs/network
- Explicit HTTPX proxy clients: https://www.python-httpx.org/advanced/proxies/
- Webshare SOCKS5 service documentation: https://www.webshare.io/features/socks5-proxy (inspected; not proof that the supplied endpoints are reachable).
- Google GenAI HttpOptions.httpx_async_client and installed _api_client.py were inspected to verify custom async client selection.

Browser-use stays pinned at 0.13.11. max_actions_per_step=2 and use_thinking=False are supported settings; two actions is a local tuning decision, not an upstream performance guarantee. Stale-index recognition follows the pinned tool's explicit "Element index ... not available" response and lets the agent reread the page; no blind replay of a mutation. Stagehand's act/extract README was inspected, but no Stagehand dependency or self-healing implementation was copied.

Editor adapters invoke existing public APIs; no editor framework is bundled. The integration test verifies textarea repair and website-side output. Full real-library Monaco/Ace/CodeMirror versions have not been exercised here; ambiguous and unsupported editors fail explicitly.

## v7 — reviewed local upstream checkouts

Both repositories were downloaded as shallow reference checkouts, outside the application archive:

- Browser-use: `/workspace/references/browser-use`, commit `3df5806a0d097a1546d92c49bcf1b28c9972c3bd`.
- Stagehand: `/workspace/references/stagehand`, commit `8023f34161d650c196dc343d2c232fb5e129a826`.

Evidence inspected:

- https://github.com/browser-use/browser-use/blob/3df5806a0d097a1546d92c49bcf1b28c9972c3bd/browser_use/browser/profile.py — `captcha_solver` is an event watchdog active when the browser emits BrowserUse CDP events; `BrowserProfile.get_args()` retains default Chromium settings. Its existing AutomationControlled setting is inherited by this app, not a new local stealth engine.
- https://github.com/browser-use/browser-use/blob/3df5806a0d097a1546d92c49bcf1b28c9972c3bd/browser_use/browser/watchdogs/captcha_watchdog.py — waiting for started/finished events with bounded timeouts. This is not an open-source local image-solving model.
- https://github.com/browser-use/browser-use/blob/3df5806a0d097a1546d92c49bcf1b28c9972c3bd/README.md — managed CAPTCHA solving and stealth are documented Cloud features requiring BROWSER_USE_API_KEY.
- https://github.com/browserbase/stagehand/blob/8023f34161d650c196dc343d2c232fb5e129a826/packages/protocol/schemas.ts — Browserbase session `solveCaptchas`/`advancedStealth` parameters. These are managed session features, not standalone local capabilities obtained by copying a flag.
- https://developers.google.com/recaptcha/docs/faq — official public v2 TEST key for automated tests. Google explicitly says this key always passes; it cannot establish production challenge-solving ability.

The local observer adds bounded CDP observation/native checkbox input and delegates visual decisions to the owner's configured vision model. No external solver service, fingerprint-spoofing bundle, token injection, CAPTCHA-script modification, or cloud session was added. Browser-use stays pinned; copying a latest-main checkout is not an automatic dependency upgrade.

## v7.3 — usage and history compaction

- Installed pinned Browser-use 0.13.11: `browser_use/llm/views.py`, `ChatInvokeUsage`, supplies prompt/completion/cache totals used by the ledger. Provider usage fields, not character estimates, are used for billing display.
- Installed pinned Browser-use `agent/views.py` (`MessageCompactionSettings`) and `agent/message_manager/service.py` (`maybe_compact_messages`) supply the existing history-summary behavior. Its trigger is a character heuristic over history; it is not a tokenizer or complete multimodal context measurement. Settings use only `trigger_char_count` to avoid the upstream model-validator conflict on nested revalidation when both derived thresholds are populated.
- https://platform.openai.com/docs/api-reference/chat/object — completion usage and cached prompt-token details for the compatible Z.ai response.
- Official Codex CLI JSON event stream: `turn.completed` usage (`input_tokens`, `cached_input_tokens`, `output_tokens`). The adapter parses only the usage fields; stdout and prompt contents are not persisted. Missing usage remains unknown.
- Prices are explicitly user supplied with source/date, not fetched from the reference repositories or inferred from model names. No new model SDK, dependency upgrade, broker or worker service was added.

## v7.4 — design system and safe chat rendering

- Re-inspected https://github.com/abbn7/glass-morphic-brilliance/blob/d1dab0ab8cf0e3f463c1a2faa7a8f21a06e94aa6/src/styles.css: normal/strong glass gradients, inner highlights, blur tiers and reduced-motion/transparency adaptation. Warm AMOLED palette and compact layout follow the owner's later approved direction. Animation durations are implementation choices, not timings inferred from screenshots. No portfolio text or WebGL scene was copied.
- Marked 18.1.1 (MIT), https://github.com/markedjs/marked — GFM parser, used before sanitization; not trusted to sanitize HTML itself.
- DOMPurify 3.4.17 (Apache-2.0 license text bundled; upstream dual-license available), https://github.com/cure53/DOMPurify — sanitization with an explicit tag/attribute allowlist, followed by HTTP/HTTPS-only link checks. No Markdown image loads or interactive raw HTML.
- Vendor files were fetched from their npm package tarballs, checked against registry SHA-512 integrity, then only the chosen compiled browser assets and license texts were copied. Exact URLs, versions, integrity strings and asset SHA-256 digests are in `licenses/frontend-vendor.json`. Bundles are local and unmodified. No install scripts or node_modules were used.
- Native platform interfaces used: VisualViewport, ResizeObserver, HTML dialog, sessionStorage, Clipboard API and reduced-motion/transparency media queries. This revision implements the previously agreed direction; it is not a claim of a separate Design Arc audit, native iOS Liquid Glass rendering, or physical Safari certification.


## v7.5 — persistence, lifecycle and resource guard

- Pinned Browser-use 0.13.11 installed source: browser/session.py (`kill`, `get_or_create_cdp_session`), browser/watchdogs/local_browser_watchdog.py (`_subprocess`, process cleanup) and supported agent on_step hooks. The bounded fallback uses the exact local psutil process object owned by the session; this private adapter is version-pinned and covered by controlled process-loss/recovery testing. No global process-name kill or automatic replay was added.
- Python sqlite3 Connection.backup and transactional connections: consistent backup, WAL/FULL durability and additive archive tables. The one-time legacy migration uses an integrity-checked temporary backup before atomic rename. SQLite pagination retains bounded UI snapshots without discarding archived records. https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup
- Installed Uvicorn 0.40.0 server.py (`Server.handle_exit`, `shutdown`, `capture_signals`) supplies the lifecycle hook used by serve.py. The app marks closing before transport draining so SSE/WebSocket loops can exit; the official server still handles signals and the lifespan. SIGTERM can correctly produce exit 143 after a complete graceful shutdown.
- Native SSE id/Last-Event-ID semantics and bounded archive replay; reconnecting a new EventSource uses an authenticated cursor query fallback. No external broker, task queue or multi-worker runtime was introduced.
- Memory observations are cgroup working-set samples (current minus inactive_file), not image size or an instantaneous peak guarantee. Thresholds and loop detection are application policy, not claims of upstream-provided exactly-once behavior or universal stall detection.
- QA endurance uses a deterministic local model through the same agent/browser pipeline, with private fault-control routes excluded from production Docker. No live model quality, current provider quota, stealth or CAPTCHA success claim follows from those results.

## Upgrade validation — editors and upstream preflight

- Monaco Editor 0.52.2: https://www.npmjs.com/package/monaco-editor/v/0.52.2. The test downloads the published tarball into memory, verifies its pinned SHA-512 npm integrity, and serves only its `min/vs` files from a disposable local server. A real Chromium instance exercises the public `monaco.editor.getEditors` API, including an outer container selector, read-only behavior and ambiguous editors. Production does not bundle Monaco.
- Ace 1.43.3 and CodeMirror 5.65.20: https://www.npmjs.com/package/ace-builds/v/1.43.3 and https://www.npmjs.com/package/codemirror/v/5.65.20. The separate real-browser test verifies pinned SHA-256 test assets; production does not bundle them.
- Browser-use 0.13.14 was downloaded into a separate scratch target with `--no-deps`, leaving the pinned 0.13.11 production environment unchanged. Twenty-six selected tests, a controlled editor task, and the owned-browser loss/resume test passed using the existing 0.13.11 dependency set; injected process-loss warnings were expected. This is a compatibility preflight, not a full dependency-resolved upgrade or a performance comparison: 0.13.14 declares, among others, `browser-use-sdk>=3.10.0` while the production lock has 3.4.2. No upgrade was adopted.
- Chrome DevTools Protocol `Runtime.evaluate`: https://chromedevtools.github.io/devtools-protocol/tot/Runtime/#method-evaluate and `Page.getFrameTree`: https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-getFrameTree. For a visible allowlisted verification iframe, the pinned Browser-use session manager can expose an OOPIF target with an empty URL; the controller obtains its own `location.href`, requires an exact match with the visible iframe URL and deduplicates target sessions before a native click. This was observed against Google's official public reCAPTCHA test key, not demonstrated as general CAPTCHA solving.
- Railway service limits and pricing were reviewed on 2026-10-27: https://docs.railway.com/pricing/plans and https://docs.railway.com/pricing. Plan caps and included credits can change; the project's 2 GiB test is not evidence that it fits the Free plan.

## v7.7 — visual materials and chat recovery

- User's portfolio at `d1dab0ab8cf0e3f463c1a2faa7a8f21a06e94aa6`, [`src/styles.css`](https://github.com/abbn7/glass-morphic-brilliance/blob/d1dab0ab8cf0e3f463c1a2faa7a8f21a06e94aa6/src/styles.css): inspected its normal/strong glass gradients, inset highlights and blur tiers. The v7.7 warm dark backing, opacity, spacing and motion are local design decisions. No portfolio text, assets or component source were copied.
- assistant-ui at `683883388a7a4c6d084a40948e10c376560abcbe`, [`useThreadViewportAutoScroll.ts`](https://github.com/assistant-ui/assistant-ui/blob/683883388a7a4c6d084a40948e10c376560abcbe/packages/react/src/primitives/thread/useThreadViewportAutoScroll.ts): inspected follow/initialization/thread-switch scrolling concepts. dot retains its own vanilla JavaScript and does not bundle assistant-ui or React.
- prompt-kit at `5a9496635cc0e1bf7679fe2a9e35d9b36b99c08a`, [`prompt-input.tsx`](https://github.com/ibelick/prompt-kit/blob/5a9496635cc0e1bf7679fe2a9e35d9b36b99c08a/components/prompt-kit/prompt-input.tsx): inspected textarea height and input behavior. dot retains its existing DOM-based composer; no component source was copied.
- Codex at `fab1a5754558ec90f27efa9b3bc4a1159802bc03`, [`README.md`](https://github.com/openai/codex/blob/fab1a5754558ec90f27efa9b3bc4a1159802bc03/README.md): reviewed product scope, not a measured visual reference. Existing Agent Router CLI transport remains unchanged.
- Local Browser-use `3df5806a0d097a1546d92c49bcf1b28c9972c3bd` and Stagehand `8023f34161d650c196dc343d2c232fb5e129a826` reference checkouts: reviewed action timeouts and observe/act/extract patterns. No new engine, dependency upgrade, claim of automatic self-healing or cloud feature was introduced.
- SSE recovery uses the application's existing authenticated archive API and native EventSource cursor. New client-side paging is bounded to 2,000 in-memory history events and 500 chat event rows; the archive remains authoritative. No server API or token format was changed.

## v7.8 — smoked crystal and recovery refinement

The owner's portfolio at the pinned commit documented above informed the layered glass material; the warm AMOLED palette follows the owner's direction. The browser-use and Stagehand checkouts documented above were inspected as references; neither was upgraded or added as a dependency. Recovery uses the existing Progress and SQLite persistence mechanisms. The user's direction to inspect the page before continuing an uncertain action is model guidance, not a deterministic prevention guarantee.

## v7.9 — bounded browser frames and resume recovery

The implementation builds on the existing browser-use integration and progress journal, with the pinned upstream sources listed above. Browser frame ownership uses the existing browser object URL APIs; it does not add a browser automation dependency. Inspecting the page before repeating an uncertain action remains agent guidance, not a deterministic guarantee.
