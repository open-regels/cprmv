#!/usr/bin/env python3
"""Writes this repository's release SBOM to docs/sbom/, in CycloneDX.

ICTU recommendation 10 asks for SBOMs of released versions, kept analysable: a
new advisory lands against code that shipped months ago, and answering "was
that version affected?" needs the bill of materials as it was THEN. Workflow
artifacts expire after 90 days on a public repository, so the committed copy is
the durable one; .github/workflows/sbom.yml uploads the same document as an
artifact for a promotion.

Shipped dependencies only: the input is serve_api/requirements.txt, the
hash-locked set the image installs. requirements-dev.txt (pytest, black, ...) is
not in the image and is not in the SBOM; the daily dependency audit walks both.
The container image's own Debian packages are covered by the BuildKit SBOM
attestation that ci.yml attaches to the image, not by this file.

The generator is the CycloneDX tool, `cyclonedx-py` from cyclonedx-bom, pinned
in sbom.yml (and listed in SECURITY-PIPELINE.md). It reads the requirements
file, so no install is needed and the document describes the lockfile rather
than whatever happens to be in a virtualenv. This script only runs it and then
makes its output deterministic, so the same requirements give byte-identical
output:
  - serialNumber and metadata.timestamp are removed (fresh on every run);
  - the tool names components "requirements-L<line>" after the line of the file
    they came from, which moves when a comment is edited, so bom-refs become the
    package URL instead, and the line-quoting description is dropped;
  - components and dependencies are sorted, keys are sorted, the root component
    comes from pyproject.toml.
The requirements file does not record which package needs which, so the graph is
flat: the root depends on every component. The components and their hashes are
the content; do not read the graph as a resolution tree.

CycloneDX 1.6 is the tool's default specification version; it is passed
explicitly so a tool upgrade cannot change it unnoticed.

Usage:
  python scripts/write-sbom.py                  write docs/sbom/cprmv-api-<version>.cdx.json
  python scripts/write-sbom.py --check          exit 1 if that file is missing or stale
  python scripts/write-sbom.py --verify-release exit 1 if missing; warn if stale
  python scripts/write-sbom.py --print-path     print that file's path and exit
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = "serve_api/requirements.txt"
PYPROJECT = "serve_api/pyproject.toml"
SPEC_VERSION = "1.6"
# The project is "cprmv" but the SBOM describes the API image's dependencies,
# and the file name says so.
FILE_PREFIX = "cprmv-api"


def output_path(version: str) -> str:
    """Repository-relative, forward slashes, whatever the platform."""
    return f"docs/sbom/{FILE_PREFIX}-{version}.cdx.json"


def project(root: Path) -> tuple[str, str]:
    meta = tomllib.loads((root / PYPROJECT).read_text(encoding="utf-8"))["project"]
    return meta["name"], meta["version"]


def normalise(raw: dict, name: str, version: str) -> dict:
    """The tool's document, made deterministic. See the module docstring."""
    doc = {k: v for k, v in raw.items() if k != "serialNumber"}
    metadata = {k: v for k, v in raw.get("metadata", {}).items() if k != "timestamp"}
    root_ref = f"{name}@{version}"
    metadata["component"] = {
        "bom-ref": root_ref,
        "name": name,
        "type": "application",
        "version": version,
    }
    doc["metadata"] = metadata

    components = []
    for comp in raw.get("components", []):
        comp = {k: v for k, v in comp.items() if k != "description"}
        comp["bom-ref"] = comp.get("purl") or f"{comp['name']}@{comp['version']}"
        components.append(comp)
    components.sort(key=lambda c: c["bom-ref"])
    refs = [c["bom-ref"] for c in components]
    if len(set(refs)) != len(refs):
        # Two lines for one package@version: the document would be ambiguous.
        raise ValueError("the requirements list a package@version more than once")
    doc["components"] = components
    doc["dependencies"] = [{"ref": root_ref, "dependsOn": refs}] + [
        {"ref": ref} for ref in refs
    ]
    return doc


def serialise(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def run_tool(root: Path) -> dict:
    exe = shutil.which("cyclonedx-py")
    if not exe:
        raise RuntimeError("cyclonedx-py not found; pip install cyclonedx-bom==8.0.1")
    result = subprocess.run(
        [
            exe,
            "requirements",
            str(root / REQUIREMENTS),
            "--sv",
            SPEC_VERSION,
            "--output-reproducible",
            "--of",
            "JSON",
            "-o",
            "-",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"cyclonedx-py failed:\n{result.stderr.strip()}")
    return json.loads(result.stdout)


def generate(root: Path) -> str:
    name, version = project(root)
    return serialise(normalise(run_tool(root), name, version))


def comparable(text: str) -> str:
    """What --check compares: the document without the fields that change when
    its content does not. The file keeps all three, because a CycloneDX document
    is expected to say when, and with what, it was made; but a release SBOM made
    with another tool version must not fail the release pull request when every
    component is identical. A different component list still fails."""
    doc = json.loads(text)
    doc.pop("serialNumber", None)
    meta = doc.get("metadata")
    if meta:
        meta.pop("timestamp", None)
        meta.pop("tools", None)
    return json.dumps(doc, sort_keys=True)


def main(argv: list[str], root: Path = ROOT) -> int:
    _, version = project(root)
    out = output_path(version)

    # --print-path, so the workflow can ask which file belongs to this version
    # without restating the naming rule above.
    if "--print-path" in argv:
        print(out)
        return 0

    generated = generate(root)
    target = root / out

    # --check is strict, and belongs where the release is cut: the document must
    # describe the requirements it was generated from.
    #
    # --verify-release is what a promotion can honestly assert. A promotion
    # carries every commit merged into acc since the release, so its
    # requirements may have moved and the committed SBOM still be the right
    # document for the version being released. A missing SBOM is a failure;
    # drift is a warning that says which.
    strict = "--check" in argv
    verify = "--verify-release" in argv
    if strict or verify:
        if not target.exists():
            print(
                f"::error::{out} is missing. Run: python scripts/write-sbom.py",
                file=sys.stderr,
            )
            return 1
        drifted = comparable(target.read_text(encoding="utf-8")) != comparable(
            generated
        )
        if drifted and strict:
            print(
                f"::error::{out} does not match the current requirements. "
                "Run: python scripts/write-sbom.py",
                file=sys.stderr,
            )
            return 1
        if drifted:
            print(
                f"::warning::{out} exists but no longer matches this tree's "
                "requirements. Expected on a promotion, which carries commits made "
                "after the release; investigate if this is the release commit itself."
            )
            return 0
        print(f"{out} matches the requirements")
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(generated)
    count = len(json.loads(generated)["components"])
    print(f"{out}: {count} components (shipped dependencies of cprmv-api {version})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (RuntimeError, ValueError, OSError) as err:
        print(f"::error::write-sbom: {err}", file=sys.stderr)
        sys.exit(1)
