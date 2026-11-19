# 0014 - Ollama healthcheck

## Asked
- Ollama logged `GET /api/tags` every few seconds. Check every 5 minutes instead; it's a dev server.

## Extrapolated
- Keep checking every 5 s while the container starts, so `ollama-pull` and the `tagger` don't wait minutes after `make up`.

## Plan
- `ollama` healthcheck: `start_period: 60s`, `start_interval: 5s`, then `interval: 5m`. Same `ollama list` test.

---

## Claude Notes
- The lines came from the healthcheck (`ollama list` makes `HEAD /` and `GET /api/tags`, both logged), not the app. About 17,000 lines a day at 5 s; about 300 now.
- A TCP-only check (`bash -c "</dev/tcp/127.0.0.1/11434"`) logs nothing, but only proves the port is open; not used.
- `start_interval` needs Docker Engine 25+ (dev host: 29.1). Docker stops the start interval once the container is healthy: after recreating Ollama, one check in the first 20 s, then healthy.
