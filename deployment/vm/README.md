# The CPRMV VMs

The CPRMV API runs on two Azure VMs, one per tier, that keep themselves current:

| Tier     | Branch | Host                        | VM             | Deployment directory   |
| -------- | ------ | --------------------------- | -------------- | ---------------------- |
| `acc`    | `acc`  | `acc.cprmv.open-regels.nl`  | `vm-cprmv-acc`    | `deployment/vm/acc/`    |
| `stable` | `main` | `cprmv.open-regels.nl`      | `vm-cprmv-stable` | `deployment/vm/stable/` |

A timer on each VM runs `reconcile.sh <tier>` every 2 minutes: it fetches the head
of the tier's branch from GitHub, pulls the matching image from GHCR
(`sha-<commit>`), applies `deployment/vm/<tier>/` from that commit with Docker
Compose, checks `/health`, and writes `deploy-status.json`. A merge into `acc` or
`main` is therefore a deploy. Nothing connects to a VM to deploy; SSH is for
emergencies.

The design is in `docs/superpowers/specs/2026-11-24-acc-vm-deployment-design.md`.

## What the VM needs

- Ubuntu 24.04 LTS on **x86-64** (the image is `linux/amd64` only), Docker Engine
  with the compose plugin, git, jq, util-linux (`flock`), curl. cloud-init installs
  them.
- Inbound 80 and 443 from anywhere (the site and ACME HTTP-01). SSH from one
  address only.
- Outbound HTTPS **open**, as on an Azure VM by default. If it is ever narrowed to
  an allowlist, keep: `github.com`, `ghcr.io`, `pkg-containers.githubusercontent.com`
  (image layers), Let's Encrypt (`acme-v02.api.letsencrypt.org` and its OCSP/CRL
  hosts), Docker's apt repository (`download.docker.com`) for provisioning, Docker
  Hub for the Caddy image (`registry-1.docker.io`, `auth.docker.io`,
  `production.cloudflare.docker.com`), and every
  external service the API calls, as named in `serve_api/data/cprmvmethods.ttl`
  and `serve_api/methods/` (for instance `repository.officiele-overheidspublicaties.nl`,
  `service.omgevingswet.overheid.nl`, `api-organisaties.overheid.nl`).
- DNS: the tier's host pointing at the VM (`cutover-dns.sh`).

On the VM, for tier `acc` (for `stable`, read `stable` for `acc`):

| Path                                       | What                                                 |
| ------------------------------------------ | ---------------------------------------------------- |
| `/usr/local/lib/cprmv/reconcile.sh`        | the reconciler, installed once, never self-updating  |
| `/etc/systemd/system/cprmv-reconcile@.*`   | its service and timer, instantiated as `@acc`        |
| `/etc/cprmv/stable.env`                    | stable only: `CPRMV_BRANCH=main` (acc needs none)    |
| `/opt/cprmv/acc/repo/`                     | bare repository the reconciler creates and fetches   |
| `/opt/cprmv/acc/releases/<sha>/`           | `deployment/vm/acc/` at `<sha>`, plus `.env`         |
| `/opt/cprmv/acc/current`                   | symlink to the release that runs                     |
| `/opt/cprmv/acc/state.json`                | running, previous, failed commits                    |
| `/opt/cprmv/acc/www/deploy-status.json`    | what Caddy serves publicly                           |

## Provisioning

Everything that writes to Azure is run by the **user**, never by an assistant.
Sign in first with `az login --tenant <the ICTU tenant>`. `provision.sh`,
`cloud-init.yaml` and `cutover-dns.sh` sit in `deployment/vm/` and serve both
tiers; `TIER=acc` (the default) or `TIER=stable` selects one. The scripts are
self-contained, so copy them to a short path and run them from there, pointing
`REPO_ROOT` at the checkout (provision.sh embeds the reconciler and its units from
it into the cloud-init user data, so the VM gets exactly the files that were
reviewed; nothing is fetched at boot):

```
cp deployment/vm/provision.sh ~/provision-cprmv.sh
! TIER=acc SUBSCRIPTION=<subscription id> ADMIN_SSH_SOURCE=<your address> REPO_ROOT=$PWD bash ~/provision-cprmv.sh
! TIER=stable SUBSCRIPTION=<subscription id> ADMIN_SSH_SOURCE=<your address> REPO_ROOT=$PWD bash ~/provision-cprmv.sh
```

