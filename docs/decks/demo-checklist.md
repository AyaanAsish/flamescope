# FlameScope - pre-demo checklist

For the live demo with the detailed companion deck `flamescope-demo.pptx` and the script `flamescope-demo-script.md`. (The Space Apps submission is the separate 7-slide pitch deck.)

## Thirty minutes before

- [ ] `make doctor` - docker, compose, python3.12, node, free ports; in live mode also that Ollama answers at `OLLAMA_BASE_URL` with `LLM_MODEL` and `EMBED_MODEL` pulled.
- [ ] Decide the mode. Live: `LLM_PROVIDER=ollama` (this stack: `LLM_MODEL=deepseek-v4-pro:cloud`, `LLM_TIMEOUT_S=120`). Safe fallback: `LLM_PROVIDER=mock` and `EMBED_PROVIDER=mock` in `.env`.
- [ ] `make deploy` only if the stack is not already up (live about 2 to 3 minutes including scoring, mock about 25 seconds; it re-seeds the database). Never run `make test`, `make test-integration` or `make test-e2e` on the demo stack: they redeploy in mock mode and the undeploy check removes the data.
- [ ] `make status` - db, api and ui healthy; `/meta/stats` shows 25 investigations, 2003 test_runs, 355 publications, 40 findings, 215 chunks and `ingest_mode` seed.
- [ ] Check the top bar: LLM badge "ollama · <model>" for live, "mock" for mock mode; dataset badge "seed · 25 investigations".
- [ ] Rehearse once in the browser, which also warms the compare and scenario caches: Overview, Ranking (Lunar habitat, Habitat tab, Evidence on FLEX), FLEX (Test runs, Next), Compare (FLEX, SPICE, SAFFIRE-II), Scenario Lab (Lunar habitat, Explain), Data Extract, Safety Tech, Ask, Earth Apps, Architecture.
- [ ] Ask the prepared question once: "What is known about smoke detection in microgravity?" - it must show citation chips. If it shows only "The curated PSI corpus does not contain enough information to answer that.", ask again, use the backup "What did SAFFIRE-II measure?", or use slide 18.
- [ ] Check that Scenario Explain shows cited sentences for the lunar preset; if not, rehearse the recovery line (script, "Explain shows something else").
- [ ] Open the browser tabs in demo order, or one tab starting at http://localhost:3000.
- [ ] Browser zoom at 100 %; window at 1440x900 or larger so the sidebar stays expanded.
- [ ] Notifications off (Do Not Disturb), other apps closed, no personal tabs visible.
- [ ] Display mirroring on and resolution checked on the projector; the dark theme is readable at the projector brightness.
- [ ] Fallback deck `flamescope-demo.pptx` open in presenter view on slide 1; speaker notes visible.
- [ ] Placeholders filled on slide 1: `{{PRESENTER}}`, `{{DATE}}`.
- [ ] Laptop on power; Wi-Fi needed for the cloud model; water.

## After

- [ ] Optional: `make undeploy` (stops everything and removes containers and volumes, including the seeded data).
