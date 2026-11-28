"""Shared parsing for the dependency register gate (scripts/dependency-gate.py).

The npm repositories run a CI check that blocks a new direct dependency until a
committed register entry agrees with registry and GitHub evidence, and blocks
pins younger than the cooldown. This is its Python counterpart for
serve_api/. Everything that reads a file or a string lives here, with no
network and no git, so the gate and the cooldown script share one reading of
requirements.txt, pyproject.toml, the register and the policy, and the tests
need no fixtures beyond strings.

Standard library only: the CI job runs it before anything is installed.

Groups play the part npm manifests play. `runtime` is [project.dependencies];
every [project.optional-dependencies] extra (`dev`, `tools`) is a group of its
own. The register's `manifest` field holds the group name. Names are compared
in their PEP 503 form, so `Ruamel.YAML` and `ruamel-yaml` are one package.
"""

import json
import re
import tomllib
from dataclasses import dataclass, field

MIN_WHY = 40
CRITERIA = (
    "maintained",
    "maintainers",
    "licence",
    "releasePolicy",
    "footprint",
    "needed",
)


class InputError(Exception):
    """A file the gate reads is malformed. The gate exits 2 on it, never 0 or 1:
    a gate that cannot read its input must not look like a verdict."""


def normalise(name: str) -> str:
    """PEP 503: lower case, runs of `-`, `_` and `.` become one `-`."""
    return re.sub(r"[-_.]+", "-", name).lower()


def code(s: str) -> str:
    """A markdown code span that cannot break its line or its table cell:
    backticks inside become `'`, newlines become spaces."""
    flat = re.sub(r"[\r\n]+", " ", str(s)).replace("`", "'")
    return f"`{flat}`"


# --- requirements.txt ------------------------------------------------------


@dataclass
class Pin:
    name: str
    version: str
    hashes: list[str] = field(default_factory=list)
    source: str | None = None


_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*==\s*([^\s;]+)")
_HASH = re.compile(r"--hash=(\S+)")


def _logical_lines(text: str) -> list[str]:
    """Lines with `\\` continuations joined and comments dropped. pip-compile
    writes `# via` blocks on their own lines, so a whole-line comment is the
    only kind that needs handling; an inline ` #` is cut as well."""
    out: list[str] = []
    buf = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not buf and (not line or line.startswith("#")):
            continue
        if line.startswith("#"):
            # a comment inside a continuation ends nothing; skip it
            continue
        line = re.sub(r"\s+#.*$", "", line)
        if line.endswith("\\"):
            buf += line[:-1].rstrip() + " "
            continue
        out.append((buf + line).strip())
        buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def parse_requirements(text: str) -> dict[str, Pin]:
    """The hash-locked pins of a pip-compile requirements file, keyed by the
    normalised name. A line that is not `name==version` with at least one
    `--hash` is an InputError: an unpinned or unhashed line is not locked."""
    pins: dict[str, Pin] = {}
    for line in _logical_lines(text):
        if line.startswith("-"):
            # --index-url, --extra-index-url and the like carry no pin
            continue
        m = _PIN.match(line)
        if not m:
            raise InputError(f"requirements: {code(line.split()[0])} is not pinned with ==")
        name, version = m.group(1), m.group(2)
        hashes = _HASH.findall(line)
        if not hashes:
            raise InputError(f"requirements: {code(name)} has no --hash")
        source = None
        index = re.search(r"--(?:extra-)?index-url[= ](\S+)", line)
        if index:
            source = index.group(1)
        pins[normalise(name)] = Pin(normalise(name), version, hashes, source)
    return pins


# --- pyproject.toml --------------------------------------------------------

_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _names(requirements: list[str]) -> set[str]:
    names = set()
    for req in requirements:
        m = _REQ_NAME.match(req)
        if not m:
            raise InputError(f"pyproject.toml: cannot read a package name from {code(req)}")
        names.add(normalise(m.group(1)))
    return names


def direct_groups(pyproject_text: str) -> dict[str, set[str]]:
    """{'runtime': {...}, 'dev': {...}, ...}: the direct dependencies per group,
    names normalised, extras and version specifiers dropped. An absent table
    gives no group."""
    try:
        doc = tomllib.loads(pyproject_text)
    except tomllib.TOMLDecodeError as err:
        raise InputError(f"pyproject.toml is not valid TOML: {err}") from err
    project = doc.get("project", {})
    groups: dict[str, set[str]] = {}
    if "dependencies" in project:
        groups["runtime"] = _names(project["dependencies"])
    for extra, reqs in project.get("optional-dependencies", {}).items():
        groups[extra] = _names(reqs)
    return groups


def new_direct(
    base_groups: dict[str, set[str]], head_groups: dict[str, set[str]]
) -> list[tuple[str, str]]:
    """(name, group) pairs in head and not in the same group of base, sorted.
    Moving a package between groups is new for the group it moved to: it
    changes where the package runs."""
    out = []
    for group, names in head_groups.items():
        for name in names - base_groups.get(group, set()):
            out.append((name, group))
    return sorted(out, key=lambda p: (p[1], p[0]))