`SUBSCRIPTION` and `ADMIN_SSH_SOURCE` are required and are never written to a file:
the repository is public. (`DNS_RESOURCE_GROUP` is read by `cutover-dns.sh`; the
same line can carry it.) The tier gives the defaults:

| Setting                            | `TIER=acc`         | `TIER=stable`         |
| ---------------------------------- | ------------------ | --------------------- |
| resource group                     | `rg-cprmv-acc`     | `rg-cprmv-stable`     |
| VM                                 | `vm-cprmv-acc`     | `vm-cprmv-stable`     |
| vnet, subnet, NSG, public IP       | `vnet-`, `snet-`, `nsg-`, `pip-cprmv-acc` | `vnet-`, `snet-`, `nsg-`, `pip-cprmv-stable` |
| branch (`BRANCH`)                  | `acc`              | `main`                |
| DNS record (`DNS_RECORD`)          | `acc.cprmv`        | `cprmv`               |

Both use `westeurope`, `Standard_B2ms`, Ubuntu 24.04, the admin user and the key
`~/.ssh/id_ed25519.pub`. Every default sits at the top of the script and can be
overridden by an environment variable of the same name. The script is idempotent:
it shows each resource first and creates only what is missing; an NSG rule whose
source differs is updated.

For `stable`, cloud-init also writes `/etc/cprmv/stable.env` with
`CPRMV_BRANCH=main`, which the reconciler's unit reads, so the tier `stable`
follows the branch `main`. Both tiers are rendered from the one
`cloud-init.yaml` template.

Remove the copy afterwards (`rm ~/provision-cprmv.sh`). The VM is tagged with the
hash of the cloud-init it was created with; a later run says so when the rendered
cloud-init differs. `TIER=<tier> bash provision.sh --render <file>` writes the
rendered cloud-init without touching Azure.

The acc VM provisioned on 26 November 2026 predates `EnvironmentFile=` in
`cprmv-reconcile@.service`, so a re-run of provision.sh for acc reports that
cloud-init changed. That is expected (acc needs no env file) and is not a reason
to delete the VM. To bring the unit in line, install it as described under
"Installing a changed reconciler".

### Checks after provisioning

First, the `cprmv-api` package on GHCR must be public and linked to the repository,
or the VM cannot pull the image. Check anonymously, with `<head>` the head of the
tier's branch (`acc` or `main`):

```
DOCKER_CONFIG=$(mktemp -d) docker manifest inspect ghcr.io/open-regels/cprmv-api:sha-<head>
```

Until the first deploy nothing listens on port 80, so read the status over SSH:
`sudo cat /opt/cprmv/<tier>/www/deploy-status.json`. `waiting` or `stalled` clears
by itself once the image can be pulled.

cloud-init takes a few minutes; the first reconciler run follows within about
three. With `<ip>` as printed by the script and `<host>` the tier's host
(`acc.cprmv.open-regels.nl` or `cprmv.open-regels.nl`):

```
curl -s -o /dev/null -w '%{http_code}\n' http://<ip>/health        # 200 (GET only; HEAD gives 405)
curl -I -H 'Host: <host>' http://<ip>/                             # 308 redirect to https
curl -sI http://<ip>/deploy-status.json                            # Cache-Control: no-store
curl -s http://<ip>/deploy-status.json                             # "state": "running"
```

### Moving DNS

The A record `cprmv` in the zone `open-regels.nl` has a TTL of 3600; `acc.cprmv`
was lowered to 300 at its cutover. Copy the script first, then a day ahead lower the TTL so the cutover takes
effect quickly:

```
cp deployment/vm/cutover-dns.sh ~/cutover-dns.sh
! TIER=<tier> SUBSCRIPTION=<subscription id> DNS_RESOURCE_GROUP=<resource group> bash ~/cutover-dns.sh --lower-ttl
```

Then, once the new VM reports `running`:

```
! TIER=<tier> SUBSCRIPTION=<subscription id> DNS_RESOURCE_GROUP=<resource group> bash ~/cutover-dns.sh
rm ~/cutover-dns.sh
```

It refuses unless `http://<new ip>/deploy-status.json` has `state` `running`,
sets the record to exactly the new IP (TTL 300), checks that the record set holds
nothing else, and prints the old and new values. For `stable` it then deletes the
TLSA record set `_443._tcp.cprmv` if there is one, and says whether it did: that
record pins the old server's key, and Caddy's Let's Encrypt key may change at
renewal. For `acc` it touches no TLSA record. Caddy retries ACME with backoff
from its startup, so the certificate should appear within a few minutes of DNS
moving; if it does not, restart Caddy over SSH:
`sudo docker compose -p cprmv-<tier> -f /opt/cprmv/<tier>/current/compose.yml restart caddy`.
Afterwards, stop the old VM's CPRMV container by hand; the scripts never touch it.

