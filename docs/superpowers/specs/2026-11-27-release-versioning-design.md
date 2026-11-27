# CPRMV release versioning and `/bump-release`

Status: approved 27 November 2026 (short design)

## Intent

The other IOU apps release with a CalVer number and a `/bump-release` command
(`ronl-business-api`, `linked-data-explorer`, `ttl-editor`). CPRMV adopts the
numbering and gets its own command, without the changelog machinery.

CPRMV's `version` (0.4.3) is the **vocabulary version**: it runs through
`rdf/<version>/`, the ReSpec, the namespaces, the `/<version>/methods/` route and
the image tag `:<version>`. Stable has been released several times at 0.4.3 with
different dependencies. So a release gets its own number **next to** the
vocabulary version, not instead of it.

## Decided (27 November 2026)

- **Release numbers**: `vYYYY.MM.N`, CalVer with a `v` prefix. `.0` is the first
  release in a month, `.1`, `.2`, … follow-ups in the same month; the count
  restarts each month. No git tags (as in the other apps).
- **`/health`** gains `"release"`, lower case like every other key, between
  `"environment"` and `"build"`:
  `status, version, environment, release, build, image`. `null` when the image
  carries no release (any build before the first release, and local builds).
  After a release, acceptance reports the last release at or before its code
  (see "Into the image" below; amended 27 November 2026 to match it).
- **The SBOM is named after the release**: `docs/sbom/cprmv-api-vYYYY.MM.N.cdx.json`,
  one per release. `cprmv-api-0.4.3.cdx.json` stays as the historical record of
  what stable ran before release numbering.
- **Pushing `main` to GitLab is a fixed step of every release**; running
  `/bump-release` is the go-ahead. Fast-forward only, checked before with
  `git merge-base --is-ancestor`, confirmed after with `git ls-remote gitlab`;
  if GitLab has diverged the command stops and reports.
- **No changelog** adoption.

## Design

- **Where the release lives**: `serve_api/RELEASE`, one line `vYYYY.MM.N`,
  written only by a release. Absent until the first release.
- **Into the image**: the CI workflow reads `serve_api/RELEASE` when present,
  validates it as a whole string against `^v[0-9]{4}\.(0[1-9]|1[0-2])\.[0-9]+$`
  (failing the job otherwise), and passes it as the build argument
  `BUILD_RELEASE`; the Dockerfile turns it into the environment variable
  `BUILD_RELEASE`, as it does for `BUILD_SHA`. `/health` reads it per request;
  unset or empty gives `null`. On `main`, `publish` also tags the image
  `:vYYYY.MM.N`. The release is passed on both tiers: after a release the file is on
  `acc` too, so acceptance reports the last release its code is at or after, and the
  build SHA says exactly what runs (my call).
- **`scripts/write-sbom.py`** names the file after `serve_api/RELEASE`;
  `--verify-release` on `main` fails when `RELEASE` is missing or its SBOM is;
  `--check` on a release pull request as before. Its tests are updated; the
  workflow's paths gain `serve_api/RELEASE`.
- **`.claude/commands/bump-release.md`** (CPRMV-specific), modelled on the
  siblings' command but without changelog steps:
  0. Reconcile open pull requests (Renovate and others): list them, ask which
     belong in the release; the user merges them (never merged by the command).
  1. Compute the next number from `serve_api/RELEASE` on `origin/main` and
     today's date (no file → `vYYYY.MM.0`). An explicit number may be passed.
  2. Ask whether the vocabulary version changes too; if so, point to README
     "Releasing" for the list of files (the command does not bump it itself).
  3. Branch `release/vYYYY.MM.N` from `origin/acc`; write `RELEASE`; run
     `python scripts/write-sbom.py` (in the pinned container, as the README
     shows); ask before committing; push; PR into `acc`; wait for checks; the
     user merges.
  4. Open the release PR `acc` → `main`; wait for checks; the user merges.
  5. Watch `ci.yml` on the merge commit; confirm stable `/health` on
     `cprmv.open-regels.nl` and `cprmv.open-rules.eu` reports the new
     `release` and build; confirm the image tag `:vYYYY.MM.N` in GHCR and the
     Release SBOM run.
  6. Push `main` to the `gitlab` remote (fast-forward only, as above) and
     confirm the Pages pipeline.
  7. Housekeeping (as the user's global rules define it).
  It never pushes to `acc` or `main`, never merges a pull request, never adds
  attribution lines, and asks before every commit.
- **Docs**: README "Releasing" rewritten around `/bump-release` and the release
  number; `SECURITY-PIPELINE.md` (SBOM naming); the `/health` description in
  README and the deployment design.

## Not in this change

- A first release. This change only adds the mechanism; the first
  `/bump-release` produces `v2026.11.0`.
- Changelog, git tags, GitHub Releases.
