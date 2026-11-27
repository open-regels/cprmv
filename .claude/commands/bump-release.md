# bump-release

Cut a CPRMV release: give it a release number, write that number to
`serve_api/RELEASE`, generate the release SBOM, and take it through `acc` to
`main` and on to the GitLab mirror. Usage: `/bump-release` (computes the next
number) or `/bump-release vYYYY.MM.N` (an explicit number).

This is the command `ronl-business-api`, `linked-data-explorer` and `ttl-editor`
use, adapted to CPRMV and without the changelog machinery: there is no changelog
entry to author, no scope, no `package.json` to bump. The design is
`docs/superpowers/specs/2026-11-27-release-versioning-design.md`.

> **Why a release number next to the version.** CPRMV's `version` (0.4.3) is the
> **vocabulary version**: it runs through `rdf/<version>/`, the ReSpec, the
> namespaces, the `/<version>/methods/` route and the image tag `:<version>`.
> Stable has been released several times at 0.4.3 with different dependencies,
> so "0.4.3" does not say what runs. The release number does. Raising the
> vocabulary version is a separate, occasional change (step 2); a release does
> not need one.

## What this command never does

- **Never pushes to `acc` or `main`, and never merges a pull request.** Both
  branches change only through a pull request merged by the user. The command
  opens the pull requests, watches their checks, and reports; the user merges.
  The rulesets on both branches require `audit`, `scan`, `test` and `build`, and
  allow merge commits only.
- **Never commits without asking**, every time, however many releases went
  before. Prepare, stage, report what is staged, then stop and ask.
- **Never adds attribution lines** to a commit, a pull request or anything else:
  no `Co-Authored-By`, no "Generated with", no session links.
- **Never bypasses a gate**: no `--no-verify`, no skipped hooks. A failing check
  is the message; read it and fix what it names, or stop and report.
- **Never starts, stops or restarts a server**, local or on a VM. The VMs deploy
  themselves (below); if one does not, report it.

The one write to a shared branch it does make is pushing `main` to the `gitlab`
remote (step 6). In this repository that is a fixed step of every release, and
running `/bump-release` is the go-ahead for it, decided by the user on 27
November 2026. It is fast-forward only, checked before and confirmed after; if
GitLab has diverged, the command stops.

## Release numbers: CalVer `vYYYY.MM.N`

- `v2026.11.0`: the first release in November 2026
- `v2026.11.1`: a follow-up in the same month
- `v2026.12.0`: the first release of the next month (the count restarts)

With a `v` prefix, unlike the siblings' `YYYY.MM.patch` strings: the number is
also an image tag and part of the SBOM's file name, where the `v` keeps it from
reading as a vocabulary version. No git tags, no GitHub Releases, as in the other
apps.

`serve_api/RELEASE` holds the number: one line, nothing else, written only by
this command. `ci.yml` reads it with `scripts/read-release.sh`, validates it as
a whole string against `^v[0-9]{4}\.(0[1-9]|1[0-2])\.[0-9]+$`, and fails the
build on anything else. It is passed to the image as `BUILD_RELEASE` on **both**
tiers, so `/health` reports it as `"release"`: on stable the release that runs,
on acceptance the last release its code is at or after (`build.sha` says
exactly what runs). On `main`, `publish` also tags the image `:vYYYY.MM.N`.

## How a merge deploys

There is nothing to deploy by hand. A merge into `acc` or `main` runs `ci.yml`:
`test`, `build`, `publish` (the image to GHCR) and `deploy`, which waits for the
tier's VM to run the commit. The VM pulls: every 2 minutes its reconciler reads
the head of its branch, pulls the image for that commit by digest, checks
`/health`, and rolls back if that fails. So every merge in this command is a
deploy, of acceptance (step 3) or stable (step 4).

## Steps

### 0. Reconcile outstanding pull requests

Run this **before computing anything**. A pull request merged after the release
is cut is not in it, and one merged into `acc` during the release lands on
stable unannounced when the promotion carries it.

```bash
gh pr list --repo open-regels/cprmv --state open --json number,title,author,baseRefName,headRefName,mergeStateStatus
```

Present them, Renovate's and anyone else's, and ask which belong in this
release: all, a subset, or none. Out-of-scope ones stay open for the next
release. Then:

1. **The user merges the in-scope ones**, into `acc`, before step 3. Never merge
   one yourself, unless the user asks for that specific pull request.
