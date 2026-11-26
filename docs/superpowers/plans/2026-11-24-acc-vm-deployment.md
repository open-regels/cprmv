# CPRMV ACC deployment and security pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate `open-regels/cprmv` with lvg's light security pipeline (Part A), then give `acc.cprmv.open-regels.nl` a fresh VM that deploys the head of `acc` by itself and reports what it runs (Part B).

**Architecture:** GitHub Actions tests, builds and pushes `ghcr.io/open-regels/cprmv-api:sha-<commit>`, then polls the VM's public `deploy-status.json`. On the VM a systemd timer runs `reconcile.sh acc` every 2 minutes: anonymous `git fetch`, pull by tag, run by digest, check `/health`, roll back on failure. The VM is created with `az` and bootstraps itself with cloud-init.

**Tech Stack:** Python 3.14, FastAPI, pip-tools (hashed requirements), Docker + Compose, Caddy, POSIX sh + jq, systemd, bats-core, GitHub Actions, zizmor, Semgrep, pip-audit, Renovate, Azure CLI.

**Spec:** `docs/superpowers/specs/2026-11-24-acc-vm-deployment-design.md`

## Global Constraints

- Repository `open-regels/cprmv`, public; `acc` is the default branch. `acc` and `main` change only through pull requests.
- **Two pull requests.** Part A on branch `ci/security-pipeline` (it carries the design and this plan too); Part B on `feat/acc-deployment`, branched from `acc` after A merges. No worktrees.
- **Commits:** every "Commit" step means *stage, report what is staged, ask the user, commit only on their yes*. Never add `Co-Authored-By`, `Claude-Session` or "Generated with Claude Code" lines anywhere. Never `--no-verify`.
- Never start, stop or restart a server the user runs. Throwaway containers this plan names (`cprmv-smoke`, tool images) are fine; remove them afterwards.
- Every Azure write is a script the **user** runs (`! bash ~/<name>.sh`). Read-only `az` is fine.
- **Nothing floats:** actions by full commit SHA with `# vX.Y.Z`; container images by `tag@sha256:digest`; tools at exact versions; Python packages by hash.
- **Pins** (copy exactly):
  - `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`
  - `actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0`, `node-version: '24.22.2'`
  - `actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0`, `python-version: '3.14'`
  - `zizmorcore/zizmor-action@45d7276c9ca790aabd705e31ca99c6185c3e76dd # v0.8.1`, `version: '1.29.0'`
  - `docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069 # v4.4.1`
  - `docker/login-action@8aa5831fb8d48d8f76594c7ddde61ae58019f550 # v4.8.0`
  - `docker/build-push-action@c3c9e263c25d99ce0380d002d59b67737d91b0dc # v7.4.0`
  - `actions/attest-build-provenance@4d101475d8b20a2381f78447822ac1eab6504dd8 # v4.2.2`
  - bats-core `eb7f42f8d608ac693d7a4b67474f6714ea68cfc5 # v1.14.0` (checked out with `actions/checkout`, `repository: bats-core/bats-core`)
  - `semgrep==1.176.1`, `renovate@44.50.3`, `pip-tools==7.6.2` (7.7.0 is younger than the 14-day cooldown), `pip-audit==2.10.1`
  - Python base image and Caddy: tag and digest resolved by the implementer in Tasks A1 and B5, recorded in `SECURITY-PIPELINE.md`.
- **Names shared across tasks:** image `ghcr.io/open-regels/cprmv-api`; tags `sha-<40-char sha>` and `acc`; env vars `BUILD_SHA`, `BUILD_RUN`, `CPRMV_IMAGE`, `CPRMV_IMAGE_DIGEST`; job names `audit`, `scan`, `test`, `build`, `deploy-acc`; compose project `cprmv-<tier>`; status URL `https://acc.cprmv.open-regels.nl/deploy-status.json`.
- Run the API tests as GitLab did: from `serve_api/`, `pytest` (tests import `..src.serve`).
- Local shell tooling runs in containers: `docker run --rm -v "$PWD:/w" -w /w bats/bats:1.14.0 <path>` and `koalaman/shellcheck:v0.11.0`. The user's own acceptance run is the gate, not these.

## Review Focus

1. **The VM loses GitHub (fetch fails, DNS hiccup).** Expect: what runs keeps running, status says so, nothing is torn down. Test: `reconcile.bats` "fetch failure leaves the running release alone" (Task B3).
2. **The very first deploy fails, so nothing to roll back to.** Expect: state `failed`, `running` null, the sha recorded as failed, no retry loop. Test: "first deploy fails with no previous" (Task B3).
3. **The container dies later while the sha is unchanged.** Expect: the next run re-applies the current release instead of saying "nothing to do". Test: "unhealthy current release is re-applied" (Task B3).
4. **The workflow polls before the VM has even fetched the new commit**, so the status shows an older sha running, or an older sha failed. Expect: keep waiting, not fail. Test: `wait-for-deploy.bats` "an older failed sha does not fail this run" (Task B2).
5. **`deploy-status.json` unreachable** (before DNS cutover, VM rebooting). Expect: keep polling until the timeout, then fail with a message naming the URL. Test: "unreachable status keeps polling until timeout" (Task B2).

