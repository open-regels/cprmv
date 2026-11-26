# CPRMV test foundation: unit tests, a per-file branch-coverage floor, and end-to-end tests

Status: design, for approval · 26 November 2026

## Intent

The Rules Serve API (`serve_api/`) has 6 tests and 46% branch coverage
(measured 26 November 2026 with `pytest --cov=src --cov=methods --cov-branch`).
Since the 0.4.2 modularisation several older tests sit commented out in
`serve_api/test/test_serve.py`. The deployment pipeline now ships every merge to
acceptance and every release to stable by itself, so the tests are what stand
between a change and a public service.

This work gives the API a test foundation that CI enforces:

- **unit tests** for the routes in `src/serve.py` and the method modules in
  `methods/`, without depending on outside services;
- a **per-file floor of 80% branch coverage**, so no file can be merged less
  tested than that once it has reached it;
- **end-to-end tests** at two levels: the real image in its real stack on every
  pull request, against recorded copies of the outside sources; and the deployed
  acceptance API after each deploy, against the real sources.

## Current state (measured 26 November 2026)

| File | Branch coverage | Note |
|---|---|---|
| `src/serve.py` (764 lines) | 46% | all routes, method loading, MCP mount |
| `methods/frbr_sru.py` | 14% | SRU search against officiele-overheidspublicaties |
| `methods/core_web.py`, `core_json.py`, `core_xml.py` | 22–25% | generic fetch/transform |
| `methods/dso.py` | 24% | DSO API, needs `x-api-key` |
| `methods/operaton.py`, `iou.py`, `roo.py` | 29–50% | |
| `methods/juriconnect.py`, `eli.py` | 80%, 91% | |
| small method modules (`bwb.py`, `cvdr.py`, …) | 100% | declarations only |
| total | 46% | 1024 statements, 240 branches |

- Outbound HTTP uses the standard library: `urllib.request.urlopen` in
  `core_web.py`, `frbr_sru.py`, `eli.py`, `serve.py` and `utils/constants.py`
  (some via `Request`).
- The source URLs come from the method definitions in
  `serve_api/data/cprmvmethods.ttl`, which is baked into the image.
- The `x-api-key` header is passed on to a source when a method is configured
  with `pass_on_from_request` (`methods/core_api.py:44`, `serve.py:214,243,292`).
- `pytest` and `pytest-cov` are in `requirements-dev.txt`. Tests run from
  `serve_api/` (`pytest`), import `..src.serve`, and use FastAPI's `TestClient`.
  CI runs them in the `test` job of `.github/workflows/ci.yml`.

## Goals

1. Every route and every method module has unit tests that run offline, fast
   and deterministically.
2. CI fails a pull request when any file under `serve_api/src/` or
   `serve_api/methods/` is below 80% branch coverage, except files on a
   **ratchet list** (below). The list can only shrink, and a listed file's
   recorded coverage can only go up.
3. On every pull request into `acc` or `main`, the **published-shape image** runs
   in the tier's real `compose.yml` with Caddy, with the outside sources replaced
   by recorded responses, and a suite of HTTP tests passes against it.
4. After every deploy to acceptance, a **live** suite runs against
   `https://acc.cprmv.open-regels.nl` with the real sources. A failure is
   reported as a tracking issue and does not block anything.
5. One set of recorded responses ("fixtures") serves both the unit tests and the
   container end-to-end tests.

## Non-goals

- Changing the API's behaviour. If a test finds a defect, it is reported and
  fixed in its own pull request, not folded into this work silently.