2. **Read each one's checks, not only `mergeStateStatus`.** `CLEAN` with zero
   checks has not run the gate, it has not passed it:

   ```bash
   gh pr checks <n> --repo open-regels/cprmv
   ```

3. **Re-check mergeability between merges** when several touch the same file
   (`serve_api/requirements*.txt` above all). The `acc` ruleset does not require
   branches to be up to date, so merging one leaves the next on a stale tree;
   Renovate rebases on conflict, not otherwise.
4. **Say that each merge into `acc` deploys acceptance** when proposing several.
5. **A dependency pull request changes the release SBOM.** The SBOM is generated
   in step 3 from `serve_api/requirements.txt` as it is on `origin/acc` then, so
   merge first, generate after. A late merge into `acc` while the release pull
   request is open makes its strict SBOM check stale: regenerate (step 3) on the
   release branch after bringing it up to date.

### 1. Compute the release number

Read the last number on **both** branches. `acc` can be ahead of `main`: a
release pull request into `acc` merged, and its promotion never happened.

```bash
git fetch --prune origin
LAST_MAIN=$(git show origin/main:serve_api/RELEASE 2>/dev/null || true)
LAST_ACC=$(git show origin/acc:serve_api/RELEASE 2>/dev/null || true)
EXPLICIT=""        # or the number passed to /bump-release
```

- **If `acc` holds a number `main` does not** (`LAST_ACC` later than
  `LAST_MAIN`), an earlier release reached `acc` and was never promoted. Say so
  and ask: finish that release (step 4 onwards) instead of cutting a new one, or
  fold it into this one. Folding releases a **new** number, later than `acc`'s;
  reusing `acc`'s number would name two different trees, and its SBOM is already
  on `acc`.
- Then compute the next number. It must be later than **both** branches' numbers,
  so it counts on from the later of the two:

  ```bash
  # Next release number (tested against the cases below)
  MONTH=${MONTH:-$(date +%Y.%m)}
  # sort -V, never a lexical sort: v2026.11.10 is later than v2026.11.9.
  LAST=$(printf '%s\n' "$LAST_MAIN" "$LAST_ACC" | grep -v '^$' | sort -V | tail -n 1 || true)
  if [ -n "$EXPLICIT" ]; then
    NEXT=$EXPLICIT
  elif [[ "$LAST" =~ ^v([0-9]{4}\.[0-9]{2})\.([0-9]+)$ ]] && [ "${BASH_REMATCH[1]}" = "$MONTH" ]; then
    # 10#: a count is decimal, whatever leading zeros it has.
    NEXT="v$MONTH.$((10#${BASH_REMATCH[2]} + 1))"
  else
    NEXT="v$MONTH.0"
  fi
  if ! [[ "$NEXT" =~ ^v[0-9]{4}\.(0[1-9]|1[0-2])\.[0-9]+$ ]]; then
    echo "REFUSED: $NEXT is not vYYYY.MM.N"; NEXT=""
  elif [ -n "$LAST" ] && { [ "$NEXT" = "$LAST" ] ||
    [ "$(printf '%s\n' "$LAST" "$NEXT" | sort -V | tail -n 1)" = "$LAST" ]; }; then
    echo "REFUSED: $NEXT is not later than $LAST (main ${LAST_MAIN:-none}, acc ${LAST_ACC:-none})"; NEXT=""
  elif git cat-file -e "origin/acc:docs/sbom/cprmv-api-$NEXT.cdx.json" 2>/dev/null; then
    echo "REFUSED: docs/sbom/cprmv-api-$NEXT.cdx.json already exists on origin/acc"; NEXT=""
  fi
  echo "main: ${LAST_MAIN:-none}  acc: ${LAST_ACC:-none}  next: ${NEXT:-none}"
  ```

  | main         | acc          | explicit     | next                                  |
  | ------------ | ------------ | ------------ | ------------------------------------- |
  | none         | none         |              | `v2026.11.0` (the first release)      |
  | `v2026.11.0` | none         |              | `v2026.11.1`                          |
  | `v2026.11.0` | `v2026.11.1` |              | `v2026.11.2`                          |
  | `v2026.10.4` | `v2026.10.4` |              | `v2026.11.0` (a new month)            |
  | `v2026.11.9` | `v2026.11.9` |              | `v2026.11.10`                         |
  | `v2026.11.0` | `v2026.11.1` | `v2026.11.1` | refused: not later than `acc`         |

  (Examples for November 2026.) The checks also refuse a number that is not
  `vYYYY.MM.N` (the expression CI uses), and one whose SBOM is already on
  `origin/acc`. A clock that is behind the last release's month makes the
  computed number earlier than it: refused too.