---

## Part A: security pipeline (branch `ci/security-pipeline`)

- [ ] **Step 0:** `git switch -c ci/security-pipeline` from `docs/acc-vm-deployment-design` (it holds the design commit).

### Task A1: Hash-locked requirements, pinned base image

**Files:**
- Modify: `serve_api/pip-compile.sh` (both `pip-compile` lines), `serve_api/Makefile` (new target), `serve_api/requirements.txt`, `serve_api/requirements-dev.txt`, `serve_api/Dockerfile:1,19-23`

**Interfaces:**
- Produces: `serve_api/requirements*.txt` with `--hash` on every requirement, reproducible by `make deps-linux`; Task A2's `audit` re-runs `./pip-compile.sh` and diffs.

- [ ] **Step 1:** In `pip-compile.sh`, add `--generate-hashes --allow-unsafe --strip-extras` to both `pip-compile` invocations.
- [ ] **Step 2:** Add Makefile target `deps-linux` that runs `./pip-compile.sh "$@"` inside `python:3.14-bookworm@sha256:<digest>` with `pip install pip-tools==7.6.2` first, mounting `serve_api/` (output must match the Linux CI run; a Windows compile can differ in markers). Resolve the digest with `docker buildx imagetools inspect python:3.14-bookworm` and note it for A6.
- [ ] **Step 3:** Run `make -C serve_api deps-linux` (or the equivalent `docker run` if `make` is missing). Expected: both files rewritten, every requirement followed by `--hash=sha256:` lines, header names `--generate-hashes`.
- [ ] **Step 4:** Check that no version changed, only hashes were added: `git diff serve_api/requirements.txt | grep -E '^[-+][a-z0-9_.-]+==' ` shows no removed/added pin pairs other than packages `--allow-unsafe` newly lists (pip/setuptools). Report any version change to the user rather than accepting it.
- [ ] **Step 5:** Dockerfile: `FROM python:3.14-bookworm@sha256:<digest>`; remove the `pip install --upgrade pip setuptools wheel` part; install with `pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt`.
- [ ] **Step 6:** Verify: `docker build -t cprmv-api:local serve_api` succeeds, then `docker run --rm cprmv-api:local python -c "from src.serve import app; print(app.version)"` prints `0.4.3`.
- [ ] **Step 7:** Verify tests still pass in the same environment CI will use: `docker run --rm -v "$PWD/serve_api:/s" -w /s python:3.14-bookworm@sha256:<digest> sh -c "pip install -q --require-hashes -r requirements-dev.txt && pytest"`. Expected: all pass (if `lxml` has no cp314 wheel, prefix `apt-get update && apt-get install -y libxml2-dev libxslt-dev`, as GitLab did, and carry that to Tasks A2/B4).
- [ ] **Step 8: Commit** (ask first): `build(deps): lock requirements with hashes and pin the Python base image`

### Task A2: `audit` job (zizmor, Renovate config, requirements)

**Files:**
- Create: `.github/workflows/zizmor.yml`, `.github/zizmor.yml`, `renovate.json`

**Interfaces:**
- Consumes: A1's `pip-compile.sh` and hashed files.
- Produces: required check `audit`.

- [ ] **Step 1:** `.github/zizmor.yml`: copy lvg's verbatim (rules → `unpinned-uses` → `'*': hash-pin`, with its comment).
- [ ] **Step 2:** `renovate.json`, from lvg's with these differences: `extends` adds `"docker:pinDigests"`; drop the Azure SWA, Tailwind and ESLint rules; the X.0.0 rule matches `"matchDatasources": ["pypi"]` instead of `matchManagers: ["npm"]` (keep `minimumReleaseAge: "14 days"` and the description, reworded for PyPI); add `"pip-compile": { "managerFilePatterns": ["/(^|/)requirements(-dev)?\\.txt$/"] }`. Keep: 14-day minimum age, `prConcurrentLimit: 2`, `internalChecksFilter: "strict"`, vulnerability fast path, majors behind dashboard approval, runner-image majors disabled, Monday lock-file maintenance.
- [ ] **Step 3:** Verify: `npx --yes --package renovate@44.50.3 renovate-config-validator --strict`. Expected: `Config validated successfully`. If `managerFilePatterns` is rejected, the validator names the accepted key; use it.
- [ ] **Step 4:** `.github/workflows/zizmor.yml`: name `Supply-chain audit`, triggers as lvg (`pull_request`; `push` to `acc`, `main`), `permissions: contents: read`, one job with `name: audit`, `runs-on: ubuntu-24.04`. Steps, all but the first two with `if: always()`:
  1. checkout (`persist-credentials: false`); 2. zizmor action (`advanced-security: false`, `annotations: true`, `online-audits: false`);
  3. setup-node + `npx --yes --package renovate@44.50.3 renovate-config-validator --strict`;
  4. setup-python 3.14, `pip install pip-tools==7.6.2`, then `cd serve_api && ./pip-compile.sh && git diff --exit-code -- requirements.txt requirements-dev.txt` (step name: `Requirements match pyproject.toml`);
  5. `pip install --dry-run --ignore-installed --require-hashes --no-deps -r serve_api/requirements.txt` and the same for `requirements-dev.txt` (step name: `Every requirement is hashed`).
