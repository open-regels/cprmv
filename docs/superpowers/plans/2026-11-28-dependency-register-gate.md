# Dependency register gate for Python — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CPRMV gets a required `requirements-review` check that blocks a new direct dependency (per `pyproject.toml` group) until `serve_api/dependency-register.json` holds an assessment consistent with PyPI and GitHub evidence, blocks pins younger than 14 days in people's changes (logs them in Renovate's), plus a quarterly review and a developer-side cooldown.

**Architecture:** Three stdlib-only Python modules in `scripts/` (`requirements_review.py`, `dependency_gate.py`, `dependency_review.py`) sharing small helpers, tested with pytest and an injectable fetch; one `requirements-review` job (+ comment job) in `zizmor.yml`; `dependency-review.yml` quarterly; the Makefile sets `PIP_UPLOADED_PRIOR_TO=P14D`.

**Tech Stack:** Python 3.14 stdlib (`tomllib`, `json`, `urllib.request`, `re`), pytest 9.1.1 (as `sbom.yml` pins), GitHub Actions, PyPI JSON / Simple JSON / Integrity APIs, GitHub REST API.

**Spec:** `docs/superpowers/specs/2026-11-28-dependency-register-gate-design.md`

## Global Constraints

- Rules are the npm gate's, read from linked-data-explorer `scripts/dependency-gate.mjs` (`C:\Users\gorts01\Development\linked-data-explorer`, `acc`) where the spec is silent: register shape and validation, why ≥ 40 characters and distinct, `needed` always has a why, every `holds: false` has one, assessed major = locked major, referenced issues exist / are issues / are open, exit codes 0 clean · 1 blocking · 2 could not evaluate (never clean on a fetch, parse or API error), the Renovate security route (author `renovate[bot]` from the event AND `security` applied by `renovate[bot]` per the issues API, labels polled up to 60 s), comment escaping of every registry-sourced string.
- CPRMV differences (spec): groups `runtime`/`dev`/`tools` are the manifests; names normalised per PEP 503; extra register fields `licence` (SPDX) and `repository` (`owner/name` or `null` with a reason); every register change judged against evidence; added pins looked up (licence, wheels), non-blocking; **Renovate's routine pull requests: young pins logged, not blocked** (owner's decision (b)); footprint = no `py3-none-any` and no wheel for CPython 3.14 manylinux x86_64.
- Paths: register `serve_api/dependency-register.json`, policy `serve_api/lockfile-review.json` (`allowLicenses`, `minReleaseAgeDays: 14`), requirements `serve_api/requirements.txt` (runtime) and `serve_api/requirements-dev.txt` (`dev`,`tools`, constrained by runtime).
- Workflow values through `env:` only; no `labeled` trigger; minimal permissions; pins by digest like the existing workflows.
- Never a cutoff in `pip-compile.sh` or the requirements header (breaks `audit` and Renovate).
- Global CLAUDE.md: implementers stage only, never commit; the controller asks the owner before every commit; no Claude attribution; never bypass hooks; never start/stop servers; the owner merges every PR and edits rulesets. No heredocs for long content.

## Review Focus

1. A package with a docs-site `project_urls` and no `repository` in its entry → exit 1 with a message naming the missing field, never exit 2 or a pass — test in Task 2.
2. `vulture`-style `license` (full licence text) → not parsed as SPDX; falls to the classifier; with neither, the entry's `licence` is required — test in Task 2.
3. A yanked locked version of a direct dependency → blocking unless `outcome: replace` with an open follow-up — test in Task 2.
4. Renovate routine PR (author `renovate[bot]`, no `security` label) with a 3-day-old transitive pin → logged under "Cooldown exceptions", exit 0; the same PR by a person → exit 1 — test in Task 3.
5. A `requirements-dev.txt`-only change (Renovate bumps a dev tool): runtime file unchanged, dev pins reviewed, group `dev`/`tools` new-dependency rules apply — test in Task 3.

---

### Task 1: Shared parsing — requirements, pyproject, register, policy

**Files:**
- Create: `scripts/gate_common.py`, `scripts/test/test_gate_common.py`
- Create: `serve_api/lockfile-review.json` (`$comment`; `allowLicenses` = the npm repositories' list — MIT, ISC, Apache-2.0, BSD-2-Clause, BSD-3-Clause, BlueOak-1.0.0, 0BSD, MIT-0, Unlicense, CC0-1.0, Python-2.0, CC-BY-4.0 — plus any further SPDX licence already present among `requirements.txt`'s pins that the owner would expect, reported rather than added if not obviously permissive; `minReleaseAgeDays: 14`)
- Modify: `.gitignore` (`.superpowers/`)

