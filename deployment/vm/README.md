# The acceptance VM

The CPRMV API for acceptance runs on one Azure VM that keeps itself current. A
timer on the VM runs `reconcile.sh acc` every 2 minutes: it fetches the head of
`acc` from GitHub, pulls the matching image from GHCR (`sha-<commit>`), applies
`deployment/vm/acc/` from that commit with Docker Compose, checks `/health`, and
writes `deploy-status.json`. A merge into `acc` is therefore a deploy. Nothing
connects to the VM to deploy; SSH is for emergencies.

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
  hosts), Docker's apt repository (`download.docker.com`) for provisioning, and every
  external service the API calls, as named in `serve_api/data/cprmvmethods.ttl`
  and `serve_api/methods/` (for instance `repository.officiele-overheidspublicaties.nl`,
  `service.omgevingswet.overheid.nl`, `api-organisaties.overheid.nl`).
- DNS: `acc.cprmv.open-regels.nl` pointing at the VM (`cutover-dns.sh`).

On the VM, for tier `acc`:

| Path                                       | What                                                 |
| ------------------------------------------ | ---------------------------------------------------- |
| `/usr/local/lib/cprmv/reconcile.sh`        | the reconciler, installed once, never self-updating  |
| `/etc/systemd/system/cprmv-reconcile@.*`   | its service and timer, instantiated as `@acc`        |
| `/opt/cprmv/acc/repo/`                     | bare repository the reconciler creates and fetches   |
| `/opt/cprmv/acc/releases/<sha>/`           | `deployment/vm/acc/` at `<sha>`, plus `.env`         |
| `/opt/cprmv/acc/current`                   | symlink to the release that runs                     |
| `/opt/cprmv/acc/state.json`                | running, previous, failed commits                    |
| `/opt/cprmv/acc/www/deploy-status.json`    | what Caddy serves publicly                           |

## Provisioning

Everything that writes to Azure is run by the **user**, never by an assistant.
Sign in first with `az login --tenant <the ICTU tenant>`. `provision.sh` and
`cutover-dns.sh` are self-contained, so copy them to a short path and run them
from there, pointing `REPO_ROOT` at the checkout (provision.sh embeds the
reconciler and its units from it into the cloud-init user data, so the VM gets
exactly the files that were reviewed; nothing is fetched at boot):

```
cp deployment/vm/acc/provision.sh ~/provision-acc.sh
! ADMIN_SSH_SOURCE=<your address> REPO_ROOT=$PWD bash ~/provision-acc.sh
```

`ADMIN_SSH_SOURCE` is required and is never written to a file: the repository is
public. Defaults (subscription, `westeurope`, resource group `rg-cprmv-acc`,
`vm-cprmv-acc`, `Standard_B2ms`, Ubuntu 24.04, admin user, key `~/.ssh/id_ed25519.pub`)
sit at the top of the script and can be overridden by environment variables of the
same name. The script is idempotent: it shows each resource first and creates
only what is missing; an NSG rule whose source differs is updated.

Remove the copy afterwards (`rm ~/provision-acc.sh`). The VM is tagged with the hash of the cloud-init it was created with; a later run says so when the rendered cloud-init differs. `bash provision.sh --render
<file>` writes the rendered cloud-init without touching Azure.

### Checks after provisioning

cloud-init takes a few minutes; the first reconciler run follows within about
three. With `<ip>` as printed by the script:

```
curl -s -o /dev/null -w '%{http_code}
' http://<ip>/health        # 200 (GET only; HEAD gives 405)
curl -I -H 'Host: acc.cprmv.open-regels.nl' http://<ip>/           # 308 redirect to https
curl -sI http://<ip>/deploy-status.json                            # Cache-Control: no-store
curl -s http://<ip>/deploy-status.json                             # "state": "running"
```

### Moving DNS

The A record `acc.cprmv` in the zone `open-regels.nl` has a TTL of 3600. Copy the
script first, then a day ahead lower the TTL so the cutover takes effect quickly:

```
cp deployment/vm/acc/cutover-dns.sh ~/cutover-dns.sh
! bash ~/cutover-dns.sh --lower-ttl
```

Then, once the new VM reports `running`:

```
! bash ~/cutover-dns.sh
rm ~/cutover-dns.sh ~/provision-acc.sh
```