- [ ] **Step 5:** Verify locally: `docker run --rm -v "$PWD:/w" -w /w ghcr.io/zizmorcore/zizmor:1.29.0 --offline .github/workflows`. Expected: no findings.
- [ ] **Step 6: Commit** (ask first): `ci: add the supply-chain audit and Renovate configuration`

### Task A3: `scan` job (Semgrep)

**Files:**
- Create: `.github/workflows/semgrep.yml`, `.semgrepignore`

- [ ] **Step 1:** `semgrep.yml`: lvg's, unchanged; job `name: scan`, `semgrep==1.176.1`, `semgrep ci --no-suppress-errors`, secret `SEMGREP_APP_TOKEN` (already set).
- [ ] **Step 2:** `.semgrepignore` with a comment per entry: `docs/` (design and plans), `html/public/` and `serve_api/respec/` (generated ReSpec output, committed as built).
- [ ] **Step 3:** Verify: zizmor command from A2 Step 5 still reports nothing.
- [ ] **Step 4: Commit** (ask first): `ci: add the Semgrep scan`

### Task A4: Daily dependency audit

**Files:**
- Create: `scripts/audit-requirements.sh`, `scripts/pip-audit-accepted.txt`, `scripts/test/audit-requirements.bats`, `scripts/test/fixtures/{shipped-vulnerable,dev-only-vulnerable}/requirements{,-dev}.txt`, `.github/workflows/dependency-audit.yml`

**Interfaces:**
- Produces: `scripts/audit-requirements.sh <label> <requirements.txt> <requirements-dev.txt>`; appends a Markdown section to `$AUDIT_REPORT_FILE`; exit `0` = clean or development-only findings, `2` = a shipped finding or a tool error. Accepted IDs: one per line in `pip-audit-accepted.txt`, `#` comments allowed, each passed as `--ignore-vuln`.

- [ ] **Step 1: Write the failing tests** (`audit-requirements.bats`; needs network, like the real audit):
  - `shipped finding fails`: fixture requirements.txt `urllib3==1.26.4` → status 2, report contains `urllib3` and a `GHSA-`/`PYSEC-` id.
  - `dev-only finding is reported, not failed`: requirements.txt clean (`idna==3.10`), requirements-dev.txt adds `urllib3==1.26.4` → status 0, report contains `urllib3` under a heading containing `development only`.
  - `accepted id is ignored`: shipped fixture plus an accepted file listing every id the first test reported → status 0, report says `accepted`.
  - `clean is clean`: both `idna==3.10` → status 0, report contains `No known advisories`.
- [ ] **Step 2:** Run `docker run --rm -v "$PWD:/w" -w /w bats/bats:1.14.0 scripts/test/audit-requirements.bats`. Expected: FAIL (script missing). The bats image has no Python; the test file's `setup` installs `pip-audit==2.10.1` into a venv if `pip-audit` is absent, or run the suite in `python:3.14-bookworm` with bats-core cloned at the pinned SHA. Use whichever the CI job (Step 5) also uses.
- [ ] **Step 3:** Implement `scripts/audit-requirements.sh`: `pip-audit --disable-pip --no-deps -r <file> --format json` per file, plus `--ignore-vuln` per accepted id; dev-only = dev findings whose package is not in the shipped findings; write the Markdown; exit as in Interfaces. POSIX sh + jq. Accepted-file path overridable by `PIP_AUDIT_ACCEPTED` (tests use it).
- [ ] **Step 4:** Run the suite. Expected: 4 passing. `shellcheck scripts/audit-requirements.sh` clean.
- [ ] **Step 5:** `dependency-audit.yml`: lvg's shape: schedule `17 5 * * *`, `workflow_dispatch`, `pull_request` on its own paths (`.github/workflows/dependency-audit.yml`, `scripts/audit-requirements.sh`, `scripts/pip-audit-accepted.txt`); setup-python 3.14 and `pip install pip-audit==2.10.1`; copy the script and accepted file to `$RUNNER_TEMP`, loop over `acc` and `main` checking each out and running it with `serve_api/requirements.txt serve_api/requirements-dev.txt`; worst status wins; the tracking-issue step copied from lvg with the body text changed to "a known advisory in shipped dependencies (`serve_api/requirements.txt`)"; final step fails on status. Permissions: `contents: read`, `issues: write` on the job only.
- [ ] **Step 6:** Verify: zizmor clean (A2 Step 5).
- [ ] **Step 7: Commit** (ask first): `ci: audit the Python dependencies of acc and main daily`

