# CPRMV release SBOM

Status: approved 27 November 2026 (short design)

## Intent

Adopt the release-SBOM practice of the other IOU repositories
(linked-data-explorer, ttl-editor, ronl-business-api: `.github/workflows/sbom.yml`
with `scripts/write-sbom.mjs`), so that for every released version of CPRMV the
question "was that version affected by this advisory?" can be answered later
(ICTU recommendation 10). Workflow artifacts expire after 90 days on a public
repository, so the committed copy is the durable one.

## Design

- **The application SBOM, committed per release.** `scripts/write-sbom.py`
  (stdlib Python plus the pinned CycloneDX tool `cyclonedx-bom==8.0.1`, the newest
  release at least 14 days old) writes `docs/sbom/cprmv-api-<version>.cdx.json`
  in CycloneDX JSON from `serve_api/requirements.txt`: the shipped, hash-locked
  dependencies only (development dependencies are not in the image; the daily
  dependency audit covers both). The version is read from
  `serve_api/pyproject.toml`. No install is needed: the tool reads the
  requirements file.
- **Deterministic output.** Fields that change on every run (the serial number,
  the metadata timestamp, tool version noise if any) are removed or fixed, and
  components are sorted, so the same requirements give byte-identical output.
- **Modes**, as in the siblings: no argument writes the file; `--check` exits 1
  when the file is missing or differs from a fresh generation; `--verify-release`
  exits 1 when missing and warns when stale; `--print-path` prints the path.
- **`.github/workflows/sbom.yml` ("Release SBOM")**, the siblings' shape: on push
  to `main` the released version must have its SBOM; on a pull request that
  changes the SBOM file it must match the requirements exactly (a release
  bump); the script's own tests run every time; the document is uploaded as a
  90-day artifact. Pins as elsewhere (checkout, setup-python 3.14,
  upload-artifact). Not a required check, as in the siblings.
- **The image SBOM.** CPRMV also ships a container image, so the `publish` job's
  push build gets `sbom: true` (BuildKit's SBOM attestation, attached to the
  image in GHCR next to the provenance). It covers the Debian packages the
  application SBOM does not. Nothing to maintain.
- **0.4.3** gets its SBOM in this change, from the current requirements (what
  stable runs since #10), so the `main` check is green from the next release.
- **Docs:** `SECURITY-PIPELINE.md` (checks table, pin register: cyclonedx-bom),
  `README.md` release steps (regenerate the SBOM after the version bump).
- **Renovate:** the `cyclonedx-bom==` pin in the workflow is a plain `pip install`
  line; it is listed in the pin register and updated by hand like semgrep's.

## Not in this change

- SBOMs for versions before 0.4.3.
- Signing the committed SBOM; the image attestation is signed by GitHub.