**Interfaces (Produces):**
- `normalise(name: str) -> str` (PEP 503).
- `parse_requirements(text: str) -> dict[str, Pin]` — `Pin(name, version, hashes: list[str], source: str|None)`; tolerates comments, `\` continuations, `# via` blocks; raises `InputError` on a pin without `==` or hashes.
- `direct_groups(pyproject_text: str) -> dict[str, set[str]]` — `{'runtime': {...}, 'dev': {...}, 'tools': {...}}`, names normalised, extras stripped (`fastapi[standard]` → `fastapi`).
- `new_direct(base_groups, head_groups) -> list[tuple[name, group]]` — per group.
- `parse_register(text) -> Register` and `parse_policy(text) -> Policy` — the npm shapes plus `licence`/`repository` fields; errors name the entry and field.
- `InputError`, `code(s: str) -> str` (markdown code span: backticks → `'`, newlines → space).

- [ ] Failing tests: PEP 503 cases (`Ruamel.YAML`, `zope_interface`); a real excerpt of `serve_api/requirements.txt` parses to name/version/hashes; a pin without hashes raises; `direct_groups` on `serve_api/pyproject.toml` gives the 6/4/5 names; moving `httpx` from `dev` to `runtime` → `[('httpx','runtime')]`; register: duplicate (name, group) raises, `replace` without `followUp` raises, `repository: null` without a reason (`repositoryWhy` ≥ 40 chars) raises; policy without `minReleaseAgeDays` raises.
- [ ] `python -m pytest scripts/test/test_gate_common.py` → FAIL, implement, → PASS.
- [ ] Stage; report the licences found among the runtime pins that are not on the list (for the owner).

### Task 2: Evidence and signals (no network in tests)

**Files:**
- Create: `scripts/pypi_evidence.py`, `scripts/test/test_pypi_evidence.py` (fixtures: trimmed real JSON from PyPI for fastapi, lxml, vulture, bandit saved under `scripts/test/fixtures/pypi/`)

**Interfaces:**
- Consumes Task 1.
- Produces: `fetch_json(url, *, fetch=urllib, retries=3, timeout=30) -> dict` (retry 429/5xx/timeouts, honour `Retry-After` capped at 60 s, raise `FetchError` with `.status`); `Evidence` dataclass (`last_release`, `status`, `yanked`, `owners`, `organisation`, `licence`, `licence_source`, `repository`, `pure_wheel`, `target_wheel`, `attested_by`, `upload_time(version)`); `gather(name, version, *, fetch, token) -> Evidence` (JSON API + Simple JSON for `project-status` and `provenance` + GitHub repo, 404 → `archived=None`, `repo_note='repository not found'`); `resolve_licence(info) -> (spdx|None, source)` (precedence `license_expression` → `license` if it parses as an SPDX expression → classifier mapped (MIT, BSD → `BSD-3-Clause` only if unambiguous else None, Apache Software → Apache-2.0, ISC, PSF → Python-2.0) → None); `signals(evidence, entry, now, policy) -> dict[criterion, reason|None]` and `fatal`.

- [ ] Failing tests for every Review Focus 1–3 case, plus: `status` archived → fatal; one owner, no organisation → maintainers signal; bandit (organisation PyCQA) → no maintainers signal; no release in 13 months → maintained; lxml without a target wheel in a fixture → footprint signal, with a `cp314-…manylinux…x86_64` wheel → none; `fetch_json` retries 429 twice then succeeds, gives up after 3 → `FetchError`.
- [ ] Implement; tests PASS. Stage; report.

### Task 3: The gate and the requirements review (CLI)

**Files:**
- Create: `scripts/dependency_gate.py`, `scripts/requirements_review.py`, `scripts/test/test_dependency_gate.py`, `scripts/test/test_requirements_review.py`

