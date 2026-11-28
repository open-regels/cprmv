#!/usr/bin/env python3
"""requirements_review.py — what a change to the requirements files contains.

A dependency pull request shows its reviewer the direct change. What moves is
`serve_api/requirements.txt` and `requirements-dev.txt`, which pip-compile
writes and nobody reads: a new transitive pin, a downgrade, a pin that lost
its hashes, a package from somewhere other than PyPI. This compares the base
and head copies of both files as data and says which of those happened, the
Python counterpart of linked-data-explorer's scripts/lockfile-diff.mjs (spec
§4.1, docs/superpowers/specs/2026-11-28-dependency-register-gate-design.md).

Blocking, over the whole head files (a bad line fails however it arrived):

- a pin without `--hash` (`hashes`), or a requirement that is not `==` (`pin`);
- anything that does not come from PyPI (`source`): an `--index-url`/`-i`,
  `--extra-index-url`, `--find-links`/`-f`, `--trusted-host`, `-e`/
  `--editable`, `-r`/`-c` line, a `name @ url` direct reference, or a bare URL
  or path. pip-compile writes index options on lines of their own, so they are
  found here, not on the pin.

Every added pin is looked up on PyPI (the version endpoint): its licence (the
precedence of pypi_evidence.resolve_licence) and whether a wheel exists for
the image. A licence off the allow-list, none resolvable, or no wheel for the
image is listed for the reviewer, never blocking.

Usage:
  python scripts/requirements_review.py <base-dir> <head-dir>
    [--config serve_api/lockfile-review.json] [--out review.md]
Each dir holds requirements.txt and requirements-dev.txt (a serve_api/ layout).

Exit: 0 nothing blocking, 1 a blocking finding, 2 a file, the config or PyPI
could not be used, which must never read as clean.

Standard library only.
"""

import re
import sys
import time
import traceback
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_common as G  # noqa: E402
import pypi_evidence as E  # noqa: E402

FILES = ("requirements.txt", "requirements-dev.txt")
TITLE = "Requirements diff"


# --- scanning --------------------------------------------------------------


@dataclass
class Problem:
    rule: str
    file: str
    key: str
    detail: str


@dataclass
class Scan:
    pins: dict[str, G.Pin] = field(default_factory=dict)
    problems: list[Problem] = field(default_factory=list)


# Option lines that change where pip installs from, or bring in a file this
# review does not read. The value is what the finding says.
_SOURCE_OPTIONS = {
    "--index-url": "an index other than PyPI",
    "-i": "an index other than PyPI",
    "--extra-index-url": "an extra index",
    "--find-links": "a find-links location",
    "-f": "a find-links location",
    "--trusted-host": "a host trusted without TLS checks",
    "--editable": "an editable install",
    "-e": "an editable install",
    "--requirement": "another requirements file, which this review does not read",
    "-r": "another requirements file, which this review does not read",
    "--constraint": "a constraints file, which this review does not read",
    "-c": "a constraints file, which this review does not read",
}
_DIRECT_REF = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*@\s*(\S+)")
_ARCHIVE = re.compile(r"\.(?:whl|zip|tar\.gz|tar\.bz2|tgz)$", re.I)


def _option(token: str) -> str:
    if token.startswith("--"):
        return token.split("=", 1)[0]
    return token[:2]


def scan_requirements(text: str, file: str) -> Scan:
    """Every `name==version` pin of a requirements file, keyed by its
    normalised name, with or without hashes, and every line that breaks the
    review's rules. Never raises on content: a bad line is a finding (exit 1),
    not an unreadable file (exit 2)."""
    scan = Scan()
    for line in G._logical_lines(text):
        first = line.split()[0]
        if first.startswith("-"):
            what = _SOURCE_OPTIONS.get(_option(first))
            if what:
                scan.problems.append(Problem("source", file, line, f"installs from {what}"))
            continue
        ref = _DIRECT_REF.match(line)
        if ref:
            name = G.normalise(ref.group(1))
            scan.problems.append(Problem("source", file, name, f"direct reference to {G.code(ref.group(2))}"))
            continue
        if "://" in first or first.startswith((".", "/", "~")) or _ARCHIVE.search(first):
            scan.problems.append(Problem("source", file, first, "a URL or path, not a PyPI pin"))
            continue
        m = G._PIN.match(line)
        if not m:
            scan.problems.append(Problem("pin", file, first, "not pinned with =="))
            continue
        name = G.normalise(m.group(1))
        hashes = G._HASH.findall(line)
        if not hashes:
            scan.problems.append(Problem("hashes", file, name, "no --hash"))
        scan.pins[name] = G.Pin(name, m.group(2), hashes)
    return scan


# --- versions --------------------------------------------------------------