- **When it says REFUSED, stop and ask**; do not correct the number yourself.

State the number and ask the user to confirm it before going on.

### 2. Ask whether the vocabulary version changes too

Ask, and do not assume either way. Usually it does not: most releases carry
dependency updates, fixes and deployment changes at the same vocabulary version.

If it does, **this command does not bump it.** That is a change to the
vocabulary, the ReSpec and the API's routes and namespaces, with its own pull
request into `acc` and its own `CHANGELOG.md` entry, made and merged **before**
step 3. "Releasing" in `README.md` lists every file it touches. Then continue
here; the release carries it.

### 3. Prepare the release on `acc`

Branch from `origin/acc` (not from a local `acc`, which may be behind):

```bash
git switch -c "release/$NEXT" origin/acc
printf '%s\n' "$NEXT" > serve_api/RELEASE
bash scripts/read-release.sh          # expect: release=vYYYY.MM.N
```

`read-release.sh` is the check CI runs; run it here so a typo fails now, not in
`build`.

**Generate the release SBOM** with the image and the tool CI uses. Both are read
from the repository rather than written here, because Renovate moves the image
digest in `serve_api/Dockerfile` and the tool pin lives in `sbom.yml`:

```bash
PY_IMAGE=$(sed -n 's/^FROM \(python:[^ ]*\).*/\1/p' serve_api/Dockerfile | tr -d '\r')
CDX=$(grep -oE 'cyclonedx-bom==[0-9.]+' .github/workflows/sbom.yml)
echo "$PY_IMAGE / $CDX"
MSYS_NO_PATHCONV=1 docker run --rm \
  -e PIP_ROOT_USER_ACTION=ignore -e PIP_DISABLE_PIP_VERSION_CHECK=1 \
  -v "$PWD:/w" -w /w "$PY_IMAGE" \
  sh -c "pip install -q $CDX && python scripts/write-sbom.py && python scripts/write-sbom.py --check"
```

At the time of writing that is
`python:3.14-bookworm@sha256:fbaf91204f2758a70a7f7d6cf3c2871851227152a54e6a7b5b59941c4566b6b5`
with `cyclonedx-bom==8.0.1`. Stop if either variable comes back empty. On Linux
the file is written as root; `chown` it back before staging.

This writes `docs/sbom/cprmv-api-$NEXT.cdx.json` from
`serve_api/requirements.txt`. ICTU recommendation 10 asks for an SBOM per
released version, kept analysable: when an advisory lands against something
that shipped months ago, only a document written at the time says what it
contained. The `Release SBOM` workflow uploads the same document as an artifact,
but artifacts expire after 90 days on a public repository; the committed copy
is the durable one. Earlier releases' files stay where they are, and so does
`cprmv-api-0.4.3.cdx.json`, the record of what stable ran before release
numbers.

**The strict check is yours, here, and again on the pull request.** `--check`
fails on a file that does not describe the requirements it ships with. The
`release-sbom` job runs the same check on this pull request, because it changes
this release's file. Run it again after anything that moves the requirements
before the commit (a rebase, a late dependency merge).

Then the tests, as CI runs them, in the same image:

```bash
MSYS_NO_PATHCONV=1 docker run --rm \
  -e PIP_ROOT_USER_ACTION=ignore -e PIP_DISABLE_PIP_VERSION_CHECK=1 \
  -v "$PWD:/w" -w /w "$PY_IMAGE" \
  sh -c "pip install -q --require-hashes -r serve_api/requirements-dev.txt && cd serve_api && pytest -q"
```

Stage exactly the two files and report:

```bash
git add serve_api/RELEASE "docs/sbom/cprmv-api-$NEXT.cdx.json"
git status --short
```

State the release number, the SBOM's component count (the script prints it),
that `--check` and `pytest` passed with their counts, and whether the vocabulary
version changed in this release. **Then ask whether to commit.** Do not commit
unless the user says so. The message:

```
chore: release vYYYY.MM.N
```

with a short body if there is something to say (which pull requests the release
gathers, whether the vocabulary version changed). No attribution lines.

After the commit, when the user confirms, push and open the pull request into
`acc`:

```bash
git push -u origin "release/$NEXT"
gh pr create --repo open-regels/cprmv --base acc --head "release/$NEXT" \
  --title "Release $NEXT" --body-file <file>
gh pr checks <n> --repo open-regels/cprmv --watch
```

