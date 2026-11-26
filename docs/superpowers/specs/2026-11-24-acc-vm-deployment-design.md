# CPRMV ACC deployment: a VM that reconciles itself from GitHub

Status: design, for approval · 24 November 2026

## Intent

CPRMV moved from `git.open-regels.nl/standards/cprmv` to
`github.com/open-regels/cprmv` on 24 November 2026, development included. Its
build and deployment move with it.

This design builds the **acceptance** deployment from scratch, on a fresh VM, so
that `https://acc.cprmv.open-regels.nl/` always runs what the `acc` branch says,
and says so itself. It is also meant as the **template for the other IOU VM
deployments**: it is the first implementation of the approach decided in
[sgort/ronl-business-api#196](https://github.com/sgort/ronl-business-api/issues/196)
("Bring the ACC and PROD VM deployment under action control, then pin its
container images"), and the parts that are not CPRMV-specific should be
recognisable as such.

## What exists today, and why it is replaced rather than migrated

- The GitLab pipeline (`.gitlab-ci.yml`) tests, builds and pushes
  `datafluisteraar/cprmv-api:latest` to Docker Hub on `main`. Its "deploy" job
  only prints instructions. Its `develop` rule names a branch that does not exist.
- Both hostnames resolve to a VM shared with Keycloak, Operaton and Caddy. Prod
  runs a Docker Hub image pulled by hand; acc runs an image built on the server.
  Both bind-mount a host directory over `/app/data`, hiding the `data/` baked
  into the image, so neither runs what any commit describes.
- Nothing records what is running, other than `GET /` answering the version
  string from `serve.py`.
- Neither host sends CORS headers (checked 24 November 2026 with an `Origin`
  header on both; the API has no CORS code either), so browser clients do not
  call it cross-origin today and the new Caddyfile has nothing to carry over
  there. The headers they do send are listed under Compose and Caddy below.
- The same pipeline's `create-pages` job publishes the ReSpec (`html/public`) to
  GitLab Pages at `https://standaarden.open-regels.nl/standards/cprmv/<version>/`,
  the URL the published RDF uses. See "The ReSpec publication" below.
- The API's data, including the service endpoints in
  `serve_api/data/cprmvmethods.ttl`, comes from this repository alone; the old
  VM's mounted copies are not a source and are not carried over (decided
  24 November 2026).

A fresh VM is being provisioned for CPRMV. Nothing on the old VM is carried over.

## Goals

1. A merge into `acc` reaches acc.cprmv **without anyone touching the VM**.
2. **Nothing reaches into the VM.** No SSH from GitHub, no inbound port beyond
   80/443, no self-hosted runner. The VM pulls.
3. **No credentials on the VM.** The repository and the GHCR package are public,
   so the VM reads both anonymously.
4. **The VM reports what is running**, publicly, without SSH: the commit, the
   image digest, and the outcome of its last attempt.
5. The GitHub workflow that built the image **waits for that report** and fails
   if the VM does not end up running the merged commit, so a merge has a visible
   deploy verdict, as in the other IOU apps.
6. **Idempotent**: when nothing changed, a reconcile run changes nothing.
7. **A failed deploy leaves the previous version running.**
8. The image is the **only source of the API's data**: no bind mount.
9. The VM, its network rules and its DNS record are **created from the
   repository** with the `az` CLI, and the VM bootstraps itself on first boot, so
   no step needs SSH (added 24 November 2026).
10. CPRMV carries the **light security pipeline of `sgort/lvg`**, adapted from npm
    to Python where needed, so a pull request into `acc` meets the same gates as
    the other IOU repositories (added 24 November 2026).

## Non-goals

- **Production.** `cprmv.open-regels.nl` stays as it is. The layout below leaves
  a place for it (`deployment/vm/prod/`), and the reconciler takes the tier as a
  parameter, but no `main` deploy, no prod compose file, no prod VM. Prod is
  **frozen at 0.4.3** until that follow-up: with development on GitHub the
  GitLab pipeline no longer runs, so no new Docker Hub image appears either way.
- **Per-tier configuration.** `cprmvmethods.ttl` names its service endpoints
  (some of them acceptance hosts, such as `acc.backend.linkeddata.open-regels.nl`)
  and acc and prod will run the same image. Selecting endpoints per tier is a
  question for the prod follow-up; acc runs what the repository says.
- Restoring the commented-out tests in `serve_api/test/test_serve.py`.
- Verifying the build provenance on the VM. The workflow produces the
  attestation; checking it before a deploy is a follow-up (see Risks).

## Anti-goals

- A deploy that reports success while the VM runs something else.
- Any credential, on the VM or in the repository, that can write to GitHub or
  GHCR from the VM's side.
- A second copy of the API's data that can drift from the repository.
- A workflow that pushes an image from a pull request.
- Two pipelines that can both publish an API image.

## Constraints

- `acc` and `main` change only through pull requests on GitHub.
- SSH to the VMs is restricted to one fixed address. The new VM is assumed to get
  the same rule; the design does not depend on it either way, since nothing
  routine uses SSH (only installing a changed reconciler, below).
- The repository is **public**. Every workflow must be safe to run for a pull
  request from a fork: no secrets and no package write on `pull_request`.
- The API listens on 8000 and has no TLS of its own; the VM needs a reverse
  proxy that obtains certificates. On the shared VM that was a separate Caddy;
  this VM is CPRMV's alone, so its Caddy is part of this deployment.

## Approaches considered

**How the deploy reaches the VM** (decided in #196, repeated here because this
design implements it):

1. *Push over SSH from a GitHub-hosted runner.* Refused by the firewall unless
   GitHub's runner ranges are allowlisted, which widens access to a shared cloud.
2. *Self-hosted runner on the VM.* A runner on a public repository must never run
   pull-request code; a mistake in triggers hands the VM to a fork.
3. ***Pull: the VM reconciles itself.* Chosen.** No inbound access, no
   credentials, and "what is running" becomes something the VM reports.

**Where the deployment description and the reconciler live** (decided
24 November 2026):

1. ***Per application.* Chosen.** Each repository carries its own
   `deployment/vm/<tier>/` and its VM runs one reconciler for it. A release stays
   one pull request in one repository.
2. *One infrastructure repository per VM*, describing every service on it. One
   place to look, but every application release becomes a change in two
   repositories. A shared repository can still be added later for genuinely
   shared services; for CPRMV on its own VM there are none.

**Where the API's data comes from** (decided 24 November 2026): only the image.
A managed data directory synced by the reconciler was rejected because it is a
second thing to version and report; the old unmanaged mount because it had
already drifted.

## Design

### Overview

```
 PR into acc ──► acc-ci: test, build image (no push)            [required check]

 merge into acc ──► acc-ci: test, build, push
                     ghcr.io/open-regels/cprmv-api:sha-<commit>
                     + provenance attestation
                   └─► wait-for-acc: poll https://acc.cprmv.open-regels.nl/deploy-status.json
                       until it reports <commit> deployed (or failed, or timeout)

 VM, every 2 minutes (systemd timer):
   fetch acc (anonymous HTTPS) ──► target commit
   target == running and healthy?  ──► nothing to do
   image sha-<target> on GHCR?  no ──► "waiting", try next tick
   pull by tag, resolve digest, apply deployment/vm/acc/ from <target>
   docker compose up --wait, check /health reports <target>
     ok   ──► record as running
     fail ──► restore previous, record <target> as failed
   write deploy-status.json (served by Caddy)
```

### Repository layout

```
.github/workflows/acc-ci.yml            build, test, push, wait for the VM
.github/workflows/zizmor.yml            security: job `audit`
.github/workflows/semgrep.yml           security: job `scan`
.github/workflows/dependency-audit.yml  security: daily pip-audit of acc and main
renovate.json, .semgrepignore, SECURITY-PIPELINE.md
deployment/vm/README.md                 what the VM needs, provisioning, operations
deployment/vm/provision.sh              az: NSG, network, static IP, VM (TIER=acc|stable)
deployment/vm/cloud-init.yaml           first-boot bootstrap (template, per tier)
deployment/vm/cutover-dns.sh            az: acc.cprmv or cprmv A record → new VM
deployment/vm/acc/compose.yml           cprmv-api + caddy for acceptance
deployment/vm/acc/Caddyfile             acc.cprmv.open-regels.nl → cprmv-api:8000
deployment/vm/reconciler/reconcile.sh   the reconciler (tier-agnostic)
deployment/vm/reconciler/cprmv-reconcile@.service
deployment/vm/reconciler/cprmv-reconcile@.timer
```

`deployment/vm/prod/` does not exist yet. The systemd units are templated on the
tier (`cprmv-reconcile@acc.timer`) so prod is a new instance, not a new script.

`.gitlab-ci.yml` is cut down to its `create-pages` job: GitLab no longer builds
or tests anything, but still publishes the ReSpec (next section). Its test,
build and deploy jobs, the Docker Hub variables and the `develop` rule go.

### The ReSpec publication (decided 24 November 2026)

The ReSpec stays on GitLab Pages at
`https://standaarden.open-regels.nl/standards/cprmv/<version>/`, because the
published RDF names that URL and `standaarden.open-regels.nl` serves other
standards too. Where the standards are published together is a separate decision,
not this deployment's.

- `create-pages` is unchanged in what it does: on a push to GitLab's default
  branch it publishes `html/public`, which is prebuilt and committed (the
  0.4.3 fix that stopped it rebuilding).
- GitLab gets `main` **at each release, and only then**: after the pull request
  from `acc` into `main` merges, `main` is pushed fast-forward-only to the
  `gitlab` remote. That push starts the Pages pipeline, so it is a deliberate
  release step, asked for each time, never part of routine housekeeping.
  GitLab's `acc` is not kept current; GitLab is not where anything is developed.
- The API's own `/respec` is unaffected: it serves the copy under
  `serve_api/respec/`, baked into the image.

### The image

- **Registry:** `ghcr.io/open-regels/cprmv-api`, public.
- **Tag:** `sha-<full 40-character commit>`, one per `acc` commit, immutable by
  convention. A re-run of a commit pushes the same tag again, which is harmless: the
  VM pins by digest. GitHub keeps one pending run per concurrency group, so an
  intermediate commit may get no image; that is harmless too, since the reconciler
  targets the head. A moving `acc` tag is also pushed for humans; the reconciler
  never reads it.
- **Build metadata baked in:** the Dockerfile takes `BUILD_SHA` and `BUILD_RUN`
  as build arguments and sets them as environment variables and OCI labels
  (`org.opencontainers.image.revision`, `.source`, `.version`). The existing
  `LABEL version` and the stale `org.opencontainers.image.source` pointing at
  GitLab are replaced.
- **CMD fixed in passing:** the comment above `CMD` in `serve_api/Dockerfile`
  still describes `--app combined_app`, which 0.4.3 no longer needs (`/mcp` is
  mounted on `app` at `serve.py:746`). The comment goes.
- Every `acc` push builds an image, with **no path filter**: the reconciler maps
  commit to image one-to-one, and a commit with no image would stall it. Layer
  caching (GitHub Actions cache) keeps a docs-only rebuild cheap.

### `GET /health` in the API

New endpoint, alongside the unchanged `GET /`:

```json
{
  "status": "ok",
  "version": "0.4.3",
  "environment": "<CPRMV_ENVIRONMENT>",
  "build": { "sha": "<BUILD_SHA>", "run": "<BUILD_RUN>" },
  "image": { "digest": "<CPRMV_IMAGE_DIGEST>" }
}
```

`build.sha` comes from the image itself, so it cannot disagree with what was
built. `image.digest` cannot be known inside the image; the reconciler passes the
digest it deployed as `CPRMV_IMAGE_DIGEST`. Missing values report `null`, never a
guess. The compose healthcheck uses `/health` instead of `/`.

*26 November 2026:* `/health` also reports `environment`, from `CPRMV_ENVIRONMENT`
(read per request; `null` when unset or empty). Each tier's `compose.yml` sets it
to a literal: `acceptance` or `stable`.

### The workflow: `.github/workflows/acc-ci.yml`

Triggers: `pull_request` into `acc`, `push` to `acc`, `workflow_dispatch`.

- **`test`** (all triggers): Python 3.14, `pip install -r serve_api/requirements-dev.txt`,
  then the checks the GitLab job ran: `py_compile src/serve.py`, import
  `src.serve:app`, `pytest`. Permissions `contents: read`.
- **`build`** (all triggers, needs `test`): Buildx build of `serve_api/` with the
  build arguments above, loaded locally, and the `/health` smoke test. It builds
  and stops; permissions `contents: read` only.
- **`publish`** (push only, needs `build`): logs in to GHCR with `GITHUB_TOKEN`,
  rebuilds with the same build arguments (the layer cache makes it quick), pushes
  `sha-<commit>` and `acc`, verifies the pushed digest, and attests provenance
  (`actions/attest-build-provenance`). Only this job gets `packages: write`,
  `id-token: write`, `attestations: write`.
- **`deploy-acc`** (push only, needs `publish`): `environment: acceptance` with
  url `https://acc.cprmv.open-regels.nl`. Polls `deploy-status.json` every
  20 seconds for up to 15 minutes. Succeeds when `running.sha` equals the pushed
  commit and `/health` agrees. **Fails immediately** if the status reports this
  commit as `failed`. Fails on timeout. If `acc` moves on while it waits (a newer
  commit is the target), it reports "superseded" and succeeds neutrally rather
  than waiting for a commit that will never deploy.
- Concurrency: one group per ref, cancel-in-progress for `pull_request`, queued
  (not cancelled) for `push`.
- Actions pinned by full commit SHA with the version in a comment, as in the
  other IOU repositories. `persist-credentials: false` on checkout.

The check names `test` and `build` become the required status checks on `acc`.

### The reconciler: `deployment/vm/reconciler/reconcile.sh`

A POSIX shell script with one argument, the tier. Runs as the `cprmv` system
user (member of the `docker` group), under a systemd timer every 2 minutes, with
a lock (`flock`) so runs never overlap.

Paths on the VM, for tier `acc`:

```
/opt/cprmv/acc/repo/           bare repository the reconciler creates and fetches (anonymous HTTPS)
/opt/cprmv/acc/releases/<sha>/ deployment/vm/acc/ exported from that commit, plus .env
/opt/cprmv/acc/current         symlink → the release that is running
/opt/cprmv/acc/state.json      running, previous, last attempt, failed shas
/opt/cprmv/acc/www/deploy-status.json   what Caddy serves publicly
```

One run:

1. `git fetch origin acc`; target = `origin/acc`.
2. **Nothing to do** if target equals `running.sha` and
   `docker compose ps` reports the service healthy → rewrite the status file's
   `checked_at` only, exit 0. This is the idempotence check.
3. **Already failed:** if target is in `failed`, do nothing until `acc` moves.
   A broken commit is not retried every two minutes; the fix is a new commit.
4. **Image not there yet:** `docker manifest inspect ghcr.io/open-regels/cprmv-api:sha-<target>`.
   If absent, status `waiting` (the build is probably running) and exit. After
   30 minutes of waiting on the same target, status `stalled`, still without
   deploying the target. A `docker pull` that fails after the manifest was found
   is treated the same way (waiting, retried next run), not as a failed commit.
   *Amended 26 November 2026:* in `waiting`, `stalled` and the failed-target case
   (step 3), the reconciler still checks that the **running** release is healthy
   and re-applies it if not; a failure there is reported as a warning and does
   not mark any commit failed. If the Docker daemon is not reachable, the run
   changes nothing and reports a warning.
5. **Prepare:** `docker pull` the sha tag, read the digest it resolved to,
   `git archive <target> deployment/vm/acc | tar -x` into
   `releases/<target>/`, write `.env` with
   `CPRMV_IMAGE=ghcr.io/open-regels/cprmv-api@sha256:<digest>` and
   `CPRMV_IMAGE_DIGEST=sha256:<digest>`. The compose file references the image
   **only** through `${CPRMV_IMAGE}`, so what runs is pinned by digest even though
   the commit could only name a tag.
6. **Apply:** `docker compose -p cprmv-acc -f releases/<target>/compose.yml up -d --wait --remove-orphans`,
   then `GET http://127.0.0.1:8000/health` (published on loopback only) must
   report `build.sha == target`.
7. **Success:** point `current` at the new release, move the old one to
   `previous`, record, prune releases and images older than the previous one.
8. **Failure** at 5 or 6: re-apply `previous` the same way, add target to
   `failed`, record the error text (last 20 lines of compose output). If the
   restore also fails, status `broken`: the one case that needs a person.
9. Write `deploy-status.json` atomically (write a temp file, then rename).

`deploy-status.json`:

```json
{
  "tier": "acc",
  "checked_at": "2026-11-24T14:02:00Z",
  "state": "running | waiting | stalled | failed | broken",
  "target":  { "sha": "…" },
  "running": { "sha": "…", "digest": "sha256:…", "since": "…" },
  "last_attempt": { "sha": "…", "result": "deployed | failed | restored", "at": "…", "error": "…" },
  "reconciler": { "commit": "…", "matches_repo": true }
}
```

**The reconciler does not update itself.** cloud-init installs it on first boot
from the repository; a later change is installed over SSH by hand, or by
reprovisioning the VM. `reconciler.matches_repo` reports whether the installed
copy still equals the one in the target commit. A change to the reconciler in a
pull request therefore shows up as `false` until someone installs it. That costs
a manual step on reconciler changes, and buys that a bad merge cannot replace the
thing that would roll it back.

Caddy is part of the release, so a Caddyfile change deploys like any other. A
Caddy restart is the one part of a deploy that drops connections briefly.
Because each release has its own directory, the Caddyfile's mount source
changes with every release, so **Caddy is recreated on every deploy**, not only
when the Caddyfile changes (accepted 26 November 2026: acceptance tolerates a
brief drop per deploy).

### Compose and Caddy for acceptance

- `cprmv-api`: `image: ${CPRMV_IMAGE}`, `environment: CPRMV_IMAGE_DIGEST`,
  healthcheck on `/health`, `restart: unless-stopped`, port 8000 published on
  `127.0.0.1` only (for the reconciler's check), **no volumes**.
- `caddy`: `caddy:<version>-alpine@sha256:<digest>`, pinned by tag and digest
  (the #196 stage-2 rule, applied from the start), ports 80 and 443, a named
  volume for certificates, the Caddyfile and `/opt/cprmv/acc/www` mounted
  read-only.
- `Caddyfile`: `acc.cprmv.open-regels.nl` reverse-proxies to `cprmv-api:8000`,
  except `/deploy-status.json`, served from the mounted directory with
  `Cache-Control: no-store`. The headers the current deployment sends are kept:
  `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`,
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `X-XSS-Protection: 1; mode=block`, and
  `Permissions-Policy: geolocation=(), microphone=(), camera=(), payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()`.
  No CORS headers, as today.

### Provisioning with `az` (added 24 November 2026)

Two scripts, both idempotent (each resource is created only if missing, and
re-running reports what exists):

- `deployment/vm/acc/provision.sh` creates, in one resource group: a network
  security group, a virtual network, a **static** public IP, and the VM (Ubuntu
  24.04 LTS, x86-64) with `deployment/vm/acc/cloud-init.yaml` as custom data.
- `deployment/vm/acc/cutover-dns.sh` points the `acc.cprmv` A record in the
  Azure DNS zone `open-regels.nl` at the new IP (TTL 300). It is separate because
  it is the moment acc moves; it runs only once the new VM reports `running`
  on its own IP.

The **network security group** allows 80 and 443 from anywhere and 22 only from
one address, given as `ADMIN_SSH_SOURCE` when the script runs. The address is
never committed: the repository is public. SSH is for emergencies only; nothing
in the deployment uses it.

**cloud-init does the bootstrap** on first boot: Docker Engine and the compose
plugin from Docker's apt repository, git and jq, the `cprmv` user, `/opt/cprmv/acc`,
`/opt/cprmv/acc` owned by `cprmv` (the reconciler creates its own bare
repository there on its first run), the reconciler and its units, `systemctl enable --now
cprmv-reconcile@acc.timer`. The first reconciler run deploys the head of `acc`.
Caddy cannot obtain a certificate until DNS points at the VM; until then the
deployment is checked over plain HTTP on the IP.

**Who runs what.** Reading Azure (`az ... list/show`) is done during
implementation to fill in the values below. **Every write is run by the user**,
as a one-line `! bash ~/<script>.sh` handed over in the session, after the user
has signed in with `az login --tenant <ICTU tenant>`; the same pattern as App
Service changes in the other IOU repositories.

Values fixed at plan time from what `az` shows, defaulting to the current VM's:
subscription, region, resource group name, VM size (a burstable `B2s` or
equivalent unless the current VM says otherwise), and the admin SSH public key.

The **old VM** is not touched by these scripts. After the cutover, its acc
container is stopped by hand.

### What the VM must provide

Documented in `deployment/vm/README.md`, which also explains how to reprovision:

- Ubuntu 24.04 LTS on **x86-64**, Docker Engine with the compose plugin, git,
  jq. The image is built for `linux/amd64` only (builder's call; an ARM VM would
  need a multi-platform build).
- Inbound 80 and 443 from anywhere (ACME HTTP-01 and the site); SSH as the
  firewall policy already says.
- Outbound HTTPS **open**, as on an Azure VM by default. If it is ever narrowed to
  an allowlist, the runbook lists what it must keep: `github.com`, `ghcr.io`,
  `pkg-containers.githubusercontent.com` (image layers), Docker Hub for the Caddy
  image (`registry-1.docker.io`, `auth.docker.io`,
  `production.cloudflare.docker.com`), Let's Encrypt
  (`acme-v02.api.letsencrypt.org` and its OCSP/CRL hosts), and every external
  service the API calls, as named in `serve_api/data/cprmvmethods.ttl` and
  `serve_api/methods/` (for instance `repository.officiele-overheidspublicaties.nl`,
  `service.omgevingswet.overheid.nl`, `api-organisaties.overheid.nl`).
- DNS: `acc.cprmv.open-regels.nl` pointing at the new VM (`cutover-dns.sh`).

## Security pipeline (added 24 November 2026)

Modelled on `sgort/lvg` (`SECURITY-PIPELINE.md`, `.github/workflows/{zizmor,semgrep,dependency-audit}.yml`,
`renovate.json`) and its policy: **nothing a pipeline downloads or runs may
float**. Where lvg relies on npm, the Python equivalent is named.

| lvg | CPRMV |
|---|---|
| `zizmor.yml`, job **`audit`**: zizmor, Renovate config validator, lockfile matches `package.json`, format, registry signatures, pin register | Same job name. zizmor and the Renovate validator as in lvg. **Requirements match `pyproject.toml`**: re-run `pip-compile` with pinned `pip-tools` on Python 3.14 and fail on a diff. **Hashes present** in both requirements files. No format check and no registry-signature step (see below). |
| `semgrep.yml`, job **`scan`**: `semgrep ci` (Code + Supply Chain), pinned `semgrep==<version>` | Identical. Needs the `SEMGREP_APP_TOKEN` repository secret. |
| `dependency-audit.yml`: daily audit of `acc` and `main`, tracking issue, fails on shipped high/critical | Same shape with **`pip-audit`** (pinned) over `serve_api/requirements.txt` (shipped: fails) and `requirements-dev.txt` (reported, does not fail). pip-audit does not grade severity, so the shipped rule is **any known advisory**, stricter than lvg's; accepted ones are listed in `SECURITY-PIPELINE.md` and passed with `--ignore-vuln`. Needs the labels `security` and `ci`. |
| npm lockfile integrity hashes | `pip-compile --generate-hashes` for both requirements files, and `pip install --require-hashes` in the Dockerfile and the workflows. The header says the files were compiled on Python 3.12 while the image runs 3.14; they are recompiled on 3.14. |
| Actions pinned by commit SHA | Same, Renovate-maintained (`helpers:pinGitHubActionDigests`). |
| — (no images) | **Container images pinned by tag and digest**: `python:3.14-bookworm@sha256:…` in the Dockerfile, Caddy in `compose.yml`. Renovate `docker:pinDigests`. |
| `renovate.json`: 14-day minimum release age, majors behind Dashboard approval, no X.0.0, lock-file maintenance, vulnerability fast path | Same rules, with the managers `pip-compile`, `github-actions`, `dockerfile` and `docker-compose`. The npm-specific rules (Tailwind, ESLint, `allowedVersions` for npm) are dropped; the X.0.0 rule is rewritten for PyPI. |
| `SECURITY-PIPELINE.md`: pin register, checks, rulesets, accepted findings | Same structure, CPRMV's contents. |
| `.semgrepignore`: `docs/` | `docs/`, plus the generated ReSpec: `html/public/` and `serve_api/respec/`. |

**Rulesets** (recorded in `SECURITY-PIPELINE.md`, as in lvg): `acc` requires
`audit`, `scan`, `test` and `build`; `main` requires `audit` and `scan`. Both
require a pull request, allow merge commits only, block deletion and force
pushes, and have no bypass actors.

**Manual prerequisites**, for an `open-regels` organisation admin: Renovate
GitHub App access to `open-regels/cprmv`; Dependabot alerts on;
`SEMGREP_APP_TOKEN` as a secret; the labels `security` and `ci`.

**Not carried over, and why:**

- *Format check.* lvg enforces Prettier on code that was written to it. Turning
  on `ruff format` here would rewrite most of `serve_api/` in one go; that is
  Bas's call, not a side effect of this work.
- *Registry signatures.* `npm audit signatures` has no PyPI equivalent in
  general use; hashes are what Python offers, and they are required.
- *`check-supply-chain`.* lvg's script that checks the pin register against the
  workflows is Node. Porting it is a follow-up; until then the register is kept
  by hand, as lvg's was before the script.
- *Husky pre-push hooks.* Node tooling. A `pre-commit` pre-push stage (already a
  dev dependency) is possible, but changes Bas's local workflow: follow-up.
- *Playwright, bundle checks, preview cleanup.* Nothing here they would check.

## Failure behaviour, summarised

| Situation | What runs | What the status says | What the workflow says |
|---|---|---|---|
| Build failed, no image | previous | `waiting`, then `stalled` | build job failed |
| Image pulled, container unhealthy | previous (restored) | `failed`, error text | `deploy` fails |
| Restore also fails | nothing reliable | `broken` | `deploy` fails |
| VM down or reconciler stopped | unknown | stale `checked_at`, or unreachable | `deploy` times out |
| Two merges in quick succession | the newer | the newer as target | older run reports superseded |

## Risks and decisions to revisit

- **The `docker` group is root-equivalent.** The reconciler runs with it because
  it must manage containers. Rootless Docker would narrow this; not worth it on a
  VM that runs nothing else. Revisit before reusing the template on a shared VM.
- **Trust in the image comes from GHCR and the tag name.** Anyone with write
  access to the package could push a `sha-` tag. The provenance attestation
  exists so the VM can later refuse an image that this repository's workflow did
  not build; verifying it on the VM is the first follow-up.
- **Anonymous GHCR pulls are rate-limited.** At one pull per deploy this is
  irrelevant; the `manifest inspect` every two minutes while `waiting` is the
  only repeated call, and it stops once the image appears.
- **A merge to `acc` is a deploy.** That is the intent, and it means the
  required checks on `acc` are what stand between a pull request and the VM.

## Rollout

Two pull requests, security first, so the deployment pull request is the first
one to pass the gates:

1. **Pull request A, the security pipeline:** `zizmor.yml`, `semgrep.yml`,
   `dependency-audit.yml`, `renovate.json`, `.semgrepignore`,
   `SECURITY-PIPELINE.md`, the requirements recompiled with hashes on 3.14, the
   Dockerfile's base image pinned and installing with `--require-hashes`, and
   `.gitlab-ci.yml` cut down to `create-pages`. Before it, the manual
   prerequisites above. After it merges, the rulesets with `audit` and `scan`.
2. **Pull request B, the deployment:** `acc-ci.yml`, the API's `/health`, the
   Dockerfile's build metadata, and `deployment/vm/`. Once its `test` and
   `build` have reported, they are added to the `acc` ruleset.
3. Merge B: the first image is pushed; `deploy-acc` waits and times out, since no
   VM listens yet. Expected, and said so in the pull request.
   **Then make the package public:** a container package created by the first
   push is private, so the VM's anonymous pull would fail. An `open-regels`
   organisation admin sets `cprmv-api` to public and links it to the repository
   (package settings). Check anonymously afterwards:
   `docker manifest inspect ghcr.io/open-regels/cprmv-api:sha-<commit>` from a
   machine that is not logged in.
4. Provision the VM (`provision.sh`, run by the user). cloud-init bootstraps it
   and the reconciler deploys the head of `acc`; check `/health` and
   `deploy-status.json` over HTTP on the new IP.
5. Move DNS (`cutover-dns.sh`, run by the user); Caddy obtains a certificate.
   Stop the old VM's acc container.
6. Prove it: a small follow-up pull request (the `CHANGELOG`) merged into `acc`
   must reach the VM with `deploy-acc` green, and running the reconciler twice by
   hand must change nothing the second time.

## The stable tier (added 26 November 2026)

The acceptance deployment proved itself end to end on 26 November 2026 (PR #23:
merge to running on the VM in five minutes, `deploy-acc` green). The same shape
now carries the **stable** tier: the release on `main`, served at
`https://cprmv.open-regels.nl` with its API at `/docs` and the ReSpec at
`/respec`. "Stable" is the IOU name for the released, non-acceptance version
(as in lvg's `azure-lvg-stable.yml`); it is not the external production
platform.

### Decided

- **A dedicated VM** for the stable tier, CPRMV only, like acceptance. The IOU
  components on the old VM (Keycloak, Operaton, Skosmos) get VMs of their own in
  separate work, and their production instances move to external providers.
- **The image is built again on `main`.** A push to `main` builds, tests,
  publishes and attests `sha-<main commit>`, exactly as a push to `acc` does,
  so the reconciler and `/health` work unchanged. Promoting the acceptance image
  byte for byte was considered and set aside: the image would report the `acc`
  commit, not the `main` merge commit, and the reconciler's
  `build.sha == target` check would need a second rule. With the pinned base
  image and hash-locked requirements the rebuild is close to identical, but not
  guaranteed byte-identical.
- **The TLSA record `_443._tcp.cprmv` is removed** at cutover. It pins the old
  server's key (3 1 1); the new VM's certificate comes from Let's Encrypt with a
  key Caddy may rotate at renewal, so a key pin would keep breaking. Nobody
  knows why it was set; if something depends on it, that will surface.

### Design

- **One workflow for both branches.** `acc-ci.yml` becomes `ci.yml`, triggered
  by pull requests into and pushes to `acc` and `main`. The job ids `test` and
  `build` stay, so the rulesets keep matching; `publish` and `deploy-acc` become
  `publish` and `deploy`, with the tier taken from the branch:

  | Branch | Tier | Host | Tags pushed | Environment |
  |---|---|---|---|---|
  | `acc` | `acc` | `acc.cprmv.open-regels.nl` | `sha-<commit>`, `acc` | `acceptance` |
  | `main` | `stable` | `cprmv.open-regels.nl` | `sha-<commit>`, `stable`, `<version>` | `stable` |

  `<version>` is the `version` in `serve_api/pyproject.toml`. A second build of
  the same version (a re-run, or a later commit before the version is bumped)
  moves that tag; the VM pins by digest, so nothing that runs moves with it.
- **The reconciler is unchanged in logic.** The tier `stable` follows the branch
  `main`: the systemd unit reads `CPRMV_BRANCH` from `/etc/cprmv/%i.env` when
  that file exists (written by cloud-init for `stable`; `acc` needs none, since
  its branch equals its tier).
- **`deployment/vm/stable/`** holds the stable tier's `compose.yml` and
  `Caddyfile`: the same as acceptance with the host `cprmv.open-regels.nl` and
  the paths under `/opt/cprmv/stable/`.
- **Provisioning takes the tier.** `provision.sh`, `cloud-init.yaml` and
  `cutover-dns.sh` move from `deployment/vm/acc/` to `deployment/vm/` and take
  `TIER=acc|stable` (default `acc`), deriving the resource names
  (`rg-cprmv-<tier>`, `vm-cprmv-<tier>`, …), the DNS record (`acc.cprmv` or
  `cprmv`) and the branch. One copy of each script, not two. For `stable`,
  `cutover-dns.sh` also deletes the TLSA record set `_443._tcp.cprmv`, after
  the A record has moved, and says so.
- **The `main` ruleset** additionally requires `test` and `build`, as `acc`
  does, once they have reported on a pull request into `main`.

### Release flow

1. A pull request from `acc` into `main` ("Release 0.4.x"). `audit`, `scan`,
   `test` and `build` run on it. The version in `pyproject.toml` is bumped on
   `acc` before.
2. Merge: `publish` builds and pushes the stable image, the stable VM deploys
   it, `deploy` goes green.
3. GitLab: `main` is pushed fast-forward to the `gitlab` remote, which starts
   the Pages job and publishes the ReSpec. That push is asked for each time.

### Rollout

1. Pull request with the above into `acc`; merged, acceptance keeps working
   (its unit, paths and names do not change).
2. Release pull request `acc` → `main` (0.4.3 plus the deployment). Its merge
   publishes the first stable image; `deploy` times out, as on acceptance.
3. Lower the `cprmv` TTL; provision `TIER=stable`; check the new VM over its IP.
4. Cut over: `cprmv` → the new IP, TLSA removed. Check
   `https://cprmv.open-regels.nl/health`, `/docs`, `/respec`.
5. Add `test` and `build` to the `main` ruleset. Stop the old VM's CPRMV
   containers and remove both CPRMV site blocks from its Caddyfile.

### Not in this addition

- The old `cprmv-dev` DNS records (A and TLSA), which point at the old VM:
  removed together with that VM's CPRMV containers, by hand.
- The IOU components' own VMs.

## Follow-ups (not in this design)

- Verify provenance on the VM before applying an image.
- ~~Production: `deployment/vm/prod/`, a promotion workflow on `main`, its own VM
  or tier instance, versioned tags.~~ Done differently on 26 November 2026: see
  "The stable tier".
- Port lvg's `check-supply-chain` (pin register against the workflows).
- A `pre-commit` pre-push hook, and a formatter, if Bas wants them.
- An image vulnerability scan (for instance Trivy) and an SBOM, which the larger
  IOU repositories have and lvg does not.
- GitLab as a publication-only mirror: a README note pointing development to
  GitHub, and merge requests disabled. Not archived, since Pages still
  publishes from it.
- Where the IOU standards are published, together, and whether the ReSpec can
  leave GitLab Pages.
- Restore the commented-out tests.
- Lift the reconciler into a form the other IOU repositories can share, once a
  second repository uses it.

## Left to the builder

- Exact Caddy version and digest at build time.
- How `reconcile.sh` serialises JSON (`jq` is fine to require on the VM).
- The wording of the runbook.
- The exact pinned versions of zizmor, semgrep, pip-tools, pip-audit and the
  Renovate validator (take lvg's where they apply).
- Test coverage for `reconcile.sh` (for instance a `bats` suite with `docker`
  and `git` stubbed) — expected, shape left open.