_VERSION = re.compile(
    r"^(?:(\d+)!)?(\d+(?:\.\d+)*)(?:[-_.]?(a|b|c|rc|alpha|beta|pre|preview)[-_.]?(\d*))?"
    r"(?:[-_.]?(?:post|rev|r)[-_.]?(\d*))?(?:[-_.]?dev[-_.]?(\d*))?(?:\+.*)?$",
    re.I,
)
_PRE = {"a": 0, "alpha": 0, "b": 1, "beta": 1, "c": 2, "rc": 2, "pre": 2, "preview": 2}


def _version_key(v: str):
    m = _VERSION.match(v.strip().lower().lstrip("v"))
    if not m:
        return None
    epoch, release, pre, pre_n, post, dev = m.groups()
    parts = [int(x) for x in release.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    inf = float("inf")
    if pre:
        pre_key = (0, _PRE[pre], int(pre_n or 0))
    elif post is None and dev is not None:
        pre_key = (-1,)  # 1.0.dev1 sorts before 1.0a1
    else:
        pre_key = (1,)
    post_key = int(post or 0) if post is not None else -1
    dev_key = int(dev or 0) if dev is not None else inf
    return (int(epoch or 0), tuple(parts), pre_key, post_key, dev_key)


def compare_versions(a: str, b: str) -> int:
    """PEP 440 order for the forms pip-compile writes; text order for
    anything else."""
    ka, kb = _version_key(a), _version_key(b)
    if ka is None or kb is None:
        ka, kb = a, b
    return (ka > kb) - (ka < kb)


# --- the diff --------------------------------------------------------------


@dataclass
class Update:
    name: str
    old: str
    new: str
    downgrade: bool


@dataclass
class Diff:
    added: list[G.Pin]
    removed: list[G.Pin]
    updated: list[Update]

    @property
    def downgrades(self) -> list[Update]:
        return [u for u in self.updated if u.downgrade]


def diff_pins(base: dict[str, G.Pin], head: dict[str, G.Pin]) -> Diff:
    added = [head[n] for n in sorted(head) if n not in base]
    removed = [base[n] for n in sorted(base) if n not in head]
    updated = [
        Update(n, base[n].version, head[n].version, compare_versions(head[n].version, base[n].version) < 0)
        for n in sorted(head)
        if n in base and base[n].version != head[n].version
    ]
    return Diff(added, removed, updated)


def read_text(directory: Path, name: str, side: str) -> str:
    path = Path(directory) / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as err:
        raise G.InputError(f"cannot read {name} in {side} ({path}): {err.strerror or err}") from err


def scan_dir(directory: Path, side: str) -> dict[str, Scan]:
    return {f: scan_requirements(read_text(directory, f, side), f) for f in FILES}


# --- PyPI lookups of added pins --------------------------------------------


@dataclass
class PinFacts:
    licence: str | None
    licence_source: str | None
    wheel: str  # what the report says about wheels
    builds_from_source: bool


def pin_facts(name: str, version: str, *, fetch, sleep) -> PinFacts:
    pkg = urllib.parse.quote(name, safe="")
    ver = urllib.parse.quote(version, safe="")
    try:
        doc = E.fetch_json(f"{E.PYPI}/pypi/{pkg}/{ver}/json", fetch=fetch, sleep=sleep)
    except E.FetchError as err:
        raise E.FetchError(f"PyPI {name} {version}: {err}", err.status, err.url) from err
    licence, source = E.resolve_licence(doc.get("info") or {})
    usable = sorted(
        f["filename"]
        for f in doc.get("urls") or []
        if isinstance(f, dict) and f.get("filename") and not f.get("yanked")
    )
    target = next((f for f in usable if E.target_compatible(f)), None)
    if any(E.is_pure(f) for f in usable):
        wheel = "pure wheel"
    elif target:
        wheel = f"wheel {G.code(target)}"
    else:
        wheel = "no wheel for the image: builds from source"
    return PinFacts(licence, source, wheel, target is None)


# --- the report ------------------------------------------------------------


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _details(summary: str, lines: list[str]) -> list[str]:
    if not lines:
        return []
    return ["<details>", f"<summary>{summary}</summary>", "", *lines, "", "</details>", ""]


def _section(title: str, lines: list[str]) -> list[str]:
    return [f"##### {title}", "", *lines, ""] if lines else []


def _merge(per_file: dict[str, list], key) -> list[tuple[object, list[str]]]:
    """One line per change across both files: runtime pins sit in both."""
    merged: dict = {}
    for file, items in per_file.items():
        for item in items:
            merged.setdefault(key(item), (item, []))[1].append(file)
    return sorted(merged.values(), key=lambda x: key(x[0]))


def render(problems: list[Problem], diffs: dict[str, Diff], facts: dict, allow: list[str]) -> str:
    verdict = (
        f"**✗ {_plural(len(problems), 'blocking finding')}** — the check fails."
        if problems
        else "**✓ No blocking findings.**"
    )
    counts = [
        f"- {G.code(f)}: {len(d.added)} added · {len(d.removed)} removed · "
        f"{len(d.updated)} updated · {len(d.downgrades)} downgraded"
        for f, d in diffs.items()
    ]
    added = _merge({f: d.added for f, d in diffs.items()}, lambda p: (p.name, p.version))
    removed = _merge({f: d.removed for f, d in diffs.items()}, lambda p: (p.name, p.version))
    updated = _merge({f: d.updated for f, d in diffs.items()}, lambda u: (u.name, u.old, u.new))

    def where(files):
        return ", ".join(files)

    def licence_text(x: PinFacts):
        return f"{G.code(x.licence)} ({x.licence_source})" if x.licence else "_none resolvable_"

    off_list, from_source, added_lines = [], [], []
    for pin, files in added:
        x = facts[(pin.name, pin.version)]
        head = f"- {G.code(pin.name)} {G.code(pin.version)}"
        if x.licence is None or not E.licence_allowed(x.licence, allow):
            off_list.append(f"{head} — {licence_text(x)} — {where(files)}")
        if x.builds_from_source:
            from_source.append(f"{head} — {where(files)}")
        added_lines.append(f"{head} — {where(files)} — {licence_text(x)} — {x.wheel}")

    def update_line(u, files):
        return f"- {G.code(u.name)} {G.code(u.old)} → {G.code(u.new)} — {where(files)}" + (
            " — **downgrade**" if u.downgrade else ""
        )

    lines = [
        f"#### {TITLE}",
        "",
        verdict,
        "",
        *counts,
        "",
        *_section("Blocking", [f"- **{p.rule}** {G.code(p.file)} {G.code(p.key)}: {p.detail}" for p in problems]),
        *_section(
            "Downgrades",
            [f"- {G.code(u.name)} {G.code(u.old)} → {G.code(u.new)} — {where(f)}" for u, f in updated if u.downgrade],
        ),
        *_section("New pins with a licence not on the allow-list", off_list),
        *_section("New pins without a wheel for the image (CPython 3.14, manylinux x86_64)", from_source),
        *_details(f"Added ({len(added)})", added_lines),
        *_details(
            f"Removed ({len(removed)})", [f"- {G.code(p.name)} {G.code(p.version)} — {where(f)}" for p, f in removed]
        ),
        *_details(f"Updated ({len(updated)})", [update_line(u, f) for u, f in updated]),
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_failure(message: str) -> str:
    return "\n".join(
        [f"#### {TITLE}", "", "**✗ The requirements review could not run** — the check fails.", "", G.code(message), ""]
    )


# --- the command line ------------------------------------------------------


def option(args: list[str], name: str) -> str | None:
    if name in args:
        i = args.index(name)
        if i + 1 >= len(args):
            raise G.InputError(f"{name} needs a value")
        return args[i + 1]
    return None


def positionals(args: list[str]) -> list[str]:
    return [a for i, a in enumerate(args) if not a.startswith("--") and not (i > 0 and args[i - 1].startswith("--"))]


def run(args: list[str], *, fetch=E.urllib_fetch, sleep=time.sleep) -> tuple[int, str]:
    pos = positionals(args)
    if len(pos) != 2:
        raise G.InputError("usage: requirements_review.py <base-dir> <head-dir> [--config file] [--out file]")
    base_dir, head_dir = (Path(p) for p in pos)
    config = Path(option(args, "--config") or head_dir / "lockfile-review.json")
    policy = G.parse_policy(read_text(config.parent, config.name, "config"), str(config))
    base, head = scan_dir(base_dir, "base"), scan_dir(head_dir, "head")
    diffs = {f: diff_pins(base[f].pins, head[f].pins) for f in FILES}
    problems = [p for f in FILES for p in head[f].problems]
    facts = {}
    for f in FILES:
        for pin in diffs[f].added:
            key = (pin.name, pin.version)
            if key not in facts:
                facts[key] = pin_facts(pin.name, pin.version, fetch=fetch, sleep=sleep)
    report = render(problems, diffs, facts, policy.allow_licenses)
    return (1 if problems else 0), report


def describe(err: BaseException) -> str:
    if isinstance(err, (G.InputError, E.FetchError)):
        return str(err)
    return f"{type(err).__name__}: {err}"


def main(argv: list[str], *, fetch=E.urllib_fetch, sleep=time.sleep) -> int:
    out = None
    try:
        out = option(argv, "--out")
        status, report = run(argv, fetch=fetch, sleep=sleep)
    except Exception as err:  # anything unexpected is exit 2 too: a crash must not read as clean
        if not isinstance(err, (G.InputError, E.FetchError)):
            traceback.print_exc()
        print(f"requirements_review: {describe(err)}", file=sys.stderr)
        report, status = render_failure(describe(err)), 2
    if out:
        Path(out).write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