The body says what the release carries (the pull requests from step 0, the
vocabulary version, the SBOM file) and nothing else: no attribution lines.
Write it to a file in the scratchpad and pass `--body-file`; long text with
quotes breaks a shell heredoc.

`audit`, `scan`, `test` and `build` must pass, and `release-sbom` (not required,
but it is the strict SBOM check) must too. Report the URL and let **the user
merge it**. Merging deploys acceptance; once `ci.yml` is green on the merge
commit, acceptance should report the release:

```bash
ACC_MERGE=$(gh pr view <n> --repo open-regels/cprmv --json mergeCommit --jq .mergeCommit.oid)
gh run list --repo open-regels/cprmv --workflow ci.yml --commit "$ACC_MERGE" --json databaseId,status,conclusion
curl -fsS https://acc.cprmv.open-regels.nl/health | jq '{environment, release, build}'
```

`release` must be `$NEXT` and `build.sha` `$ACC_MERGE`. Keep `ACC_MERGE` for
the report in step 7.

### 4. Promote `acc` to `main`

```bash
git fetch --prune origin
git show origin/acc:serve_api/RELEASE      # must print $NEXT
git log --oneline --no-merges origin/main..origin/acc
gh pr create --repo open-regels/cprmv --base main --head acc \
  --title "Release $NEXT" --body-file <file>
gh pr checks <n> --repo open-regels/cprmv --watch
```

The body lists what `acc` carries beyond `main` (the `git log` above). This pull
request adds `serve_api/RELEASE` and this release's SBOM relative to `main`, so
`release-sbom` runs the strict check on it as well. If it fails, requirements
changed on `acc` after step 3: stop and ask whether to regenerate the SBOM on a
new release branch, or to release with a new number. Report the URL and let
**the user merge it**, with a merge commit (the only method the `main` ruleset
allows). Merging deploys stable.

### 5. Confirm stable runs the release

```bash
MERGE=$(gh pr view <n> --repo open-regels/cprmv --json mergeCommit --jq .mergeCommit.oid)
gh run list --repo open-regels/cprmv --workflow ci.yml --commit "$MERGE" --json databaseId,status,conclusion
gh run watch <run-id> --repo open-regels/cprmv --exit-status
```

`deploy` passes once the stable VM runs the commit. Then check both stable hosts;
`cprmv.open-rules.eu` is an alias served by the same VM, and both must answer:

```bash
for host in cprmv.open-regels.nl cprmv.open-rules.eu; do
  curl -fsS "https://$host/health" \
    | jq -e --arg r "$NEXT" --arg s "$MERGE" \
        '.environment == "stable" and .release == $r and .build.sha == $s' \
    && echo "$host ok" || echo "$host NOT ok"
done
```

The image tag `:$NEXT` in GHCR, anonymously (the image is public), and the
digest it points to:

```bash
TOKEN=$(curl -fsS "https://ghcr.io/token?scope=repository:open-regels/cprmv-api:pull" | jq -r .token)
curl -fsS -o /dev/null -D - \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json" \
  "https://ghcr.io/v2/open-regels/cprmv-api/manifests/$NEXT" \
  | grep -i '^docker-content-digest'
curl -fsS https://cprmv.open-regels.nl/health | jq -r .image.digest
```

A 200 with a digest means the tag exists. The two digests are expected to match
(both tags are pushed by the same `publish` step); if they do not, report it.

The `Release SBOM` run on the merge commit must be green: on a push to `main`
`--verify-release` fails if `serve_api/RELEASE` or its SBOM is missing. A
warning that the SBOM has drifted means requirements changed on `acc` after
step 3; say so.

```bash
gh run list --repo open-regels/cprmv --workflow sbom.yml --commit "$MERGE" --json databaseId,status,conclusion
```

If anything here fails, stop and report. Do not restart anything: the
reconciler retries nothing it has marked `failed`, and
`https://cprmv.open-regels.nl/deploy-status.json` says why
(`deployment/vm/README.md`, "Reading `deploy-status.json`").

### 6. Push `main` to GitLab

GitLab hosts only the published ReSpec: a push of `main` starts the
`create-pages` job in `.gitlab-ci.yml`, which publishes `html/public` to
`standaarden.open-regels.nl/standards/cprmv/<version>/`. Every gate runs on
GitHub; the `gitlab` remote is outside all of them, pushed by hand, so it is
reconciled here, at the release. Only `main`: GitLab's `acc` is not kept current.