- Tests for the ReSpec build in `html/` (issue #24 covers its build first).
- Load or performance testing.
- A live suite against stable (`main`). Stable runs the same image that
  passed acceptance and its own `deploy` check; a live run there can follow later.

## Anti-goals

- A required check that depends on government servers being up.
- Any test, fixture or log that contains the DSO API key.
- Coverage met by tests that assert nothing (each test asserts on behaviour:
  status, body content, or the request sent to the source).
- Raising the floor by excluding code from measurement. `# pragma: no cover`
  only with a comment saying why, and only where code genuinely cannot run in a
  test (for instance the `__main__` block).

## Constraints

- Python 3.14, the hashed `requirements-dev.txt`, and the pinned image. A new
  test dependency is added through `pyproject.toml` and recompiled with
  `make deps-linux`, so it is hashed like the rest.
- The repository is public. Recorded responses are public government data; the
  recorder strips request headers and never writes a key.
- Required checks are matched by job name: `test` and `build` must keep their
  names. A new required check (`e2e`) is added to both rulesets only after it
  has reported on a pull request.
- Tests run serially (pytest's default here); nothing in this work turns on
  parallel execution.

## Approaches considered

**How the container end-to-end test replaces the outside sources** (decided
26 November 2026):

1. ***A test-only shim mounted into the real image.* Chosen.** In the test run a
   `sitecustomize.py` on `PYTHONPATH` replaces `urllib.request.urlopen` with a
   lookup in the recorded responses. Everything else is real: the image CI just
   built, the tier's own `compose.yml`, Caddy with its headers, `/mcp`. No
   product code changes. The network layer itself is not exercised; the live
   suite covers that.
2. *A product setting that redirects the sources to a fake server.* More
   realistic on the network, but it changes product code and the method
   configuration only for testing.
3. *Fake servers posing as the real host names on the Docker network.* Closest
   to reality, but every source needs a fake TLS certificate the API trusts.
   Fragile.

**What "end-to-end" proves** (decided 26 November 2026): both a required
offline container suite on pull requests and a non-blocking live suite after
each acceptance deploy.

**The DSO key** (decided 26 November 2026): an Actions **environment secret**
`DSO_API_KEY` on the `acceptance` environment, read only by the post-deploy job.

## Design

### Layout

```
serve_api/test/
  conftest.py                shared fixtures: TestClient, the urlopen fake, fixture loading
  fixtures/<source>/…        recorded responses (body + status + content type), one file per request
  fixtures/index.json        request (method, URL, relevant headers) → fixture file
  unit/                      unit tests per module: test_serve_<area>.py, test_methods_<module>.py
  e2e/                       container end-to-end tests (HTTP against localhost)
  live/                      live tests (HTTP against acceptance)
  shim/sitecustomize.py      the urlopen replacement for the container run
scripts/record-fixtures.py   re-records fixtures from the real sources (run by hand)
scripts/check-coverage.py    the per-file floor and ratchet
serve_api/coverage-ratchet.json
```

The existing `test_serve.py` tests move into `unit/` (its working tests kept,
the commented-out ones either revived against the current code or deleted with
a line in the pull request saying which).

### The recorded responses

- One fake for both levels: given a `Request` or URL, it finds the fixture by
  method and full URL, plus selected headers where a source varies its answer
  by them (`Accept`). It returns an object with the same reading interface the
  code uses (`read()`, `status`/`getcode()`, `headers`, context manager).
- An unknown request **fails loudly** (raises with the URL), so a test can never
  pass by silently reaching the network or getting an empty answer.
- In unit tests the fake is installed with `monkeypatch` on each module's
  imported `urlopen` name. In the container it is installed by `sitecustomize.py`
  for the whole process.
- Error cases (HTTP 404/500, `URLError`, timeouts) are fixtures too, so the
  error branches are covered.
- `scripts/record-fixtures.py <test-ids or URLs>` fetches from the real sources
  and writes the fixture files and index entries. It reads the DSO key from
  `DSO_API_KEY` in the environment, sends it only as the request header, and
  writes no request headers to disk. Re-recording is a deliberate, reviewed
  change (the diff shows what a source now answers).
- **Who records what** (decided 26 November 2026): the builder records every
  source that needs no key. **The user records the DSO fixtures** locally with
  `DSO_API_KEY=… python scripts/record-fixtures.py dso` and they are committed;
  the key never reaches the builder or the repository. So the recorder and the
  list of DSO requests come early in the work, and the DSO unit and e2e tests
  land once those fixtures exist.
- **Method definitions** (builder's question, my call): tests that touch a
  source load the production `serve_api/data/cprmvmethods.ttl`, the same file
  the image bakes in, so unit tests and the container request identical URLs and
  share one fixture set. `test/cprmvmethods.test.ttl` stays only for tests of
  method loading itself.
- **Date- and "latest"-dependent requests** (my call): unit tests freeze "today"
  (monkeypatch the date the code reads, or inject it); the container suite uses
  only requests with explicit dates or versions, so its URLs are stable. The
  fake still fails loudly on any URL it does not know.

### Unit tests

- `src/serve.py`: each route (`/`, `/health`, `/methods`, `/<version>/methods/{name}`,
  `/rules/{…}`, `/raw/{…}`, `/ref`, `/respec`, `/mcp` mounted), content
  negotiation per format, error responses, the `x-api-key` pass-through (the
  header reaches the fake source; it is not echoed in the response), method
  loading.
- `methods/`: each module's parsing and transformation against recorded
  responses, its URL building, and its error branches.
- Plain `assert`s on the response/output. Where RDF is returned, assertions on
  specific triples or counts, not whole-document snapshots.

### The coverage floor

- `pytest --cov=src --cov=methods --cov-branch --cov-report=json` in the `test`
  job, then `scripts/check-coverage.py`:
  - every measured file must have **branch coverage ≥ 80%** (coverage.py's
    branch percentage for the file: covered lines and branches over all);
  - except files in `serve_api/coverage-ratchet.json`, which maps a file to its
    recorded percentage; such a file must not fall below that number;
  - a ratchet file at or above 80% must be removed from the list (the check
    fails and says so), so the list only shrinks;
  - a file not on the list and new files must meet 80% from the start.
- The ratchet list is created in this work from the coverage at the end of it,
  for whatever is still below 80%. Goal for this work: `serve.py` and the method
  modules that do HTTP reach 80%; whatever does not is on the list with the
  reason in the pull request.
- The script is plain Python (stdlib only), tested with its own unit tests on
  small coverage JSON inputs.

### Container end-to-end tests (`e2e`, required)

- A new job `e2e` in `ci.yml`, on pull requests and pushes to `acc` and `main`,
  `needs: build`, `contents: read` only. It reuses the image the `build` job
  produced: `build` writes `cprmv-api:ci` with `docker save` to a workflow
  artifact (pinned `actions/upload-artifact`/`download-artifact`, short
  retention) and `e2e` loads it (my call: a rebuild would be cold on pull
  requests, where the cache is not written). The tier is the one the change is
  headed for: the pull request's base branch, or the pushed branch, mapped with
  `scripts/ci-tier.sh`; a manual run uses `acc` (my call: one check named `e2e`,
  not a matrix whose names would complicate the rulesets; the two compose files
  are kept in step and differ only in host and paths). It starts the image with
  that tier's own `deployment/vm/<tier>/compose.yml` plus a test override file
  that:
  - sets `CPRMV_IMAGE` to the CI image and `CPRMV_ENVIRONMENT=e2e`;
  - mounts `serve_api/test/shim/` and the fixtures read-only and sets
    `PYTHONPATH` so `sitecustomize.py` loads;
  - serves Caddy on plain HTTP only (the `:80` block), since no certificate can
    be obtained in CI.
- `pytest serve_api/test/e2e` then calls `http://localhost` with `httpx`: the
  same routes as the unit tests at a coarser grain (status, content type, key
  triples), plus what only the stack shows: Caddy's security headers, `/mcp`
  answering, `/deploy-status.json` not served by the API, the healthcheck
  turning healthy.
- The job always prints `docker compose logs` on failure and tears the stack
  down.
- After it has reported once, `e2e` is added to both rulesets
  (`.github/rulesets/{acc,main}.json`, applied by script as before).

### Live tests (`e2e-live`, after each acceptance deploy, non-blocking)

- A job `e2e-live` in `ci.yml`, `needs: deploy`, only on push to `acc`,
  `environment: acceptance` (to read `DSO_API_KEY`), `contents: read`,
  `issues: write`.
- `pytest serve_api/test/live` against `https://acc.cprmv.open-regels.nl`: a
  short list of real requests per source, asserting structure (status, content
  type, presence of expected identifiers) rather than exact content, since the
  sources change.
- The DSO tests send `x-api-key: $DSO_API_KEY`; when the secret is absent, they
  are skipped with a clear reason (never fail open as passed).
- A failure opens or updates one tracking issue ("Live end-to-end tests against
  acceptance failing"), closed again when a run passes, the same mechanism as the
  dependency audit. The job itself is marked so a failure does not turn the
  workflow run red (`continue-on-error: true` on the test step, with the issue
  step reporting the outcome).
- Before enabling it: confirm that neither the API (uvicorn access log) nor
  Caddy logs request headers, so the key does not land in the VM's logs.

### Documentation

- `README.md` ("How to" → tests): running unit tests with coverage, the e2e
  suite locally (the compose command), and re-recording fixtures.
- `SECURITY-PIPELINE.md`: the `e2e` check, `e2e-live`, the `DSO_API_KEY`
  environment secret, the coverage floor.

## Rollout

1. Pull request into `acc` with the fake, fixtures, unit tests, the coverage
   check and ratchet, and the `e2e` job. `test` enforces the floor from this
   pull request on. Early in the work the recorder and the DSO request list are
   handed to the user, who records the DSO fixtures; until they are committed,
   the DSO tests are the last part outstanding.
2. After `e2e` has reported: add it to both rulesets.
3. The user adds `DSO_API_KEY` to the `acceptance` environment; a second pull
   request (or the same, if the secret exists by then) enables `e2e-live`.
4. A release `acc` → `main` takes it to stable.

## Risks

- **Fixtures go stale** when a source changes its format; unit and e2e tests keep
  passing while production breaks. The live suite is what notices; its tracking
  issue is the signal to re-record.
- **The shim diverges from real `urlopen`** (an attribute the code later uses
  that the fake does not provide). Mitigation: the fake fails loudly on anything
  unexpected, and the live suite exercises the real path.
- **A floor of 80% on `serve.py`** needs many route tests; if a part of it is
  dead code (several commented-out routes exist), deleting dead code is
  preferred over testing it, in its own commit.

## Left to the builder

- The healthcheck and other loopback requests pass through the fake untouched (it intercepts only outside hosts).
- The exact list of live requests per source (a handful each, representative).
- Fixture file format details (one JSON per response with a separate body file
  is fine).
- Test file split within `unit/`.
- Keeping `e2e/` and `live/` out of the default `pytest` run in the `test`
  job (markers or `testpaths`), and how the ratchet rounds percentages.