### Task A5: GitLab for Pages only, and the pipeline record

**Files:**
- Modify: `.gitlab-ci.yml` (whole file)
- Create: `SECURITY-PIPELINE.md`

- [ ] **Step 1:** `.gitlab-ci.yml`: keep `image: node:lts-alpine` and the `create-pages` job exactly as it is now (prebuilt `html/public`, default-branch rule). Delete the variables, stages, Docker anchors and the `test-cprmv-api`, `build-cprmv-api`, `deploy-cprmv-api` jobs. A header comment: development and CI live on GitHub; this file only publishes the ReSpec to `standaarden.open-regels.nl/standards/cprmv/` when `main` is pushed to GitLab at a release.
- [ ] **Step 2:** Verify: `python -c "import yaml,sys; d=yaml.safe_load(open('.gitlab-ci.yml')); assert set(k for k in d if not k.startswith('.'))=={'image','create-pages'}, d.keys()"` passes (install `pyyaml` in a throwaway venv if needed).
- [ ] **Step 3:** `SECURITY-PIPELINE.md`, lvg's structure with CPRMV's content: policy line; manual prerequisites (Renovate app, Dependabot alerts, `SEMGREP_APP_TOKEN`, labels `security` and `ci`, all done on 24 November 2026); the pin register (every pin in Global Constraints, the Python image digest from A1, "Caddy: added by Part B"); the checks table (`audit`, `scan`, `dependency-audit`; `test`, `build`, `deploy-acc` marked "Part B"); the rulesets section (filled in Task A6); the dependency audit rule (shipped = any known advisory, stricter than lvg because pip-audit does not grade severity); an empty accepted-findings table with lvg's explanation of why the table is the record; "Not carried over from lvg, and why" (the spec's five bullets).
- [ ] **Step 4: Commit** (ask first): `ci: keep GitLab for the ReSpec only, and record the security pipeline`

### Task A6: Pull request A, then rulesets