Fast-forward only. Check first, push the **remote-tracking** ref (a local
`main` can lag or hold commits `origin/main` never had), confirm after:

```bash
git fetch --prune origin
git fetch gitlab
if [ "$(git rev-parse gitlab/main)" = "$(git rev-parse origin/main)" ]; then
  echo equal
elif git merge-base --is-ancestor gitlab/main origin/main; then
  echo fast-forward
else
  echo DIVERGED
fi
```

- **DIVERGED**: stop and report. GitLab holds commits GitHub has never seen;
  never force it into line. (A diverged mirror elsewhere was archived as a
  branch first; that is the user's decision.)
- **equal** (`gitlab/main` is `origin/main`): nothing to push, and no new
  Pages pipeline; say so.
- **fast-forward**:

  ```bash
  git push gitlab origin/main:refs/heads/main
  git ls-remote gitlab refs/heads/main
  git rev-parse origin/main
  ```

  The two hashes must match.

Then confirm the Pages pipeline ran for that commit. In the GitLab UI
(`https://git.open-regels.nl/standards/cprmv/-/pipelines`), or through the API if
the project answers anonymously:

```bash
curl -fsS "https://git.open-regels.nl/api/v4/projects/standards%2Fcprmv/pipelines?ref=main&per_page=1" \
  | jq '.[0] | {sha, status, web_url}'
# Git Bash on Windows often has `python` but no `python3`; sed needs neither.
VOCAB=$(sed -n 's/^version = "\([^"]*\)".*/\1/p' serve_api/pyproject.toml | head -n 1 | tr -d '\r')
curl -fsS -o /dev/null -w '%{http_code}\n' "https://standaarden.open-regels.nl/standards/cprmv/$VOCAB/"
```

`sha` must be `origin/main` and `status` `success`; the ReSpec must answer 200.
If the API needs a sign-in, ask the user to look rather than guessing.

### 7. Housekeeping

As the user's global rules define it, with the GitLab push already done:

1. ```bash
   git fetch --prune origin
   OLD_ACC=$(git rev-parse acc)
   git switch main && git merge --ff-only origin/main
   git switch acc && git merge --ff-only origin/acc
   ```

   Fast-forward only, which moves nothing a merged pull request did not put on
   `origin`. If either refuses, stop and report. `acc` stays checked out.
2. Delete the release branch, locally and on `origin`, only once its head is in
   `origin/acc`:

   ```bash
   git merge-base --is-ancestor "release/$NEXT" origin/acc && git branch -d "release/$NEXT"
   git ls-remote --heads origin "release/$NEXT"      # usually empty: delete_branch_on_merge
   git push origin --delete "release/$NEXT"          # only if it survived
   ```

   `-d`, not `-D`: if it refuses, investigate rather than force it.
3. Leftover worktrees and stray stashes: `git worktree list`, `git stash list`.
   Report them; do not drop a stash without asking.
4. The GitLab mirror: done in step 6 (only `main`; GitLab's `acc` is not kept
   current in this repository).
5. Report the `ci.yml` runs for both merge commits, the release pull request's
   into `acc` (`ACC_MERGE`, step 3) and the promotion's into `main` (`MERGE`,
   step 5), with their conclusions:

   ```bash
   for sha in "$ACC_MERGE" "$MERGE"; do
     gh run list --repo open-regels/cprmv --workflow ci.yml --commit "$sha" --json headBranch,headSha,status,conclusion,url
   done
   ```

6. Check the local install against the lockfiles on the branch left checked out.
   This repository has no `deps:check`; compare the fast-forward's old and new
   heads instead:

   ```bash
   git diff --quiet "$OLD_ACC" HEAD -- html/package-lock.json || echo "html/package-lock.json changed"
   git diff --quiet "$OLD_ACC" HEAD -- serve_api/requirements.txt serve_api/requirements-dev.txt || echo "requirements changed"
   ```

   If the lockfile moved, hand the user `npm ci` in `html/`; do not run it. If
   the requirements moved, say so: the tests run in a fresh container, so only a
   local virtual environment, if the user keeps one, needs reinstalling.

## Report

At the end: the release number, whether the vocabulary version changed, the two
pull requests with their merge commits, the stable `/health` of both hosts, the
GHCR tag and digest, the Release SBOM run, the GitLab push (or why there was
none) and the Pages pipeline, and the housekeeping results.
