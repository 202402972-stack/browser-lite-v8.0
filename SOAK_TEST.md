# Controlled endurance test (not real AI quality or billing)

Use an isolated local Docker environment with the project's Python dependencies installed for the host controller. The QA server has a deterministic model and authenticated fault endpoints; it is excluded from production images. Do not mount a real account profile or production data. Commands bind only to 127.0.0.1.

```sh
docker build -t dot-browser:qa .
docker run -d --name dot-soak --init --memory=2g --memory-swap=2g --cpus=1 \
  -p 127.0.0.1:8767:8000 \
  -e APP_PASSWORD=container-testing-password \
  -e MAX_STEPS=10000 -e TASK_TIMEOUT_SECONDS=7500 -e QA_MODEL_DELAY=4 \
  --mount type=bind,src="$(pwd)/tests",dst=/qa,readonly \
  --entrypoint /qa/soak_start.sh dot-browser:qa
python tests/soak.py --container dot-soak --duration 7200 --output /tmp/dot-soak-report.json
```

The controller reads `TEST_APP_PASSWORD` if set; otherwise it uses the disposable QA password above. It requires httpx and websockets from the project environment. It opens a public example page then replaces its content with a clearly labeled controlled fixture. There are no model API charges. An enterprise network proxy may require the normal trusted CA mounts and BROWSER_CA_CERT; do not disable TLS verification. The server uses its inherited HTTPS_PROXY for the browser only in this QA harness.

The requested duration now starts after the task enters running state; the report separately records setup and task elapsed time. A restart deliberately interrupts that interval. The controller checks two JPEG streams, SSE reconnections, provider-timeout recovery, readiness, durable progress across an optional Docker restart and eventual completion. It saves a report on failure too. JSON samples contain runtime counters, not credentials or page contents. Use `--duration 180` for a short diagnostic, or omit the argument for two hours. The QA process increases the ordinary task step/time limits explicitly for the test. It does not change production defaults.

For environments without external browser access, `QA_OFFLINE_FIXTURE=1` creates the same labeled fixture on a local blank page. After a container restart the controller recreates that disposable fixture before explicit resume. This variant does not test external navigation, DNS, or proxy connectivity; the report records `offline_fixture`.

```sh
docker inspect dot-soak --format '{{.State.Status}} OOM={{.State.OOMKilled}}'
docker stop --timeout 45 dot-soak
docker rm dot-soak
```

A completed short run is not equivalent to the two-hour test. A run with a deliberate restart is not a continuous unrestarted leak benchmark. Working-set samples exclude inactive file cache, and sampled peaks may miss brief spikes. Host capacity must also fit the image, container and build cache; image size is separate from runtime RAM.