**Interfaces:**
- `requirements_review.py <base-dir> <head-dir> --config serve_api/lockfile-review.json --out f` — compares `requirements.txt` and `requirements-dev.txt` under each dir: added / removed / updated / downgraded, blocking on a pin without hashes or a non-PyPI source, and for every added pin (fetched) its licence (off-list → listed) and wheel availability. Exit 0/1/2.
- `dependency_gate.py <base-dir> <head-dir> --config … --register serve_api/dependency-register.json --out f` and `--check-register [--register f]` (offline shape check; absent file → note, exit 0). Evaluates: new direct per group; every register entry added or changed between base and head; the cooldown on every added/changed pin (earliest file upload time of that version). Env: `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `PR_AUTHOR`, `PR_NUMBER`. Renovate: author `renovate[bot]` → cooldown logged; + `security` by `renovate[bot]` (issues events API, labels polled ≤ 60 s) → new-dependency rules warn instead of block. Exit 0/1/2.
- Both write a markdown section; a `combine_comment(sections, statuses) -> str` in `dependency_gate.py` builds `<!-- requirements-review -->`, a verdict list per part at the top, then the sections, truncated at 65 536 characters from the end.

- [ ] Failing tests (fake fetch, temp dirs): Review Focus 4 and 5; missing entry → blocking; entry contradicting a signal → blocking; changed register entry re-judged even with no requirements change; override with open issue → pass + warning; PR number as issue → blocking; `--check-register` malformed → exit 2; a fetch failure → exit 2 with a "could not run" section; comment marker once, verdict list survives truncation.
- [ ] Implement; tests PASS. Live smoke (read-only network, `GITHUB_TOKEN=$(gh auth token)`, `GITHUB_REPOSITORY=open-regels/cprmv`, `PR_AUTHOR=someone`, `PR_NUMBER=0`): base = a scratch copy of `serve_api/` from `origin/acc`, head = the same with one direct dependency added to `[project.dependencies]` and its pin added to `requirements.txt` → exit 1 naming it. Stage; report.

### Task 4: Register with the 15 retroactive entries

**Files:**
- Create: `serve_api/dependency-register.json`

- [ ] Gather evidence for the 15 with `scripts/pypi_evidence.py` (a small throwaway driver in the scratchpad, not committed). Write each entry: group, `added` (the commit that introduced it — `git log -S` on `serve_api/pyproject.toml`, PR number if any, else `null` + `commit`), `assessed` (2026-11-28, locked version from `requirements.txt` / `requirements-dev.txt`), six criteria honest against the evidence, `licence`/`repository` where PyPI cannot supply them, `outcome`, `followUp` where needed.
- [ ] Anything that does not hold gets its sentence; a replacement candidate becomes a follow-up issue — the controller asks the owner once before creating issues.
- [ ] Verify: `dependency_gate.py` with base = `serve_api/` without the register and head = with it → all 15 entries judged, exit 0. Stage; report.

### Task 5: CI, quarterly review, developer cooldown, docs

**Files:**
- Modify: `.github/workflows/zizmor.yml` (jobs `requirements-review`, `requirements-review-comment`), `serve_api/Makefile` (`deps-linux`: `-e PIP_UPLOADED_PRIOR_TO=P14D`, `pip install -q pip==26.3 pip-tools==7.6.2`; a comment why the variable and not the flag), `serve_api/pip-compile.sh` (comment only: never add `--uploaded-prior-to`), `SECURITY-PIPELINE.md` ("Checks", new sections on the register gate and the cooldown with the Renovate exception, "Not carried over from lvg" updated, "Branch rulesets" with the step for the owner), `.github/rulesets/acc.json` and `main.json` (add `requirements-review`, to be applied by the owner after its first run)
- Create: `.github/workflows/dependency-review.yml` (quarterly, label `dependencies`), `scripts/dependency_review.py` (+ test)

- [ ] Job `requirements-review`: checkout (base fetched), Python 3.14, `pip install pytest==9.1.1`, run the four test files, `--check-register`, then if either requirements file or the register changed: export base `serve_api/` with `git archive`/`git show`, run the review and the gate, worst status (>2 → 2), combine, write the report output with a random delimiter; comment job by marker, no checkout, same-repo only.
- [ ] Validate: YAML parse, `bash -n` on run blocks, `uvx zizmor@1.29.0 --offline` → no new findings; simulate the step locally against scratch dirs (no lockfile change → exit 0; added dependency without entry → exit 1; malformed register → exit 2).
- [ ] `make deps-linux` is the owner's (Docker); hand it over: after it, `git diff -- serve_api/requirements*.txt` shows no header change.
- [ ] Stage; report.

### Task 6: Pull request, proof, rulesets

- [ ] The owner runs `python -m pytest scripts/test` and `make deps-linux` (no header change); green → controller asks to commit, push, open the PR into `acc`.
- [ ] On the PR: `requirements-review` judges all 15 entries (register changed) and passes. Controller asks before a throwaway draft PR (API-created, base = this branch) adding a runtime dependency + its pins without an entry; confirm the failure; close; delete the branch.
- [ ] After merge: the owner applies `.github/rulesets/acc.json` (and `main.json` after the first promotion) with `requirements-review`.
