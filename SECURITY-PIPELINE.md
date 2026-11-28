# Pipeline supply-chain posture

Policy: nothing a pipeline downloads or runs may float. Use a commit hash, digest,
exact version or package hash wherever one exists. This is `sgort/lvg`'s light
pipeline, ported from npm to Python. `acc` is the integration branch and `main` is
the stable release.

Development and CI live on GitHub (`open-regels/cprmv`). GitLab only publishes the
ReSpec: `.gitlab-ci.yml` holds the `create-pages` job and nothing else, and
`main` is pushed there at a release.

## Manual prerequisites

All done on 24 November 2026 by the `open-regels` organisation admin.

- The Renovate (Mend) GitHub App has access to `open-regels/cprmv`. Its onboarding
  pull request (#3) was closed once `renovate.json` was on `acc`.
- Dependabot alerts are enabled. Renovate's fast route for security fixes depends
  on them.
- `SEMGREP_APP_TOKEN` is set as a repository secret.
- The issue labels `security` and `ci` exist, for the daily dependency audit.
- The issue label `dependencies` exists (created 28 November 2026), for the
  quarterly dependency review.

## Pinned

| Dependency                       | Pin                                                                                         | Version | Maintained by                                    |
| -------------------------------- | ------------------------------------------------------------------------------------------- | ------- | ------------------------------------------------ |
| `actions/checkout`               | `3d3c42e5aac5ba805825da76410c181273ba90b1`                                                  | v7.0.1  | Renovate                                         |
| `actions/setup-node`             | `949feb2413d6458794dcd2491c4babbbce0c15c1`                                                  | v7.1.0  | Renovate                                         |
| `actions/setup-python`           | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0`                                                  | v7.1.0  | Renovate                                         |
| `zizmorcore/zizmor-action`       | `45d7276c9ca790aabd705e31ca99c6185c3e76dd`                                                  | v0.8.1  | Renovate                                         |
| `docker/setup-buildx-action`     | `f87e5991a6d7451dcb8d9637bfbc97413f497069`                                                  | v4.4.1  | Renovate                                         |
| `docker/login-action`            | `8aa5831fb8d48d8f76594c7ddde61ae58019f550`                                                  | v4.8.0  | Renovate                                         |
| `docker/build-push-action`       | `c3c9e263c25d99ce0380d002d59b67737d91b0dc`                                                  | v7.4.0  | Renovate                                         |
| `actions/attest-build-provenance` | `4d101475d8b20a2381f78447822ac1eab6504dd8`                                                 | v4.2.2  | Renovate                                         |
| `bats-core/bats-core`            | `eb7f42f8d608ac693d7a4b67474f6714ea68cfc5`, checked out with `actions/checkout`            | v1.14.0 | Renovate                                         |
| Node.js                          | `node-version: '24.22.2'` in `zizmor.yml`                                                   | 24.22.2 | Renovate (setup-node input); runs the Renovate validator only |
| Python (CI)                      | `python-version: '3.14'` in `zizmor.yml`, `dependency-audit.yml` and `dependency-review.yml` | 3.14    | Renovate, grouped with the image, behind Dashboard approval |
| zizmor (the audit tool)          | `version: '1.29.0'` in `zizmor.yml`                                                         | 1.29.0  | Renovate; merge the action update first          |
| semgrep                          | `semgrep==1.176.1` in `semgrep.yml`                                                         | 1.176.1 | manual                                           |
| renovate config validator        | `renovate@44.50.3` in `zizmor.yml`                                                          | 44.50.3 | manual                                           |
| pip-tools                        | `pip-tools==7.6.2` in `zizmor.yml`, `serve_api/Makefile` and `renovate.json` (`constraints`) | 7.6.2   | manual; 7.7.0 is younger than the 14-day cooldown |
| cyclonedx-bom (the SBOM tool)    | `cyclonedx-bom==8.0.1` in `sbom.yml`                                                    | 8.0.1   | manual (a plain `pip install` line); newest release at least 14 days old |
| pytest in the script workflows   | `pytest==9.1.1` in `sbom.yml`, `zizmor.yml` (`requirements-review`) and `dependency-review.yml` | 9.1.1   | manual; keep equal to the pin in `serve_api/requirements-dev.txt` |
| pip in the compile container     | `pip==26.3` in `serve_api/Makefile` (`deps-linux`)                                      | 26.3    | manual; at least 26.1, the first pip that reads `PIP_UPLOADED_PRIOR_TO=P14D` (see "Cooldown") |
| pip-audit                        | `pip-audit==2.10.1` in `dependency-audit.yml` and `ci.yml` (`test` job)                 | 2.10.1  | manual                                           |
| shellcheck                       | runner-provided in `ci.yml` (`test` job); **not pinned**                                | runner  | exception: ubuntu-24.04 ships it, and CI only lints; the local check uses `koalaman/shellcheck:v0.11.0` |
| Python base image                | `python:3.14-bookworm@sha256:fbaf91204f2758a70a7f7d6cf3c2871851227152a54e6a7b5b59941c4566b6b5` in `serve_api/Dockerfile` line 1 and `PY_IMAGE` in `serve_api/Makefile` | 3.14-bookworm | Renovate, both files in one pull request (see below) |
| GitLab Pages image               | `node:26-alpine@sha256:6bd9ab43c0ec0190ca7b2d193906cb8b7edf6e7f4afa43ddeccd6452710bffb5` in `.gitlab-ci.yml` | 26 (LTS) | Renovate (`gitlabci` manager, `docker:pinDigests`) |
| Caddy image                      | `caddy:2.11.9-alpine@sha256:003a97808e781aa9f7e75cc2f43d34d461099031faf5e20faefb9f61126836f0` in `deployment/vm/{acc,stable}/compose.yml`, one Renovate PR moves both (same depName) (released 2026-11-05) | 2.11.9  | Renovate (`docker-compose` manager, `docker:pinDigests`) |
| Python dependencies              | `serve_api/requirements.txt` and `requirements-dev.txt`, `--generate-hashes`                | -       | Renovate (`pip_requirements` per package, `pip-compile` weekly lock-file maintenance); the `audit` drift check rejects an inconsistent bump |

There is no script that compares this table with the workflows. When Renovate
updates an action, update its row on the same branch before merging.

**One image, two files.** The base image is written in `serve_api/Dockerfile` and
in `PY_IMAGE` of the `deps-linux` target in `serve_api/Makefile`, so the lock files
are compiled on the image that runs them. Renovate's docker manager finds the
Dockerfile; a `customManagers` regex in `renovate.json` finds the Makefile copy
under the same dependency, so both move in one pull request. The regex needs the
exact spacing `PY_IMAGE = `; reformatting that line stops Renovate updating it.

**Recompiling the requirements.** `requirements.txt` and `requirements-dev.txt` are
compiled on Linux, Python 3.14, with `pip-tools==7.6.2`, and carry hashes. Run
`make deps-linux` in `serve_api/` (or its Docker equivalent, a Linux container, or
WSL); `make deps-linux ARGS=--upgrade` upgrades. A compile on Windows differs in
platform markers, and the hashed Linux files will not `pip install` on Windows:
platform-only dependencies such as `colorama` and `pywin32-ctypes` are absent from
them. The `audit` job recompiles and fails on any drift, so a Windows-compiled file
is rejected. `requirements-dev.txt` is compiled with `--constraint requirements.txt`,
so a shipped package has the same version in both files and the tests run against
the versions the image ships.

On Windows there is no `make`; from the repository root in Git Bash run:

```
MSYS_NO_PATHCONV=1 docker run --rm -e PIP_ROOT_USER_ACTION=ignore -e PIP_DISABLE_PIP_VERSION_CHECK=1 -v "$PWD/serve_api:/s" -w /s python:3.14-bookworm@sha256:fbaf91204f2758a70a7f7d6cf3c2871851227152a54e6a7b5b59941c4566b6b5 sh -c "pip install -q pip==26.3 pip-tools==7.6.2 && sed 's/\r$//' pip-compile.sh > /tmp/pc.sh && PIP_UPLOADED_PRIOR_TO=P14D sh /tmp/pc.sh"
```

`PIP_UPLOADED_PRIOR_TO=P14D` is the developer's cooldown; keep it in this command
as in the Makefile, on the compile only, so the image's own pip never sees it
(see "Cooldown").

Add `--upgrade` after `/tmp/pc.sh` to upgrade. On Linux or WSL with native Docker the
output files are owned by root; `chown` them back before committing.

If `audit` fails on drift of added `--hash` lines only (a new wheel uploaded for an
existing release), run the Linux compile and commit the result.

A Renovate pull request that moves the Python minor (grouped with the image, behind
Dashboard approval) needs the requirements recompiled on the new Python
(`make deps-linux ARGS=--upgrade` or the docker command above) and pushed onto it.

## Checks

| Check              | Workflow               | Covers                                                                                                                         |
| ------------------ | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `audit`            | `zizmor.yml`           | Workflow analysis, Renovate config, requirements match `pyproject.toml`, every requirement hashed, pins                        |
| `requirements-review` | `zizmor.yml`        | The register gate (see "Dependency register gate"): script tests and the register's shape on every run; on a pull request that changes `serve_api/requirements.txt`, `requirements-dev.txt`, `pyproject.toml` or `dependency-register.json`, the requirements diff, new direct dependencies against the register, and the 14-day cooldown. One comment (`<!-- requirements-review -->`), posted by `requirements-review-comment`. Required once the owner has added it (see "Branch rulesets") |
| `dependency-review` | `dependency-review.yml` | Quarterly (2 January, April, July, October), on demand, and on a pull request that changes the review, the gate scripts, their tests, the register or the serve_api requirements (no issue is opened then): the evidence for every direct dependency, opened as one issue per quarter labelled `dependencies`; not a merge check |
| `scan`             | `semgrep.yml`          | Semgrep Code and Supply Chain                                                                                                  |
| `dependency-audit` | `dependency-audit.yml` | Daily `pip-audit` of `acc` and `main`; not a merge check. Also runs on a pull request that changes the audit itself            |
| `test`             | `ci.yml`               | `py_compile`, import, `pytest`, shellcheck, bats                                                                             |
| `release-sbom`     | `sbom.yml`             | Not a required check. Tests the SBOM script; on push to `main` the release in `serve_api/RELEASE` must exist and have its SBOM; on a pull request that changes it, it must match `requirements.txt`; uploads the SBOM as a 90-day artifact |
| `build`            | `ci.yml`               | Image build and `/health` smoke test; read-only token, runs on pull requests too                                       |
| `publish`          | `ci.yml`               | Push to `acc` or `main` only: push to GHCR (tags `sha-<commit>` and `acc`; on `main` `sha-<commit>`, `stable`, `<version>` from `serve_api/pyproject.toml` and `vYYYY.MM.N` from `serve_api/RELEASE`), verify the pushed digest, attest provenance; the only job with write permissions |
| `deploy`           | `ci.yml`               | Push only: waits for the VM of the tier (environment `acceptance` for `acc`, `stable` for `main`, created by GitHub on first use) to report the commit; **not required**, it fails when the VM is down |

The shell scripts are shellchecked and tested with bats-core in `test`:
`scripts/ci-tier.sh` (the branch to tier mapping), `scripts/read-release.sh` (reads and validates
`serve_api/RELEASE` for `build` and `publish`), `scripts/wait-for-deploy.sh` (the `deploy` poll), `scripts/smoke-health.sh`
(the `/health` check of the built image, run in `build` and, on the pushed digest, in `publish`) and
`deployment/vm/reconciler/reconcile.sh` (the reconciler on the VM).

Required checks match by job name, so renaming a job means updating the rulesets.
`audit`, `requirements-review` and `scan` run on every pull request, whatever its
base branch or paths, so a pull request cannot skip a required check by not
triggering it. `requirements-review` decides inside the job, with `git diff`
against the base, whether there is anything to judge, and succeeds with a note
when there is not.

**Fork pull requests.** GitHub passes no secrets to a pull request from a fork, so
`semgrep ci` does not start and `scan` **fails** for a fork pull request. Tracked in
https://github.com/open-regels/cprmv/issues/4 (the same problem as
`sgort/ttl-editor#128`). Until it is solved, the contributor pushes a branch to this
repository instead, or an admin edits the ruleset for that merge. There are no forks
today.

## Dependency register gate

The same gate as in linked-data-explorer, ttl-editor, ronl-business-api and lvg
(ICTU recommendations 1 and 6), reimplemented in Python for PyPI
(`docs/superpowers/specs/2026-11-28-dependency-register-gate-design.md`). The
criteria are linked-data-explorer's `docs/dependency-criteria.md`, the one copy
every repository links to. The scripts are stdlib only and tested under pytest
in `scripts/test/` with no network:

- `scripts/requirements_review.py` compares the base and head copies of both
  requirements files: pins added, removed, updated and downgraded. A pin without
  hashes or from anywhere but PyPI blocks. Every added pin is looked up on PyPI,
  and a licence off the allow-list in `serve_api/lockfile-review.json` or a pin
  with no wheel for the image is listed, not blocking.
- `scripts/dependency_gate.py` judges every direct dependency that is new to a
  group of `serve_api/pyproject.toml` (`runtime`, `dev`, `tools`), and every entry
  `serve_api/dependency-register.json` adds or changes, against PyPI and GitHub
  evidence. A criterion the entry says holds while the evidence says it does not,
  a missing or short `why`, an assessed major other than the locked one, a cited
  issue that is not an open issue, or a missing `licence`/`repository` field
  where PyPI cannot supply one blocks. It also enforces the cooldown (below).
- Ways through, each written into the comment and the job summary: a committed
  override (`status: "override"` with an open issue, or a `cooldownOverrides`
  entry with an open issue), or a Renovate security pull request: author
  `renovate[bot]` and the `security` label put on by `renovate[bot]`, read from
  the issues API (waiting up to 60 s for Renovate's labels), never from the
  event payload. A Renovate security pull request also passes a missing register
  entry with a warning.
- Exit codes: 0 clean, 1 blocking, 2 could not evaluate. A PyPI or GitHub
  failure, or a malformed file, is 2 and fails the check; it never reads as clean.

The job runs the script tests and `--check-register` on every run, so a broken
register fails even a pull request that touches nothing else. On a pull request
whose serve_api files differ, it exports the base copies with `git show`, runs
the review and the gate, combines them with `--combine` (verdicts at the top,
which a cut to GitHub's comment limit never removes; the full text in the job
summary) and exits with the worst status. Values reach the scripts through
`env:` only; the comment job holds the only write token and runs no repository
code. There is no `labeled` trigger. Fork pull requests get the job summary, no
comment.

`scripts/dependency_review.py` runs quarterly in `dependency-review.yml`
(ICTU recommendation 11): every register entry and direct dependency with its
evidence and signals gathered again, entries whose locked major has moved past
`assessed.version`, `replace` and `override` entries with the state of their
issue, the `cooldownOverrides`, and the previous quarter's merged Renovate pull
requests: those labelled `security`, and the young pins the gate logged on
them. A person records keep, replace or accept per finding in the issue.

## Cooldown

Every pin a pull request adds or changes in either requirements file must have
been uploaded to PyPI at least 14 days before the run (`minReleaseAgeDays` in
`serve_api/lockfile-review.json`, the same 14 days as Renovate's
`minimumReleaseAge`). "Uploaded" is the earliest upload of that version's files.
A younger pin blocks `requirements-review` on a person's pull request unless a
`cooldownOverrides` entry with an open issue covers it.

**The remaining exception: Renovate's routine pull requests** (owner's decision
(b), 28 November 2026). Renovate's pip-compile manager passes no cutoff to
pip-compile and rejects a header option it does not know
(`lib/modules/manager/pip-compile/common.ts` L306-317), and hosted Renovate
cannot be given the variable below, so every Renovate pull request re-resolves
the transitive pins with no cutoff, and the weekly lock-file maintenance almost
always brings at least one pin younger than 14 days. Blocking those would stop
the maintenance for good. So on any pull request whose author is
`renovate[bot]`, young pins are **logged, not blocked**: listed in the comment,
the job summary and the next quarterly review. The new-dependency rules still
apply, and the package Renovate updates has already waited its 14 days. For
CPRMV's transitive tree, the cooldown is enforced on people's changes and logged
on Renovate's.

This route keys on the pull request's author only, read from the event
(`github.event.pull_request.user.login`). A person who pushes commits to a
`renovate/*` branch is still inside a pull request authored by `renovate[bot]`,
so young pins in those commits are logged, not blocked. Review a Renovate pull
request with commits from someone else as a person's change.

**The developer path.** `make deps-linux` (and `deps-upgrade`, and the docker
command under "Recompiling the requirements") sets the environment variable
`PIP_UPLOADED_PRIOR_TO=P14D` for the compile only (not for the bootstrap
`pip install`, so the image's own pip never sees it) and installs `pip==26.3`
next to `pip-tools==7.6.2`; pip 26.1 is the first to accept the `P<n>D` form.
pip then resolves only files at least 14 days old, so a person's recompile meets
the gate's cooldown before it is pushed. It must stay the variable, never
pip-compile's `--uploaded-prior-to` flag: pip-compile writes the flag into the
requirements header, `audit` recompiles with `./pip-compile.sh` and compares
byte for byte, and Renovate's pip-compile manager rejects a header option it
does not know and stops maintaining the files. The variable is applied and not
recorded, and `audit`'s recompile sets none and keeps the committed pins.

## Release SBOM

`sbom.yml` ("Release SBOM") keeps a bill of materials per release, so that "was
that release affected by this advisory?" can be answered later (ICTU
recommendation 10). Workflow artifacts last at most 90 days on a public
repository, so the durable copy is `docs/sbom/cprmv-api-<release>.cdx.json`,
committed at release time by `/bump-release` (see "Releasing" in the README).

- **Named after the release number**, `vYYYY.MM.N` from `serve_api/RELEASE`, not
  after the vocabulary version: stable was released several times at 0.4.3 with
  different dependencies, so a file per vocabulary version would be overwritten
  by each of them. `docs/sbom/cprmv-api-0.4.3.cdx.json` is the record of what
  stable ran before release numbers (27 November 2026) and stays as it is. The
  script refuses to run while `serve_api/RELEASE` is missing or malformed, so on
  a pull request whose tree has none (only before the first release) the
  workflow skips the strict check, the generation and the upload. Nothing else
  is skipped: on a push to `main` a missing `RELEASE` fails `--verify-release`,
  and a manual run without one fails at the generation.

- `scripts/write-sbom.py` runs `cyclonedx-py` (CycloneDX 1.6) on
  `serve_api/requirements.txt`: the shipped, hash-locked dependencies. The
  development dependencies are not in the image and not in the SBOM; the daily
  dependency audit covers both files. The output is deterministic (no serial
  number or timestamp, sorted), so the same requirements give the same bytes.
  The requirements file records no dependency graph, so the graph in the
  document is flat.
- On a pull request that changes the release's SBOM file the strict `--check`
  must pass; on a push to `main` `serve_api/RELEASE` and its file must exist
  (`--verify-release`), and drift is only a warning, because a promotion carries
  later commits.
- The container image has its own SBOM: the `publish` job builds with
  `sbom: true`, and BuildKit attaches an SBOM attestation to the image in GHCR.
  It covers the Debian packages the application SBOM does not.
- `release-sbom` is not a required check, as in the sibling repositories. The
  `cyclonedx-bom` pin is updated by hand, like `semgrep`.

## Branch rulesets

Rulesets are GitHub state, so this section and `.github/rulesets/` record what a
diff cannot show. Both were created on 26 November 2026 with `audit` and `scan`;
`test` and `build` were added later that day, to `acc` after they had first reported
on a pull request into `acc` and to `main` after the first release pull request (a
required check that has never reported blocks every merge).

| Ruleset                 | ID         | Branch | Required checks                              |
| ----------------------- | ---------- | ------ | -------------------------------------------- |
| `acc supply-chain gate` | `28148785` | `acc`  | `audit`, `scan`, `test`, `build`             |
| `main promotion gate`   | `28148786` | `main` | `audit`, `scan`, `test`, `build`             |

Both require a pull request with zero approvals and merge commits only, and both
block branch deletion and force pushes. Neither has bypass actors.

**`requirements-review` is still to be added, by the owner.** Add it to
`acc supply-chain gate` after the job has first reported on a pull request into
`acc`. Add it to `main promotion gate` only after it has reported on a release
pull request into `main`, not before; then update the table above. Until
then it runs and comments but does not block a merge. A required check that has
never reported blocks every merge, which is why it waits for the first run.

`.github/rulesets/acc.json` and `main.json` are the record of what the rulesets
should be, including `test` and `build` for both branches, and already
`requirements-review` for both: apply them once the check has reported. They are not applied by CI. To
apply one, an admin runs, for example:

```
gh api -X PUT repos/open-regels/cprmv/rulesets/28148785 --input .github/rulesets/acc.json
```

Keep the file and the live ruleset in step: change one, change the other.

If semgrep.dev is unreachable or `SEMGREP_APP_TOKEN` is revoked, `scan` fails and
merges stop until the repository owner edits the rulesets.

## Dependency audit rule

The audit runs `pip-audit` over the pinned requirements, on `acc` and `main`, every
day at 05:17 UTC and on demand (`scripts/audit-requirements.sh`). It opens, updates
and closes a tracking issue labelled `security` and `ci`.

- **Shipped (`serve_api/requirements.txt`): any known advisory fails.** `pip-audit`
  does not grade severity, so this is stricter than lvg's high/critical rule.
- **Development only (`requirements-dev.txt`): reported, does not fail.** An
  advisory in a package that is also vulnerable in the shipped file counts as
  shipped.
- **The audit failing to run is a failure** (exit 2), never "clean": a package
  `pip-audit` skips in the shipped file, empty or unparsable output, or a tool or
  network error.
- **Accepted advisories** are listed one ID per line in
  `scripts/pip-audit-accepted.txt` and passed to `pip-audit` as `--ignore-vuln`.
  Each needs a row in the table below.

## Findings we accept, and why

A decision on a finding is recorded in one of two places, and only one of them is
in git.

- **Semgrep Code false positives** are suppressed inline: a comment with the
  reason, then `# nosemgrep: <full rule id>` above the line. The reason is
  reviewed in the pull request and holds for every Semgrep project that scans the
  repository. They get no row here.
- **Everything else** is triaged in the Semgrep UI with a comment, and the
  platform's API does not return that comment: Supply Chain findings, which have
  no inline mechanism, and Code findings that are true positives we accept rather
  than fix (a `nosemgrep` would misstate them as false). Advisories accepted for
  the dependency audit have no comment field at all. **This table is the
  record**: each row is the reason, and the comment in the UI repeats it. A
  finding marked ignored in the UI, or an ID in `scripts/pip-audit-accepted.txt`,
  without a row here is a gap.

Last triaged on 27 November 2026, from the Semgrep findings of `acc` at `2341daa`
and `main` at `502a351`.

| Package, file (version) | Advisory or rule | Source (Semgrep finding ID or pip-audit) | Decision | Reason | Revisit when |
| ----------------------- | ---------------- | ---------------------------------------- | -------- | ------ | ------------ |
| `html/index.html:14`, Logius `respec-nlgov.js` (unversioned build) | `html.security.audit.missing-integrity.missing-integrity` (Code) | 1107098784 (one finding in the UI for `acc` and `main`) | accepted, 27 Nov 2026 | Logius publishes the NL-gov ReSpec profile at one fixed URL and replaces it in place, so an `integrity` hash would break the spec on every upstream release. The tag carries `class="remove"`: ReSpec strips it from the exported document, and neither published copy (`html/public/<version>/` on GitLab Pages, `serve_api/respec/` in the image) loads it. Exposure is limited to building and editing the spec, from a government host over HTTPS. | Logius publishes versioned builds, or the ReSpec build (#21, #24) vendors the profile |

## Not carried over from lvg, and why

- **Format check.** lvg enforces Prettier on code that was written to it. Turning on
  `ruff format` here would rewrite most of `serve_api/` in one go; that is the
  maintainer's call, not a side effect of this work.
- **Registry signatures.** `npm audit signatures` has no PyPI equivalent in general
  use; hashes are what Python offers, and they are required.
- **`check-supply-chain`.** lvg's script that checks the pin register against the
  workflows is Node. Porting it is a follow-up; until then the register is kept by
  hand, as lvg's was before the script.
- **Husky pre-push hooks.** Node tooling. A `pre-commit` pre-push stage (already a
  dev dependency) is possible, but changes the maintainer's local workflow:
  follow-up.
- **Transitive tool dependencies.** The CI tools (semgrep, pip-audit, pip-tools, the
  Renovate validator) are pinned by version, but their own transitive dependencies
  are not, as in lvg.
- **Playwright, bundle checks, preview cleanup.** Nothing here they would check.
- **lvg's `lockfile-review` and `dependency-review` scripts.** They read
  `package-lock.json` and the npm registry. The same rules are carried over as
  Python scripts for PyPI (`requirements-review`, `dependency-review`; see
  "Dependency register gate"), not the Node scripts. Two differences are on
  purpose: every register change is judged against evidence, not only
  shape-checked; and young pins in Renovate's routine pull requests are logged,
  not blocked (see "Cooldown").
