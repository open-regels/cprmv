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
  pull request (#3) is to be closed once `renovate.json` is on `acc`.
- Dependabot alerts are enabled. Renovate's fast route for security fixes depends
  on them.
- `SEMGREP_APP_TOKEN` is set as a repository secret.
- The issue labels `security` and `ci` exist, for the daily dependency audit.

## Pinned

| Dependency                       | Pin                                                                                         | Version | Maintained by                                    |
| -------------------------------- | ------------------------------------------------------------------------------------------- | ------- | ------------------------------------------------ |
| `actions/checkout`               | `3d3c42e5aac5ba805825da76410c181273ba90b1`                                                  | v7.0.1  | Renovate                                         |
| `actions/setup-node`             | `949feb2413d6458794dcd2491c4babbbce0c15c1`                                                  | v7.1.0  | Renovate                                         |
| `actions/setup-python`           | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0`                                                  | v7.1.0  | Renovate                                         |
| `zizmorcore/zizmor-action`       | `45d7276c9ca790aabd705e31ca99c6185c3e76dd`                                                  | v0.8.1  | Renovate                                         |
| `docker/setup-buildx-action`     | `f87e5991a6d7451dcb8d9637bfbc97413f497069`                                                  | v4.4.1  | Renovate; Part B                                 |
| `docker/login-action`            | `8aa5831fb8d48d8f76594c7ddde61ae58019f550`                                                  | v4.8.0  | Renovate; Part B                                 |
| `docker/build-push-action`       | `c3c9e263c25d99ce0380d002d59b67737d91b0dc`                                                  | v7.4.0  | Renovate; Part B                                 |
| `actions/attest-build-provenance` | `4d101475d8b20a2381f78447822ac1eab6504dd8`                                                 | v4.2.2  | Renovate; Part B                                 |
| `bats-core/bats-core`            | `eb7f42f8d608ac693d7a4b67474f6714ea68cfc5`, checked out with `actions/checkout`            | v1.14.0 | Renovate; Part B                                 |
| Node.js                          | `node-version: '24.22.2'` in `zizmor.yml`                                                   | 24.22.2 | Renovate (setup-node input); runs the Renovate validator only |
| Python (CI)                      | `python-version: '3.14'` in `zizmor.yml` and `dependency-audit.yml`                         | 3.14    | manual; matches the image                        |
| zizmor (the audit tool)          | `version: '1.29.0'` in `zizmor.yml`                                                         | 1.29.0  | Renovate; merge the action update first          |
| semgrep                          | `semgrep==1.176.1` in `semgrep.yml`                                                         | 1.176.1 | manual                                           |
| renovate config validator        | `renovate@44.50.3` in `zizmor.yml`                                                          | 44.50.3 | manual                                           |
| pip-tools                        | `pip-tools==7.6.2` in `zizmor.yml` and `serve_api/Makefile`                                 | 7.6.2   | manual; 7.7.0 is younger than the 14-day cooldown |
| pip-audit                        | `pip-audit==2.10.1` in `dependency-audit.yml`                                               | 2.10.1  | manual                                           |
| Python base image                | `python:3.14-bookworm@sha256:fbaf91204f2758a70a7f7d6cf3c2871851227152a54e6a7b5b59941c4566b6b5` in `serve_api/Dockerfile` line 1 and `PY_IMAGE` in `serve_api/Makefile` | 3.14-bookworm | Renovate, both files in one pull request (see below) |
| Caddy image                      | added by Part B                                                                             | -       | Part B                                           |
| Python dependencies              | `serve_api/requirements.txt` and `requirements-dev.txt`, `--generate-hashes`                | -       | Renovate (`pip-compile` manager)                 |

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
is rejected.

## Checks

| Check              | Workflow               | Covers                                                                                                                         |
| ------------------ | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `audit`            | `zizmor.yml`           | Workflow analysis, Renovate config, requirements match `pyproject.toml`, every requirement hashed, pins                        |
| `scan`             | `semgrep.yml`          | Semgrep Code and Supply Chain                                                                                                  |
| `dependency-audit` | `dependency-audit.yml` | Daily `pip-audit` of `acc` and `main`; not a merge check. Also runs on a pull request that changes the audit itself            |
| `test`             | `acc-ci.yml`           | Part B: `py_compile`, import of the app, `pytest`                                                                              |
| `build`            | `acc-ci.yml`           | Part B: image build; on a push to `acc`, push to GHCR and attest provenance                                                    |
| `deploy-acc`       | `acc-ci.yml`           | Part B: waits for the VM to report the commit; not a merge check                                                               |

Required checks match by job name, so renaming a job means updating the rulesets.
`audit` and `scan` run on every pull request, whatever its base branch or paths,
so a pull request cannot skip a required check by not triggering it.

**Fork pull requests.** GitHub passes no secrets to a pull request from a fork, so
`semgrep ci` does not start and `scan` **fails** for a fork pull request. Tracked in
https://github.com/open-regels/cprmv/issues/4 (the same problem as
`sgort/ttl-editor#128`). Until it is solved, the contributor pushes a branch to this
repository instead, or an admin edits the ruleset for that merge. There are no forks
today.

## Branch rulesets

Rulesets are GitHub state, so this section records what a diff cannot show. They
are created after Part A merges, with `audit` and `scan`; `test` and `build` are
added to the `acc` ruleset once Part B has reported them.

| Ruleset                 | ID                    | Branch | Required checks                              |
| ----------------------- | --------------------- | ------ | -------------------------------------------- |
| `acc supply-chain gate` | recorded when created | `acc`  | `audit`, `scan`; Part B adds `test`, `build` |
| `main promotion gate`   | recorded when created | `main` | `audit`, `scan`                              |

Both require a pull request with zero approvals and merge commits only, and both
block branch deletion and force pushes. Neither has bypass actors.

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

Semgrep Supply Chain findings have no inline suppression. They are triaged in the
Semgrep UI with a comment, and the platform's API does not return that comment.
Advisories accepted for the dependency audit have no comment field at all.
**This table is the record**: each row is the reason, and the comment in the UI
repeats it. A finding marked ignored in the UI, or an ID in
`scripts/pip-audit-accepted.txt`, without a row here is a gap.

None today.

| Package (version) | Advisory | Source (Semgrep finding ID or pip-audit) | Decision | Reason | Revisit when |
| ----------------- | -------- | ---------------------------------------- | -------- | ------ | ------------ |

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
- **Playwright, bundle checks, preview cleanup.** Nothing here they would check.