- [ ] **Step 1:** Push `ci/security-pipeline` (ask first), open the pull request into `acc`: what it adds, the manual prerequisites already done, that Renovate's onboarding #3 closes once `renovate.json` is on `acc`, and that `audit` and `scan` become required after merge.
- [ ] **Step 2:** Wait for `audit` and `scan` to report on the pull request; fix what they name. Hand the user the checks to look at and wait for their green and their merge. Do not merge.
- [ ] **Step 3:** After merge, create `.github/rulesets/acc.json` and `main.json` (on Part B's branch, so they are reviewed) and give the user a script to apply them with `gh api -X POST repos/open-regels/cprmv/rulesets --input <file>`: both require a pull request with 0 approvals, merge commits only, `deletion` and `non_fast_forward` blocked, no bypass actors; `acc` requires `audit` and `scan`, `main` requires `audit` and `scan`. Record the returned IDs in `SECURITY-PIPELINE.md`. Close Renovate's #3 if it is still open.
- [ ] **Step 4:** Housekeeping as CLAUDE.md defines it (no GitLab push: not a release).

---

## Part B: the ACC deployment (branch `feat/acc-deployment`, from `acc` after A merges)

### Task B1: `GET /health` and build metadata in the image

**Files:**
- Modify: `serve_api/src/serve.py` (after `cprmv_info`, line ~142), `serve_api/test/test_serve.py`, `serve_api/Dockerfile`

**Interfaces:**
- Produces: `GET /health` →
  `{"status": "ok", "version": app.version, "build": {"sha": BUILD_SHA|null, "run": BUILD_RUN|null}, "image": {"digest": CPRMV_IMAGE_DIGEST|null}}`, read from the environment **per request**; unset or empty → `null`. Image build args `BUILD_SHA`, `BUILD_RUN` become `ENV` and labels.

- [ ] **Step 1: Write the failing tests** in `test_serve.py`:
  - `test_health_reports_build_and_digest`: `monkeypatch.setenv` `BUILD_SHA=abc123`, `BUILD_RUN=42`, `CPRMV_IMAGE_DIGEST=sha256:feed` → status 200 and JSON equals `{"status": "ok", "version": "0.4.3", "build": {"sha": "abc123", "run": "42"}, "image": {"digest": "sha256:feed"}}`.
  - `test_health_reports_null_when_unset`: all three `delenv(raising=False)` → `build == {"sha": None, "run": None}`, `image == {"digest": None}`.
  - `test_health_treats_empty_as_null`: all three set to `""` → same nulls.
  - `test_get_root` stays as it is (unchanged `/`).
- [ ] **Step 2:** `cd serve_api && pytest test/test_serve.py -k health -v`. Expected: 3 FAIL (404).
- [ ] **Step 3:** Implement `def health() -> dict` under `@app.get("/health")` in `serve.py`, with a docstring for `/docs`.
- [ ] **Step 4:** Same command. Expected: 3 PASS; then full `pytest` passes.
- [ ] **Step 5:** Dockerfile: `ARG BUILD_SHA` / `ARG BUILD_RUN` → `ENV BUILD_SHA=$BUILD_SHA BUILD_RUN=$BUILD_RUN`; labels `org.opencontainers.image.revision=$BUILD_SHA`, `org.opencontainers.image.source=https://github.com/open-regels/cprmv`, `org.opencontainers.image.version=0.4.3` replacing the old `version` and GitLab `source` labels; `HEALTHCHECK` fetches `/health`; delete the stale two-line `--app combined_app` comment above `CMD`.
- [ ] **Step 6:** Verify: `docker build --build-arg BUILD_SHA=testsha --build-arg BUILD_RUN=1 -t cprmv-api:local serve_api`; `docker run -d --name cprmv-smoke cprmv-api:local`; `docker exec cprmv-smoke python -c "import urllib.request,json;print(json.load(urllib.request.urlopen('http://localhost:8000/health'))['build'])"` prints `{'sha': 'testsha', 'run': '1'}` (retry for up to 30 s while it starts); `docker rm -f cprmv-smoke`.
- [ ] **Step 7: Commit** (ask first): `feat(api): report build and image on /health`

### Task B2: `wait-for-deploy.sh` (the workflow's verdict)

**Files:**
- Create: `scripts/wait-for-deploy.sh`, `scripts/test/wait-for-deploy.bats`

**Interfaces:**
- Produces: `scripts/wait-for-deploy.sh <status_url> <sha> <repo_url> <branch> <health_url>`; env `WAIT_TIMEOUT` (default 900), `WAIT_INTERVAL` (default 20). Exit 0 when `state != broken`, `running.sha == sha` and `GET <health_url>` reports `build.sha == sha` (the spec: "and `/health` agrees"), or when `git ls-remote <repo_url> refs/heads/<branch>` no longer equals `sha` (prints `superseded by <new sha>`). Exit 1 when `last_attempt.sha == sha` and `last_attempt.result` is `failed` or `restored`, or `state == broken`, or on timeout (message names the URL and last state seen). A failed fetch of the status is not a verdict; keep polling. `status_url` may be `file://` (tests).

- [ ] **Step 1: Write the failing tests** (fixture status files written per test; a local bare repo as `repo_url`; `WAIT_INTERVAL=0`, `WAIT_TIMEOUT=2`):
  - `deployed when running sha matches` → 0.
  - `fails fast when this sha failed` (`last_attempt: {sha: S, result: restored}`) → 1 within one poll, output contains `failed`.
  - `an older failed sha does not fail this run` (last_attempt for another sha, running another sha) → times out → 1 with `timed out`, not `failed` (Review Focus 4).
  - `broken fails` → 1.
  - `superseded when the branch moved` (bare repo head ≠ S) → 0, output `superseded`.
  - `unreachable status keeps polling until timeout` (`file:///nonexistent`) → 1, output names the URL (Review Focus 5).
- [ ] **Step 2:** Run `docker run --rm -v "$PWD:/w" -w /w bats/bats:1.14.0 scripts/test/wait-for-deploy.bats` (install `jq` and `git` in the test's setup if missing, or use the CI image). Expected: FAIL.
- [ ] **Step 3:** Implement in POSIX sh with `curl -fsS` and `jq`.
- [ ] **Step 4:** Run. Expected: 6 PASS; shellcheck clean.
- [ ] **Step 5: Commit** (ask first): `feat(ci): wait for the VM to report the deployed commit`

### Task B3: The reconciler

**Files:**
- Create: `deployment/vm/reconciler/reconcile.sh`, `deployment/vm/reconciler/test/reconcile.bats`, `deployment/vm/reconciler/test/stubs/{docker,curl}`

**Interfaces:**
- Consumes: `compose.yml` reading `${CPRMV_IMAGE}` and `${CPRMV_IMAGE_DIGEST}` from `.env` (Task B4); `/health` (B1).
- Produces: `reconcile.sh <tier>`, exit 0 except on its own errors. Overridable env (defaults): `CPRMV_ROOT` (`/opt/cprmv`), `CPRMV_REPO_URL` (`https://github.com/open-regels/cprmv.git`), `CPRMV_BRANCH` (= tier), `CPRMV_IMAGE_REPO` (`ghcr.io/open-regels/cprmv-api`), `CPRMV_HEALTH_URL` (`http://127.0.0.1:8000/health`), `CPRMV_HEALTH_TIMEOUT` (120 s), `CPRMV_STALLED_AFTER` (1800 s), `CPRMV_INSTALLED_RECONCILER` (`/usr/local/lib/cprmv/reconcile.sh`). Layout under `$CPRMV_ROOT/<tier>/`: `repo/`, `releases/<sha>/`, `current` symlink, `state.json`, `www/deploy-status.json`, `reconcile.lock`. `state.json`: `{running: {sha, digest, since}|null, previous: {sha, digest}|null, failed: [sha], waiting: {sha, since}|null}`. `deploy-status.json`: the spec's schema, plus `warning` (string or null).

The run, in order (spec "One run"): lock (`flock -n`, busy → exit 0 silently) → fetch → idempotence check → failed list → image present → prepare → apply → verify → record → prune → write status atomically (temp file + `mv`).

- [ ] **Step 1: Write the failing tests.** Real `git` against a bare repo with commits containing `deployment/vm/acc/compose.yml`; stubbed `docker` and `curl` on `PATH`, driven by files in `$STUB_DIR` (image present per sha, digest per sha, compose-up failure per sha, health sha served = the sha last brought up, `ps` health). Each test asserts `deploy-status.json` and the stub's call log:
  1. `first run deploys the head`: state `running`, `running.sha` = head, `releases/<head>/.env` has `CPRMV_IMAGE=ghcr.io/open-regels/cprmv-api@sha256:<d>` and `CPRMV_IMAGE_DIGEST=sha256:<d>`, `current` → that release, compose called with `-p cprmv-acc ... up -d --wait --remove-orphans`.
  2. `second run changes nothing`: no `pull`/`up` in the log; only `checked_at` differs.
  3. `image not yet built waits`: state `waiting`, no `up`; with `CPRMV_STALLED_AFTER=0` on the next run → `stalled`; `running` untouched.
  4. `failed deploy restores the previous`: deploy A, then head B with compose failure → `up` for B then for A, state `failed`, `last_attempt.result == "restored"`, `failed` contains B, `running.sha` = A, `last_attempt.error` non-empty.
  5. `wrong sha on /health counts as failure`: health stub serves A while B is brought up → same outcome as 4.
  6. `failed sha is not retried`: rerun on B → no `pull`/`up`.
  7. `new commit after a failure is tried`: head C (good) → running C.
  8. `restore failing is broken`: B fails and A's re-`up` fails → state `broken`.
  9. `first deploy fails with no previous` → state `failed`, `running` null, `failed` contains head, no second `up` (Review Focus 2).
  10. `unhealthy current release is re-applied`: running = head, `ps` reports unhealthy → one `up` for the current release (Review Focus 3).
  11. `fetch failure leaves the running release alone`: repo URL made unreachable → no `up`/`down`, state unchanged, `warning` mentions fetch (Review Focus 1).
  12. `prune keeps current and previous`: after A, B, C → `releases/` holds B and C only.
  13. `reports whether the installed reconciler matches`: `CPRMV_INSTALLED_RECONCILER` pointing at a different file → `reconciler.matches_repo == false`; at the repo copy → `true`.
  14. `a held lock skips the run`: hold `reconcile.lock` with `flock` in the test → exit 0, no calls.
- [ ] **Step 2:** Run `docker run --rm -v "$PWD:/w" -w /w bats/bats:1.14.0 deployment/vm/reconciler/test/reconcile.bats` (the bats image is Alpine: `apk add git jq util-linux` in `setup_file` if absent). Expected: FAIL.
- [ ] **Step 3:** Implement `reconcile.sh` (POSIX sh, `set -eu`, jq for JSON, `git archive <sha> deployment/vm/<tier> | tar -x --strip-components=3` into the release dir). Error text = last 20 lines of compose output.
- [ ] **Step 4:** Run. Expected: 14 PASS; shellcheck clean.
- [ ] **Step 5: Commit** (ask first): `feat(deploy): reconcile the VM from the acc branch`

### Task B4: Compose, Caddy and the systemd units for ACC

**Files:**
- Create: `deployment/vm/acc/compose.yml`, `deployment/vm/acc/Caddyfile`, `deployment/vm/reconciler/cprmv-reconcile@.service`, `deployment/vm/reconciler/cprmv-reconcile@.timer`

- [ ] **Step 1:** `compose.yml`, values from the spec ("Compose and Caddy for acceptance"): `cprmv-api` with `image: ${CPRMV_IMAGE}`, `environment: CPRMV_IMAGE_DIGEST: ${CPRMV_IMAGE_DIGEST}`, healthcheck on `/health`, `restart: unless-stopped`, `ports: ["127.0.0.1:8000:8000"]`, no volumes; `caddy` with `caddy:<2.x>-alpine@sha256:<digest>` (resolve the current 2.x with `docker buildx imagetools inspect`, add it to the pin register), ports 80/443, named volumes `caddy_data`, `caddy_config`, `./Caddyfile:/etc/caddy/Caddyfile:ro`, `/opt/cprmv/acc/www:/srv/status:ro`, `depends_on: cprmv-api: condition: service_healthy`.
- [ ] **Step 2:** `Caddyfile`: site `acc.cprmv.open-regels.nl` plus `:80` fallback for the pre-DNS check; `handle /deploy-status.json` → `root * /srv/status`, `file_server`, `Cache-Control: no-store`; everything else `reverse_proxy cprmv-api:8000`; the five headers exactly as in the spec.
- [ ] **Step 3:** Units: service `Type=oneshot`, `User=cprmv`, `ExecStart=/usr/local/lib/cprmv/reconcile.sh %i`; timer `OnBootSec=1min`, `OnUnitActiveSec=2min`, `Unit=cprmv-reconcile@%i.service`.
- [ ] **Step 4:** Verify: `CPRMV_IMAGE=x CPRMV_IMAGE_DIGEST=y docker compose -f deployment/vm/acc/compose.yml config -q` exits 0; `docker run --rm -v "$PWD/deployment/vm/acc:/c" caddy:<pinned> caddy validate --config /c/Caddyfile --adapter caddyfile` prints `Valid configuration`; `docker run --rm -v "$PWD:/w" -w /w ubuntu:24.04 sh -c "apt-get -qq update && apt-get -qq install -y systemd >/dev/null && systemd-analyze verify deployment/vm/reconciler/*.timer"` reports nothing beyond the missing ExecStart path.
- [ ] **Step 5: Commit** (ask first): `feat(deploy): describe the ACC stack and its timer`

### Task B5: `acc-ci.yml`

**Files:**
- Create: `.github/workflows/acc-ci.yml`

**Interfaces:**
- Consumes: B1 build args, B2 script, B3 and A4 bats suites.
- Produces: checks `test`, `build`, `publish`, `deploy-acc`.

- [ ] **Step 1:** Write the workflow per the spec ("The workflow"), with: triggers `pull_request` (branches `acc`), `push` (branches `acc`, no path filter), `workflow_dispatch`; concurrency `acc-ci-${{ github.event.pull_request.number || github.ref }}`, `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`; top-level `permissions: contents: read`.
  - `test`: setup-python 3.14; `pip install --require-hashes -r serve_api/requirements-dev.txt`; in `serve_api/`: `python -m py_compile src/serve.py`, `python -c "from src.serve import app"`, `pytest`; `shellcheck` (preinstalled on the runner) over `git ls-files '*.sh'` (so scripts added later, such as B6's, are covered without editing the workflow); checkout bats-core at the pinned SHA into `$RUNNER_TEMP/bats` and run `scripts/test` and `deployment/vm/reconciler/test`.
  - `build` (needs `test`): buildx; build `serve_api` with build args `BUILD_SHA=${{ github.sha }}`, `BUILD_RUN=${{ github.run_number }}`, `cache-from/to: type=gha`, `load: true`, tag `cprmv-api:ci`; smoke: run it, poll `/health` up to 60 s, assert `build.sha == github.sha`, remove it. Job permissions: `contents: read` only.
  - `publish` (push on `acc` only, needs `build`; own checkout and buildx): login to `ghcr.io` with `GITHUB_TOKEN`, push `ghcr.io/open-regels/cprmv-api:sha-${{ github.sha }}` and `:acc`, attest with `subject-name: ghcr.io/open-regels/cprmv-api`, `subject-digest` from the push step, `push-to-registry: true`. `create-storage-record: false` on the attestation. Job permissions: `contents: read`, `packages: write`, `id-token: write`, `attestations: write`. Pass `${{ }}` values to `run:` through `env:` (zizmor template-injection).
  - `deploy-acc` (push only, needs `publish`): `environment: {name: acceptance, url: https://acc.cprmv.open-regels.nl}`; checkout; `scripts/wait-for-deploy.sh https://acc.cprmv.open-regels.nl/deploy-status.json "$SHA" https://github.com/open-regels/cprmv.git acc https://acc.cprmv.open-regels.nl/health`.
- [ ] **Step 2:** Verify: zizmor clean (A2 Step 5).
- [ ] **Step 3: Commit** (ask first): `ci: test, build, publish and verify the ACC deployment`

### Task B6: Provisioning and the runbook

**Files:**
- Create: `deployment/vm/acc/provision.sh`, `deployment/vm/acc/cloud-init.yaml`, `deployment/vm/acc/cutover-dns.sh`, `deployment/vm/README.md`; Modify: `SECURITY-PIPELINE.md` (Part B rows), `.github/rulesets/acc.json` (add `test`, `build`)

- [ ] **Step 1:** Ask the user for `! az login --tenant <the ICTU tenant>`. Then read: `az network public-ip list --query "[?ipAddress==<the current VM's public IP>]"` across the three subscriptions, `az vm show` for the current VM (region, size, image), and `az network dns zone list` (resource group and subscription of `open-regels.nl`). Report the values; they become the scripts' defaults.
- [ ] **Step 2:** `provision.sh`: `set -eu`; variables at the top (subscription, `RESOURCE_GROUP=rg-cprmv-acc`, location, `VM_NAME=vm-cprmv-acc`, size, `ADMIN_USER`, `ADMIN_SSH_PUBLIC_KEY` path), `ADMIN_SSH_SOURCE` required from the environment (refuse to run without it; never written to a file). Each resource `show` first, `create` only if missing: NSG with rules 80 and 443 from `*`, 22 from `$ADMIN_SSH_SOURCE`; vnet/subnet; static Standard public IP; VM `Ubuntu2404` (x86-64) with `--custom-data cloud-init.yaml`, no password auth. Ends by printing the public IP and the two check URLs (`http://<ip>/health`, `http://<ip>/deploy-status.json`).
- [ ] **Step 3:** `cloud-init.yaml`: Docker's apt repository and `docker-ce docker-ce-cli containerd.io docker-compose-plugin`, `git jq util-linux`; user `cprmv` in group `docker`, no login shell; `/opt/cprmv/acc` and `/opt/cprmv/acc/www` owned by `cprmv` (no clone: the reconciler creates its own bare repository in `repo/` on its first run); install `reconcile.sh` to `/usr/local/lib/cprmv/` and the units to `/etc/systemd/system/`; `systemctl enable --now cprmv-reconcile@acc.timer`.
- [ ] **Step 4:** `cutover-dns.sh`: reads the new IP from the public IP resource; refuses unless `curl -fsS http://<ip>/deploy-status.json` reports `state == running`; then `az network dns record-set a` sets `acc.cprmv` in `open-regels.nl` to exactly that IP (replace, not add) with TTL 300, and prints the old and new values.
- [ ] **Step 5:** `deployment/vm/README.md`: what the VM needs (spec section, with the outbound list), provisioning (who runs what), the status file and how to read it, what each state means and what to do (`broken` is the only one that needs a person), installing a changed reconciler (SSH, or reprovision), and adding a tier.
- [ ] **Step 6:** Verify: shellcheck clean on both scripts; `docker run --rm -v "$PWD/deployment/vm/acc:/c" ubuntu:24.04 sh -c "apt-get -qq update && apt-get -qq install -y cloud-init >/dev/null && cloud-init schema --config-file /c/cloud-init.yaml"` → `Valid schema`.
- [ ] **Step 7:** `SECURITY-PIPELINE.md`: Caddy and the Part B actions in the pin register, `test`/`build`/`deploy-acc` in the checks table. `.github/rulesets/acc.json`: add `test`, `build`.
- [ ] **Step 8: Commit** (ask first): `feat(deploy): provision the ACC VM with az and cloud-init`

### Task B7: Pull request B and the rollout (spec "Rollout" 3–6)

- [ ] **Step 1:** Push and open the pull request into `acc` (ask first). Say that `deploy-acc` will time out on the first merge, since no VM listens yet. Wait for the user's green and merge.
- [ ] **Step 2:** After merge: the user makes `cprmv-api` public in the package settings and links it to the repository; check with `docker logout ghcr.io; docker manifest inspect ghcr.io/open-regels/cprmv-api:sha-<merge sha>` → succeeds. Give the user the ruleset update script (`test`, `build` on `acc`).
- [ ] **Step 3:** Hand the user `! ADMIN_SSH_SOURCE=<their address> bash ~/provision-cprmv-acc.sh` (copied from `deployment/vm/acc/provision.sh`). Then poll `http://<ip>/deploy-status.json` until `running` with the head of `acc`, and `http://<ip>/health`.
- [ ] **Step 4:** Hand the user `! bash ~/cutover-dns-cprmv-acc.sh`. Check `https://acc.cprmv.open-regels.nl/health` once the certificate is issued. Ask the user to stop the old VM's acc container.
- [ ] **Step 5:** Prove it: a small pull request (a `CHANGELOG.md` entry for the deployment) merged into `acc` reaches the VM with `deploy-acc` green; then ask the user to run `sudo -u cprmv /usr/local/lib/cprmv/reconcile.sh acc` twice over SSH and confirm `deploy-status.json` changes only `checked_at`.
- [ ] **Step 6:** Delete the copied `~/*.sh` scripts; housekeeping.