It refuses unless `http://<new ip>/deploy-status.json` has `state` `running`,
sets the record to exactly the new IP (TTL 300), checks that the record set holds
nothing else, and prints the old and new values. Caddy retries ACME with backoff
from its startup, so the certificate should appear within a few minutes of DNS
moving; if it does not, restart Caddy over SSH:
`sudo docker compose -p cprmv-acc -f /opt/cprmv/acc/current/compose.yml restart caddy`.
Afterwards, stop the old VM's acc container by hand; the scripts never touch it.

## Reading `deploy-status.json`

`https://acc.cprmv.open-regels.nl/deploy-status.json` (or `http://<ip>/...`):

| Field                      | Meaning                                                               |
| -------------------------- | --------------------------------------------------------------------- |
| `state`                    | see below                                                             |
| `checked_at`               | last run of the reconciler; a stale value means the VM or timer is down |
| `target.sha`               | the head of `acc` the reconciler is working towards                   |
| `running`                  | the commit and image digest that run now                              |
| `last_attempt`             | the last deploy: `deployed`, `failed` or `restored`, with the error   |
| `reconciler.matches_repo`  | the installed `reconcile.sh` equals the one in the target commit      |
| `warning`                  | something to look at that did not change the state                    |

| State      | Meaning                                                              | Do                                                                 |
| ---------- | -------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `running`  | The target runs and is healthy.                                      | Nothing.                                                           |
| `waiting`  | The target's image is not on GHCR yet (the build is probably running). What ran before keeps running. | Nothing; it resolves itself.  |
| `stalled`  | Still no image for the target after 30 minutes.                      | Look at the `build` job of that commit. A new commit unblocks it.  |
| `failed`   | The target did not come up; the previous release was restored (`last_attempt.result` says `restored`) or nothing ran before. The commit is not retried. | Read `last_attempt.error`, fix, merge a new commit. |
| `broken`   | The target failed **and** the restore failed: nothing reliable runs. | **The only state that needs a person.** SSH in, read `journalctl -u cprmv-reconcile@acc` and `/opt/cprmv/acc/state.json`, and bring a release up by hand with `docker compose -p cprmv-acc ...`. |

On the VM, to read the status or run the reconciler by hand:

```
sudo cat /opt/cprmv/acc/www/deploy-status.json
sudo -u cprmv /usr/local/lib/cprmv/reconcile.sh acc
journalctl -u cprmv-reconcile@acc --since '1 hour ago'
```

Run twice by hand, it must change nothing the second time.

## Installing a changed reconciler

The reconciler never updates itself, so that a bad merge cannot replace the thing
that would roll it back. When a pull request changes `reconcile.sh` or the units,
`reconciler.matches_repo` reads `false` until someone installs the new copy. Over
SSH, from a checkout at the commit that is deployed:

```
scp deployment/vm/reconciler/reconcile.sh <admin>@<ip>:/tmp/reconcile.sh
ssh <admin>@<ip> 'sudo install -m 0755 -o root -g root /tmp/reconcile.sh /usr/local/lib/cprmv/reconcile.sh && rm /tmp/reconcile.sh'
```

For the units, copy them to `/etc/systemd/system/` the same way (mode 0644) and run
`sudo systemctl daemon-reload`. The alternative is to reprovision: delete the VM
and run `provision.sh` again (the static public IP, NSG and network are kept).

## Adding a tier

The units are templated on the tier and `/opt/cprmv` belongs to `cprmv`, so a tier
`prod` is: a directory `deployment/vm/prod/` with its own `compose.yml` and
`Caddyfile` (its `compose.yml` mounts `/opt/cprmv/prod/www`), a branch of the same
name (or `CPRMV_BRANCH` in a drop-in), and
`sudo systemctl enable --now cprmv-reconcile@prod.timer`. The reconciler creates
`/opt/cprmv/prod` itself and is the same script. Two tiers on one VM would both
want ports 80 and 443; prod gets its own VM or tier instance, as the design says.

## Things to know

- **Caddy restarts on every deploy.** Each release has its own directory, so the
  Caddyfile's mount source changes every time and compose recreates Caddy. Accepted
  for acceptance: a brief connection drop per deploy.
- The `cprmv` user is in the `docker` group, which is root-equivalent. It is a
  system account without a login shell.
- Quiet throwaway containers, as used in this repository's checks, pass
  `-e PIP_ROOT_USER_ACTION=ignore -e PIP_DISABLE_PIP_VERSION_CHECK=1` so that pip
  prints no root-user or upgrade notices.