### Serving cprmv.open-rules.eu

`cprmv.open-rules.eu` is an alias on the stable VM: the stable Caddyfile lists it
next to `cprmv.open-regels.nl`, so the same API answers on both names, each with
its own certificate. Caddy can obtain that certificate only once the name's DNS
points at the stable VM. To move it, lower the TTL a day ahead, then cut over,
with the zone and record overridden:

```
cp deployment/vm/cutover-dns.sh ~/cutover-dns.sh
! TIER=stable SUBSCRIPTION=<subscription id> DNS_RESOURCE_GROUP=<resource group> DNS_ZONE=open-rules.eu DNS_RECORD=cprmv bash ~/cutover-dns.sh --lower-ttl
! TIER=stable SUBSCRIPTION=<subscription id> DNS_RESOURCE_GROUP=<resource group> DNS_ZONE=open-rules.eu DNS_RECORD=cprmv bash ~/cutover-dns.sh
rm ~/cutover-dns.sh
```

The TLSA step then looks for `_443._tcp.cprmv` in `open-rules.eu`; if that record
set does not exist, the script says so and deletes nothing. `DNS_RESOURCE_GROUP`
is the resource group of the `open-rules.eu` zone, which may differ from the one
holding `open-regels.nl`.

### Rolling out the stable tier

Once a release pull request (below) has merged into `main`, so that
`sha-<main head>` is on GHCR. On that first release the `deploy` job times out,
because the stable VM does not exist yet (as it did on acceptance); that is
expected, and the steps below bring the VM up:

1. **Lower the TTL** of `cprmv`, a day ahead. First refresh the script, since an
   older acc-only copy may be in `~`: `cp deployment/vm/cutover-dns.sh ~/cutover-dns.sh`. Then
   `! TIER=stable SUBSCRIPTION=<subscription id> DNS_RESOURCE_GROUP=<resource group> bash ~/cutover-dns.sh --lower-ttl`.
2. **Provision** with `TIER=stable` (see Provisioning).
3. **Check over the IP** with the curl checks above, with `<host>`
   `cprmv.open-regels.nl`, until `deploy-status.json` says `running` with the head
   of `main`.
4. **Cut over** with `TIER=stable` (see Moving DNS): the A record `cprmv` moves to
   the new IP and the TLSA record `_443._tcp.cprmv` is removed. Then check
   `https://cprmv.open-regels.nl/health`, `/docs` and `/respec/`.
5. **Ruleset:** apply `.github/rulesets/main.json`, which requires `test` and
   `build` on `main` as well, only once both have reported on a pull request into
   `main` (see `SECURITY-PIPELINE.md`, "Branch rulesets"). Then stop the old VM's
   CPRMV containers and remove both CPRMV site blocks from its Caddyfile.

## Release flow

1. Bump the version on `acc` (through a pull request, as every change to `acc`)
   in every place the repository writes it: see "Releasing" in the root
   `README.md`. The `<version>` image tag is read from `serve_api/pyproject.toml`.
2. Open a pull request from `acc` into `main` ("Release <version>"). `audit`,
   `scan`, `test` and `build` run on it.
3. Merge it. `publish` builds and pushes `sha-<main commit>`, `stable` and
   `<version>`; the stable VM deploys it within minutes, and `deploy` goes green.
   (On the first release `deploy` times out instead: the stable VM does not exist
   yet. See "Rolling out the stable tier".)
4. GitLab: push `main` fast-forward to the `gitlab` remote, which starts the Pages
   job and publishes the ReSpec. That push is asked for each time; it is never
   part of a merge.

## Reading `deploy-status.json`

`https://<host>/deploy-status.json` (or `http://<ip>/...`):

| Field                      | Meaning                                                               |
| -------------------------- | --------------------------------------------------------------------- |
| `state`                    | see below                                                             |
| `checked_at`               | last run of the reconciler; a stale value means the VM or timer is down |
| `target.sha`               | the head of the tier's branch the reconciler is working towards       |
| `running`                  | the commit and image digest that run now                              |
| `last_attempt`             | the last deploy: `deployed`, `failed` or `restored`, with the error   |
| `reconciler.matches_repo`  | the installed `reconcile.sh` equals the one in the target commit      |
| `warning`                  | something to look at that did not change the state                    |