# --- register and policy ---------------------------------------------------


@dataclass
class Register:
    dependencies: list[dict]
    cooldown_overrides: list[dict]


@dataclass
class Policy:
    min_release_age_days: int
    allow_licenses: list[str]


def _is_obj(v) -> bool:
    return isinstance(v, dict)


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _parse_entry(raw, index: int, label: str) -> dict:
    at = f'"{raw["name"]}"' if _is_obj(raw) and raw.get("name") else f"#{index + 1}"

    def fail(what: str):
        raise InputError(f"{label}: entry {at}: {what}")

    if not _is_obj(raw):
        fail("not an object")
    for key in ("name", "manifest"):
        if not isinstance(raw.get(key), str) or not raw[key]:
            fail(f"{key} missing")
    if raw.get("status") not in ("assessed", "override"):
        fail('status must be "assessed" or "override"')
    if "assessed" in raw:
        a = raw["assessed"]
        if not _is_obj(a) or not isinstance(a.get("version"), str) or not a["version"]:
            fail("assessed.version missing")
    elif raw["status"] == "assessed":
        fail("assessed missing")
    if "followUp" in raw and not _is_int(raw["followUp"]):
        fail("followUp must be an integer")
    if "licence" in raw and (not isinstance(raw["licence"], str) or not raw["licence"]):
        fail("licence must be an SPDX string")
    if "repository" in raw:
        repo = raw["repository"]
        if repo is None:
            why = raw.get("repositoryWhy")
            if not isinstance(why, str) or len(why.strip()) < MIN_WHY:
                fail(f"repository null needs a repositoryWhy of at least {MIN_WHY} characters")
        elif not isinstance(repo, str) or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
            fail("repository must be owner/name or null")
    if raw["status"] == "assessed":
        if not _is_obj(raw.get("criteria")):
            fail("criteria missing")
        for name in CRITERIA:
            c = raw["criteria"].get(name)
            if not _is_obj(c) or not isinstance(c.get("holds"), bool):
                fail(f"criteria.{name}.holds must be true or false")
            if "why" in c and not isinstance(c["why"], str):
                fail(f"criteria.{name}.why must be text")
        if raw.get("outcome") not in ("keep", "replace"):
            fail('outcome must be "keep" or "replace"')
        if raw["outcome"] == "replace" and "followUp" not in raw:
            fail("outcome replace needs an integer followUp")
    else:
        o = raw.get("override")
        if not _is_obj(o) or not isinstance(o.get("reason"), str) or not o["reason"]:
            fail("override.reason missing")
        if not _is_int(o.get("issue")):
            fail("override.issue must be an integer")
    return raw


def parse_register(text: str, label: str = "dependency-register.json") -> Register:
    """Parse the register; any shape error names the entry and the field."""
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as err:
        raise InputError(f"{label} is not valid JSON: {err}") from err
    if not _is_obj(doc) or not isinstance(doc.get("dependencies"), list):
        raise InputError(f'{label}: "dependencies" must be a list')
    seen: set[tuple[str, str]] = set()
    dependencies = []
    for i, raw in enumerate(doc["dependencies"]):
        entry = _parse_entry(raw, i, label)
        key = (normalise(entry["name"]), entry["manifest"])
        if key in seen:
            raise InputError(f'{label}: duplicate entry for "{entry["name"]}" in "{entry["manifest"]}"')
        seen.add(key)
        dependencies.append(entry)
    overrides = doc.get("cooldownOverrides", [])
    if not isinstance(overrides, list):
        raise InputError(f'{label}: "cooldownOverrides" must be a list')
    for i, o in enumerate(overrides):
        if (
            not _is_obj(o)
            or not isinstance(o.get("package"), str)
            or not isinstance(o.get("version"), str)
            or not isinstance(o.get("reason"), str)
            or not o["reason"]
            or not _is_int(o.get("issue"))
        ):
            raise InputError(
                f"{label}: cooldownOverrides #{i + 1} needs package, version, reason and an integer issue"
            )
    return Register(dependencies, overrides)


def parse_policy(text: str, label: str = "lockfile-review.json") -> Policy:
    """Parse the policy file: the cooldown in days and the licence allow-list."""
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as err:
        raise InputError(f"{label} is not valid JSON: {err}") from err
    if not _is_obj(doc):
        raise InputError(f"{label}: not an object")
    days = doc.get("minReleaseAgeDays")
    if not _is_int(days) or days < 0:
        raise InputError(f"{label}: minReleaseAgeDays must be a non-negative integer")
    allow = doc.get("allowLicenses")
    if not isinstance(allow, list) or not all(isinstance(x, str) for x in allow):
        raise InputError(f"{label}: allowLicenses must be a list of SPDX strings")
    return Policy(days, allow)
