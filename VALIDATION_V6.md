# v6 validation — 2026-10-25

## Proxy supplied by the owner

Nine Webshare endpoints from the screenshots were attempted using authenticated HTTP CONNECT through the environment's egress route. Connections closed during handshake. SOCKS5 was also attempted on the first three endpoints and closed during handshake. Direct TCP attempts on two endpoints returned ConnectionRefusedError; a SOCKS5 attempt on the first endpoint did likewise. No successful exit-IP result was obtained. Endpoint addresses are omitted from this report.

These observations do NOT prove that credentials are invalid or that the same endpoints fail from the owner's local network. Authentication was not successfully established. The dashboard's Working labels are not proof of reachability from this test location. Screenshot transcription and network/provider restrictions remain possible factors. Actual credentials are not included in this archive. Run proxy_doctor.py locally to test the real route from the deployment network.

## Engine and managed egress

45 automated tests passed. They include Webshare paste formats, HTTP 407 diagnostics, a real HTTPX request entering the local proxy gateway and failing closed on upstream rejection, Google receiving the managed HTTP client, Codex receiving proxy environment variables without bypass, stale-element failure classification, and reopening a disconnected browser before a new operation. Existing encrypted configuration, auth, single task, approval and model transport tests still pass.

The application scope routes browser traffic plus the implemented model SDK requests/catalog through one gateway. It is not a host firewall, VPN, identity/fingerprint isolation, or a packet-level DNS/WebRTC leak audit. Browser-only legacy configurations stay browser-only until explicitly changed. OS tools, pip downloads, host applications and unrelated SDK extensions are outside this scope. No real upstream success was established with the supplied Webshare credentials.

Real Chromium through the authenticated local test HTTP proxy passed with seven target connections and a 1280x800 frame. This verifies the bridge/auth path with a controlled proxy, not Webshare reachability. The Browser-use integration completed two deterministic calls with actual DOM and vision, live images, Arabic input, click and scroll. UI regression passed at 360, 390, 430 and 1280px, including simulated keyboard geometry and preserved conversation/event nodes.

## Coding and real provider

The browser editor integration read a buggy textarea function, replaced its code, clicked the website-side test button and observed PASS. Ambiguous editor selection returned an error instead of modifying an arbitrary editor. No code was executed on the host. This controlled repair is not proof that a model can solve every coding task. Monaco, Ace and CodeMirror 5 adapters use existing public page APIs, but full real-library versions were not tested here; CodeMirror 6 has no special adapter.

A real owner-authorized Z.ai GLM-4.5-Flash read task completed on example.com through the new request-scoped client wrapper in about 36 seconds, including about 33 seconds of model latency. This single run is not a controlled speed comparison or quality benchmark. Credentials were provided through hidden terminal input, not written into project files. The real test had no custom upstream configured because the supplied endpoints were unreachable.

Dependencies remain pinned; no runtime dependency was added. No new Railway deployment, physical iPhone or hour-long endurance test was performed. Preview images are historical illustrative UI fixtures, not proof of real Webshare operation or model-generated code repair.


## 512MiB container check

The v6 source was exercised using the existing pinned-dependency image layer, one CPU, 512MiB and no swap. The actual HTTP app process ran a deterministic browser task with live streaming: completed in two steps, eight received frames, no UI page errors, no OOM kills, and 335.3MiB highest sampled working set. This is a simple controlled website task without paid-model inference, not a general capacity guarantee. The normal production entrypoint was replaced only in this test harness to inject the deterministic model; UID 10001 and trusted environment CA setup were retained. The supplied Dockerfile remains the production entrypoint.