| State      | Meaning                                                              | Do                                                                 |
| ---------- | -------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `running`  | The target runs and is healthy.                                      | Nothing.                                                           |
| `waiting`  | The target's image is not on GHCR yet (the build is probably running). What ran before keeps running. | Nothing; it resolves itself.  |
| `stalled`  | Still no image for the target after 30 minutes.                      | Look at the `build` or `publish` job of that commit. A new commit unblocks it.  |
| `failed`   | The target did not come up; the previous release was restored (`last_attempt.result` says `restored`) or nothing ran before. The commit is not retried. | Read `last_attempt.error`, fix, merge a new commit. |
| `broken`   | The target failed **and** the restore failed: nothing reliable runs. | **The only state that needs a person.** SSH in, read `journalctl -u cprmv-reconcile@<tier>` and `/opt/cprmv/<tier>/state.json`, and bring a release up by hand with `docker compose -p cprmv-<tier> ...`. |

On the VM, to read the status or run the reconciler by hand (for `stable`, read
`stable` for `acc`; run by hand, `stable` also needs `CPRMV_BRANCH=main`, which
the unit takes from `/etc/cprmv/stable.env`):

```
sudo cat /opt/cprmv/acc/www/deploy-status.json
sudo -u cprmv /usr/local/lib/cprmv/reconcile.sh acc
sudo -u cprmv CPRMV_BRANCH=main /usr/local/lib/cprmv/reconcile.sh stable
journalctl -u cprmv-reconcile@acc --since '1 hour ago'
```

Run twice by hand, it must change nothing the second time.

## Installing a changed reconciler

The reconciler never updates itself, so that a bad merge cannot replace the thing
that would roll it back. When a pull request changes `reconcile.sh`,
`reconciler.matches_repo` reads `false` until someone installs the new copy (it
compares only `reconcile.sh`; a changed unit shows no such sign). Over SSH, from a
checkout at the commit that is deployed:

```
scp deployment/vm/reconciler/reconcile.sh <admin>@<ip>:/tmp/reconcile.sh
ssh <admin>@<ip> 'sudo install -m 0755 -o root -g root /tmp/reconcile.sh /usr/local/lib/cprmv/reconcile.sh && rm /tmp/reconcile.sh'
```

For a changed unit file, copy it to `/etc/systemd/system/` the same way (mode 0644)
and reload systemd; the next timer run uses it:

```
scp deployment/vm/reconciler/cprmv-reconcile@.service <admin>@<ip>:/tmp/cprmv-reconcile@.service
ssh <admin>@<ip> 'sudo install -m 0644 -o root -g root /tmp/cprmv-reconcile@.service /etc/systemd/system/cprmv-reconcile@.service && rm /tmp/cprmv-reconcile@.service && sudo systemctl daemon-reload'
```

The timer unit (`cprmv-reconcile@.timer`) goes the same way. The alternative is to reprovision: delete the VM
and run `provision.sh` again (the static public IP, NSG and network are kept).

## Adding a tier

The units are templated on the tier and `/opt/cprmv` belongs to `cprmv`, so a tier
`prod` is: a directory `deployment/vm/prod/` with its own `compose.yml` and
`Caddyfile` (its `compose.yml` mounts `/opt/cprmv/prod/www`), a branch of the same
name (or `CPRMV_BRANCH` in `/etc/cprmv/prod.env`), and
`sudo systemctl enable --now cprmv-reconcile@prod.timer`. The reconciler creates
`/opt/cprmv/prod` itself and is the same script. Two tiers on one VM would both
want ports 80 and 443; each tier gets its own VM, as `acc` and `stable` do. To
provision one with the scripts here, add the tier to the `case` at the top of
`provision.sh` and `cutover-dns.sh`.

## Things to know

- **Caddy restarts on every deploy.** Each release has its own directory, so the
  Caddyfile's mount source changes every time and compose recreates Caddy. Accepted:
  a brief connection drop per deploy.
- The `cprmv` user is in the `docker` group, which is root-equivalent. It is a
  system account without a login shell.
- Quiet throwaway containers, as used in this repository's checks, pass
  `-e PIP_ROOT_USER_ACTION=ignore -e PIP_DISABLE_PIP_VERSION_CHECK=1` so that pip
  prints no root-user or upgrade notices.
