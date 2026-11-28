# The dependency register gate for Python — design

Date: 2026-11-28 · Repository: open-regels/cprmv · Base branch: `acc`

The same gate as in linked-data-explorer (#368), ttl-editor (#276), ronl-business-api (#503) and lvg (#49),
for a Python project. Their design: linked-data-explorer
`docs/superpowers/specs/2026-11-27-dependency-register-gate-design.md`. The criteria stay in
linked-data-explorer's `docs/dependency-criteria.md`, the one copy all repositories link to.

## 1. Intent

In the four npm repositories a new direct dependency now blocks the merge until a committed,
evidence-checked assessment exists, and every version a lockfile adds or changes must be at least 14 days
old (ICTU recommendations 1 and 6). CPRMV has neither. The shared scripts read `package-lock.json` and the
npm registry, so they cannot run here; this design gives CPRMV the same rules in Python, from PyPI and
GitHub evidence. The owner chose this (approach A) on 2026-11-28.

## 2. What is true today

- **Direct dependencies** are declared unpinned in `serve_api/pyproject.toml`: six runtime
  (`fastapi[standard]`, `rdflib`, `parse`, `lxml`, `ciso8601`, `fastmcp`), the `dev` extra (`pytest`,
  `pytest-cov`, `httpx`, `pre-commit`) and the `tools` extra (`bandit`, `black`, `mypy`, `ruff`, `vulture`).
- **Pins** are compiled with hashes by pip-tools 7.6.2 (`serve_api/pip-compile.sh`, `serve_api/Makefile`
  `deps-linux`): `requirements.txt` (runtime, 98 pins) and `requirements-dev.txt` (`--extra=dev,tools`,
  constrained by `requirements.txt`, 122 pins).
- **Checks** (`SECURITY-PIPELINE.md`, "Checks"; rulesets 28148785/28148786 require `audit`, `scan`, `test`,
  `build` on both branches): `audit` recompiles both files with `./pip-compile.sh` and fails on any
  difference, and installs both with `--require-hashes --dry-run`; `dependency-audit` runs `pip-audit` daily;
  `release-sbom` keeps an SBOM per release (`serve_api/RELEASE`, CalVer).
- **No review of what a requirements change brings in**, no gate on new direct dependencies, no quarterly
  maintenance review, and no cooldown below Renovate's own `minimumReleaseAge` (14 days, `renovate.json`).
- **Renovate does not pass a cutoff to pip-compile.** Its package-manager cooldown sync covers npm, pnpm,
  Yarn, Poetry and Cargo only (docs.renovatebot.com, key-concepts/minimum-release-age). Transitive pins
  Renovate resolves are not age-limited today. `constraints.pipTools` is marked deprecated in Renovate's
  options (TODO #42599).
- **Labels:** `security` and `ci` exist; `dependencies` was created by the owner on 28 November 2026 for
  the quarterly review.
- **Existing Python tooling:** `scripts/write-sbom.py` (stdlib, tested by `scripts/test/test_write_sbom.py`
  under pytest), bats for shell scripts. Python 3.14 in every workflow.

### PyPI evidence, measured 2026-11-28 on the 15 direct dependencies

| Criterion | Source | Quality |
|---|---|---|
| Maintained | Simple API JSON `project-status` (PEP 792: active / archived / deprecated / quarantined); JSON API per-file `upload_time_iso_8601` (last release); per-file `yanked` | Good. All 15 `active` today |
| Maintainers | JSON API top-level `ownership`: `roles[]` (`Owner`/`Maintainer`, user) and `organization` (PEP 752) | Good. fastapi: 1 owner, no org; bandit: PyCQA, 3 |
| Licence | `info.license_expression` (PEP 639), else `info.license`, else `License ::` classifier | Mixed. 9 of 15 give SPDX `license_expression`; vulture's `license` is the full licence text |
| Release policy | Integrity API (PEP 740) / Simple API per-file `provenance`: trusted publisher (repo, workflow) | Positive signal only. Attested: pytest, bandit, black |
| Footprint | Wheel tags of the locked version's files: pure (`py3-none-any`) vs platform wheels; no wheel for the target (`cp314`, `manylinux`) means a source build, the closest analogue of npm install scripts | Good |
| Repository | `info.project_urls` (free-form keys) | Mixed. 6 of 15 point at a docs site, not GitHub |

Upload time is per file, not per release. Cooldown: pip 26.0 added `--uploaded-prior-to`, pip 26.1 the
`P<n>D` duration form; pip-tools 7.6.2's `pip-compile --uploaded-prior-to P14D` works with pip ≥ 26.1 (tested:
it resolved an older `parse`).

## 3. Approaches

| | What | Trade-off |
|---|---|---|
| **(A) The same gate in Python** — **chosen** | Stdlib-only scripts in the style of `write-sbom.py`; same register shape, criteria, ways through and comment as the npm gate; PyPI + GitHub evidence | A second implementation of the same rules, in another language |
| (B) Teach the shared Node gate to read PyPI | One implementation | A second ecosystem in a script five repositories carry; Node deciding a Python repository's dependencies, which "Not carried over from lvg" avoided on purpose |
| (C) Package-manager cooldown only, the rest "not carried over" | Small | R1 does not move; Renovate's transitive pins stay unchecked |

## 4. Design

### 4.1 Scripts (stdlib only, Python 3.14)

| Script | Role | npm counterpart |
|---|---|---|
| `scripts/requirements_review.py` | Compares base and head of both requirements files: pins added, removed, updated, downgraded; packages whose pin lost its hashes or gained a non-PyPI source fail outright. Every **added** pin is looked up on PyPI and its licence (4.4 precedence) and wheel availability are listed, non-blocking, as the npm review lists new licences and install scripts (*my call*; the cooldown check fetches the same data) | `lockfile-diff.mjs` |
| `scripts/dependency_gate.py` | New direct dependencies (per group) against the register, with gathered evidence; the 14-day cooldown on every added or changed pin; the Renovate security route; the comment section | `dependency-gate.mjs` |
| `scripts/dependency_review.py` | Quarterly: every direct dependency's evidence; open overrides, `replace` outcomes, the previous quarter's Renovate security exceptions | `dependency-review.mjs` |

Module names use underscores so the tests import them; tests in `scripts/test/` under pytest, like
`test_write_sbom.py`, with no network (an injectable fetch). Exit codes as in the npm gate: 0 clean, 1
blocking, 2 could not evaluate — never clean on a network, parse or API error.

### 4.2 What "new direct dependency" means

Parsed from `serve_api/pyproject.toml` with `tomllib`. A dependency is new when its name, normalised per
PEP 503 (lower case, runs of `-_.` → `-`), is in a **group** of head and not in that same group of base. Groups: `runtime` (`[project.dependencies]`) and each optional-dependency extra (`dev`, `tools`).
Moving a package between groups is a new entry for the new group (it changes where it runs, the npm gate's
per-manifest rule). Extras in a requirement (`fastapi[standard]`) are part of the requirement, not of the
name. *My call:* groups play the part npm manifests play; the register's `manifest` field holds the group
name.

### 4.3 The register: `serve_api/dependency-register.json`

The npm register's shape (`dependencies[]`, `cooldownOverrides[]`, six criteria `maintained`,
`maintainers`, `licence`, `releasePolicy`, `footprint`, `needed`, `outcome`, `followUp`, `status`,
`override`, `assessed.version`), with `manifest` = group, plus two optional fields PyPI makes necessary:

- `licence` (SPDX string) — required when PyPI gives no parseable licence (see 4.4);
- `repository` (`owner/name` on GitHub) — required when `project_urls` names no GitHub repository.

Same rules: a `why` of at least 40 characters, distinct within an entry; `needed` always has one; every
`holds: false` has one; the assessed major equals the locked major; referenced issues exist, are issues
(not pull requests) and are open. It starts with retroactive entries for the 15 direct dependencies (4.8).

**Every register change is judged against evidence** (*my call*, stricter than the npm gate, which only
shape-checks a register-only change): whenever `serve_api/dependency-register.json` changes, each entry it
adds or changes is evaluated against fetched PyPI and GitHub evidence, as a new dependency would be. This
covers the retroactive entries on this change's own pull request, and an entry weakened later.

### 4.4 Signals from PyPI

| Criterion | Fails (must be `holds: false` with a why) |
|---|---|
| maintained | `project-status` not `active` (archived/deprecated/quarantined → blocking unless `outcome: replace` with an open follow-up); locked version yanked (blocking, same exception); no release in 12 months; status or upload times unavailable |
| maintainers | `ownership.roles` has one user and `organization` is null, or ownership is unavailable |
| licence | Resolved licence (`license_expression`, else `license` if it parses as an SPDX expression, else the classifier mapped to SPDX, else the entry's `licence`) not on the allow-list; none resolvable and no `licence` in the entry → blocking |
| footprint | No `py3-none-any` wheel and no wheel matching the image's target (Python 3.14, `manylinux` x86_64) for the locked version → the pin builds from source |
| releasePolicy | — (a judgement; a trusted-publisher attestation is shown as evidence when present) |
| needed | — (always a judgement) |

The allow-list is a new `serve_api/lockfile-review.json` (`allowLicenses`, `minReleaseAgeDays: 14`), started
from the licences already in `requirements.txt` that are on the npm repositories' list, so a new one gets
looked at. GitHub evidence (archived, owner type) from the resolved repository, as in the npm gate. A
dependency whose source is not on GitHub has `"repository": null` with a reason in the entry; the
archived check cannot run, so `maintained` must be `holds: false` with a why — the npm gate's "repository
not checked" rule (*my call*). A GitHub repository that answers 404 is evidence the same way, not an
error; any other GitHub or PyPI failure exits 2.

### 4.5 Cooldown

- **At PR time (the gate):** every pin added or changed in either requirements file must have been uploaded
  at least 14 days before the run. "Uploaded" is the earliest upload time of that version's files
  (pip-compile resolves the version, and its hashes list every file). Younger → blocking for a person's
  pull request; ways through as in 4.6.
- **At the package manager (developer path):** the Makefile's `deps-linux`/`deps-upgrade` set the
  environment variable `PIP_UPLOADED_PRIOR_TO=P14D` and install pip ≥ 26.1 next to pip-tools 7.6.2.
  Measured 2026-11-28: pip-compile applies the cutoff from the variable (a cutoff of 1 October resolved
  `parse` 1.22.2 instead of 1.22.4) and **does not write it into the requirements header**. The flag
  `--uploaded-prior-to` cannot be used: pip-compile records it in the header (measured), `audit` recompiles
  with `./pip-compile.sh` and compares byte for byte, and Renovate's pip-compile manager rejects any header
  option outside its list with "Option … not supported (yet)" (`lib/modules/manager/pip-compile/common.ts`
  L306-317), so it would stop maintaining the file. `audit`'s recompile sets no variable and keeps the
  committed pins, so it is unaffected.
- **Renovate's routine pull requests — owner's decision (b), 2026-11-28.** Hosted Renovate cannot be given
  the variable, so every Renovate pull request re-resolves transitive pins with no cutoff, and the weekly
  lock-file maintenance almost always brings at least one pin younger than 14 days. Blocking them would
  stop the maintenance for good (a new young pin every week); our own maintenance workflow (with a token
  that triggers CI and write rights) was judged too heavy for now. So for any pull request whose author is
  `renovate[bot]`, young pins are **logged, not blocked**: listed in the comment and the job summary, and
  in the quarterly review. The new-dependency rules still apply to them. Renovate's own updates already
  wait `minimumReleaseAge` (14 days) for the package they update. Written down as the remaining exception:
  for CPRMV's transitive tree, the cooldown is enforced on people's changes and logged on Renovate's.

### 4.6 Ways through, each logged

As in the npm gate: a committed override in the register (`status: "override"` with an open issue, or a
`cooldownOverrides` entry), or a Renovate security pull request — author `renovate[bot]` and the
`security` label applied by `renovate[bot]`, read from the issues API, waiting up to 60 s for Renovate's
labels. The gate writes the exception into the comment and the job summary; the quarterly review lists
them. Unlike the npm gate, the cooldown on a **routine** Renovate pull request is also logged rather than
blocking (4.5); a Renovate security pull request additionally passes the new-dependency rules with a
warning, as in the npm gate. The author is read from the event, never from anything a person can set.

### 4.7 CI

- **`requirements-review` job** in `zizmor.yml` (one job, one required check, like `lockfile-review`):
  script tests and `--check-register` first, then — when either requirements file changed — the review and
  the gate, worst status wins, one comment (`<!-- requirements-review -->`) with a verdict list at the top
  that truncation never cuts, posted by a `requirements-review-comment` job with no checkout. Values
  through `env:` only; no `labeled` trigger; permissions `contents: read`, `issues: read`,
  `pull-requests: read`.
- **`dependency-review.yml`**: quarterly, opens one issue labelled `dependencies` (the label exists since
  28 November 2026).
- The owner adds `requirements-review` to both rulesets after it has reported once, and updates
  `.github/rulesets/acc.json` / `main.json`, which this repository keeps as the record.

### 4.8 Retroactive assessments

The 15 direct dependencies predate any checklist here, but CPRMV has no register yet and they are few, so
each gets an entry from evidence gathered by the new script (*my call*, unlike LVG's empty start: here the
gate also needs `licence` and `repository` fields the evidence cannot supply for some). Licence or
repository gaps go in the entries; anything that does not hold gets its sentence or a follow-up issue.

### 4.9 Documentation

`SECURITY-PIPELINE.md`: the new check in "Checks", sections on the register gate and the cooldown, the
remaining exception (Renovate's pip-compile), and "Not carried over from lvg" no longer listing this.
`serve_api/Makefile` and `pip-compile.sh` comments.

## 5. Goals, non-goals, anti-goals

- **Goals:** a new direct dependency in any group, or a too-young pin in a person's change to either
  requirements file, blocks `requirements-review`; young pins in Renovate's pull requests are logged; the
  same logged ways through; the 15 assessed and checked against evidence; the docs say so.
- **Non-goals:** changing the npm gate or its scripts; uv or Poetry; making `--only-binary` an install rule
  (footprint is a signal, not a policy).
- **Anti-goals:** a gate that passes when PyPI or GitHub cannot be read; a cutoff in the requirements
  header (breaks Renovate and `audit`); a check that a label a person sets can satisfy; a cooldown that
  stops Renovate's maintenance for good.

## 6. Done when

- `requirements-review` passes on its own pull request, having judged all 15 entries against fetched
  evidence (4.3).
- `make deps-linux` compiles with the cutoff and leaves the header unchanged, so `audit` stays green.
- A throwaway draft pull request adding a dependency to `[project.dependencies]` (with recompiled
  requirements) without an entry fails it.
- The owner has added the check to both rulesets and the JSON records match.
- `SECURITY-PIPELINE.md` and the Makefile say what is true.
