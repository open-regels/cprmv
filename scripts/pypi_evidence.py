"""PyPI and GitHub evidence for the dependency register gate, and the signals
the gate draws from it (spec §4.4, docs/superpowers/specs/
2026-11-28-dependency-register-gate-design.md).

For one package at its locked version this asks:

- the JSON API, project endpoint (`/pypi/<name>/json`): every release's files
  with upload times and yanked flags (the last release, the cooldown's upload
  time of any version) and `ownership` (PEP 752);
- the JSON API, version endpoint (`/pypi/<name>/<version>/json`): the locked
  version's licence fields, `project_urls`, its files and its yanked flag;
- the Simple API in JSON (`/simple/<name>/`): `project-status` (PEP 792) and
  each file's `provenance` (PEP 740), followed for one file to the Integrity
  API for the trusted publisher;
- the GitHub API for the repository: archived, and whether an organisation
  owns it.

`signals()` turns that into the npm gate's shape (signalsFor in
dependency-gate.mjs): per criterion the reason it cannot hold, or None, plus
`fatal` (excused only by `outcome: replace` with an open follow-up, which the
gate checks) and `required` (register fields the evidence makes necessary;
always blocking).

Standard library only; every fetch goes through an injectable `fetch(url,
headers, timeout) -> (status, headers, body)`, so the tests need no network.
A GitHub repository that answers 404 or 410 is evidence; any other failure
raises FetchError, on which the gate exits 2.
"""

import email.utils
import http.client
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_common import code, normalise  # noqa: E402

PYPI = "https://pypi.org"
GITHUB_API = "https://api.github.com"
SIMPLE_JSON = "application/vnd.pypi.simple.v1+json"
USER_AGENT = "dependency-gate (python urllib)"
RETRY_AFTER_CAP = 60
BACKOFF = (2, 5)

# The image the service runs in: python:3.14-bookworm on amd64. Bookworm ships
# glibc 2.36, so a manylinux wheel that needs a newer glibc does not install.
TARGET_MINOR = 14
TARGET_GLIBC = (2, 36)
LEGACY_MANYLINUX = {"manylinux1": (2, 5), "manylinux2010": (2, 12), "manylinux2014": (2, 17)}


class FetchError(Exception):
    """A registry or API could not be read. `status` is the last HTTP status,
    or None when there was no answer (timeout, connection error)."""

    def __init__(self, message: str, status: int | None = None, url: str | None = None):
        super().__init__(message)
        self.status = status
        self.url = url


# --- fetching --------------------------------------------------------------


def urllib_fetch(url: str, headers: dict, timeout: float) -> tuple[int, dict, bytes]:
    """The default fetch: one GET. An HTTP error status is an answer, not an
    exception; a timeout or connection failure raises."""
    if not url.startswith("https://"):
        raise FetchError(f"refusing a non-https URL: {url}", url=url)
    req = urllib.request.Request(url, headers=headers)
    # The URL is https (checked above) and built from fixed API roots with the
    # package name and version percent-encoded, so no file:// or custom scheme
    # can reach urlopen.
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, dict(res.headers.items()), res.read()
    except urllib.error.HTTPError as err:
        return err.code, dict((err.headers or {}).items()), err.read() or b""


def retry_after(value, now: float | None = None) -> float | None:
    """Seconds to wait from a Retry-After header (seconds or an HTTP date),
    capped at 60; None when absent or unreadable."""
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    try:
        seconds = float(text)
    except ValueError:
        try:
            when = email.utils.parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
        if when is None:
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        seconds = when.timestamp() - (time.time() if now is None else now)
    if not math.isfinite(seconds):
        # "nan" and "inf" parse as floats; neither is a wait.
        return None
    return min(max(seconds, 0), RETRY_AFTER_CAP)


def fetch_json(
    url: str,
    *,
    fetch=urllib_fetch,
    headers: dict | None = None,
    retries: int = 3,
    timeout: float = 30,
    sleep=time.sleep,
    backoff=BACKOFF,
    expect: type | None = dict,
):
    """GET and parse JSON. A 429 or 5xx, a timeout or a dropped connection is
    retried after 2 s and then 5 s, or after the server's Retry-After (at most
    60 s); `retries` attempts in all, each with its own timeout. Any other
    status fails at once, as does a body that is not JSON or not of the
    `expect`ed type (a dict by default; None accepts any JSON). Everything
    that goes wrong ends as a FetchError carrying the last status."""
    hdrs = {"Accept": "application/json", "User-Agent": USER_AGENT, **(headers or {})}
    host = urllib.parse.urlsplit(url).netloc
    last: FetchError | None = None
    wait = None
    for attempt in range(1, retries + 1):
        if attempt > 1:
            sleep(wait if wait is not None else backoff[min(attempt - 2, len(backoff) - 1)])
        wait = None
        try:
            status, res_headers, body = fetch(url, hdrs, timeout)
        except (OSError, http.client.HTTPException) as err:
            # OSError covers timeouts and URLError; HTTPException a dropped
            # or garbled response (IncompleteRead, RemoteDisconnected).
            # A FetchError (refused URL) is neither and propagates.
            last = FetchError(f"{host}: {err}", None, url)
            continue
        if 200 <= status < 300:
            try:
                doc = json.loads(body)
            except (ValueError, UnicodeDecodeError) as err:
                raise FetchError(f"{host} answered {status} with no JSON: {err}", status, url) from err
            if expect is not None and not isinstance(doc, expect):
                raise FetchError(
                    f"{host} answered {status} with JSON {type(doc).__name__}, not {expect.__name__}", status, url
                )
            return doc
        last = FetchError(f"{host} answered {status}", status, url)
        if status != 429 and status < 500:
            raise last
        lower = {k.lower(): v for k, v in (res_headers or {}).items()}
        wait = retry_after(lower.get("retry-after"))
    assert last is not None
    raise last


# --- licences --------------------------------------------------------------

# SPDX licence identifiers (spdx.org/licenses) the gate recognises: the ones a
# Python package plausibly declares. An identifier outside this list is not
# taken as SPDX, so prose such as "BSD" or "MIT License" never passes for an
# expression; LicenseRef- identifiers always parse.
SPDX_IDS = {
    i.lower(): i
    for i in (
        "0BSD AFL-3.0 AGPL-3.0 AGPL-3.0-only AGPL-3.0-or-later Apache-1.1 Apache-2.0 "
        "APSL-2.0 Artistic-2.0 BlueOak-1.0.0 BSD-1-Clause BSD-2-Clause BSD-2-Clause-Patent "
        "BSD-3-Clause BSD-3-Clause-Clear BSD-4-Clause BSL-1.0 CC-BY-3.0 CC-BY-4.0 "
        "CC-BY-SA-4.0 CC0-1.0 CDDL-1.0 CNRI-Python curl ECL-2.0 EPL-1.0 EPL-2.0 EUPL-1.2 "
        "GPL-2.0 GPL-2.0-only GPL-2.0-or-later GPL-3.0 GPL-3.0-only GPL-3.0-or-later HPND "
        "ISC LGPL-2.0-only LGPL-2.0-or-later LGPL-2.1 LGPL-2.1-only LGPL-2.1-or-later "
        "LGPL-3.0 LGPL-3.0-only LGPL-3.0-or-later MIT MIT-0 MIT-CMU MPL-1.1 MPL-2.0 "
        "MS-PL NCSA OFL-1.1 OpenSSL PostgreSQL PSF-2.0 Python-2.0 Python-2.0.1 Unicode-3.0 "
        "Unicode-DFS-2016 Unlicense UPL-1.0 W3C WTFPL X11 Zlib ZPL-2.1"
    ).split()
}
SPDX_EXCEPTIONS = {
    i.lower(): i
    for i in (
        "Autoconf-exception-3.0 Bison-exception-2.2 Classpath-exception-2.0 "
        "GCC-exception-3.1 LLVM-exception OpenSSL-exception Qt-LGPL-exception-1.1"
    ).split()
}
_REF = re.compile(r"^(?:DocumentRef-[A-Za-z0-9.-]+:)?LicenseRef-[A-Za-z0-9.-]+$")

# Trove classifiers that name exactly one SPDX licence. "BSD License" is not
# here on purpose: it covers 2-, 3- and 4-clause BSD alike, so the entry's
# `licence` field has to say which.
CLASSIFIER_SPDX = {
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: MIT No Attribution License (MIT-0)": "MIT-0",
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: ISC License (ISCL)": "ISC",
    "License :: OSI Approved :: Python Software Foundation License": "PSF-2.0",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "License :: OSI Approved :: The Unlicense (Unlicense)": "Unlicense",
    "License :: OSI Approved :: Zero-Clause BSD (0BSD)": "0BSD",
    "License :: OSI Approved :: Blue Oak Model License (BlueOak-1.0.0)": "BlueOak-1.0.0",
    "License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication": "CC0-1.0",
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"\(|\)|[^\s()]+", text)


def _parse_spdx(text):
    """(tree, canonical text) for an SPDX expression, or None. Tree nodes:
    ('id', id), ('with', id, exception), ('and', [..]), ('or', [..])."""
    if not isinstance(text, str) or not text.strip():
        return None
    toks = _tokens(text)
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else None

    def take():
        nonlocal pos
        pos += 1
        return toks[pos - 1]

    def licence_id(tok):
        if tok is None:
            return None
        plus = tok.endswith("+") and len(tok) > 1
        base = tok[:-1] if plus else tok
        if _REF.match(base):
            return base + ("+" if plus else "")
        known = SPDX_IDS.get(base.lower())
        return known + ("+" if plus else "") if known else None

    def atom():
        tok = peek()
        if tok == "(":
            take()
            node = expr()
            if node is None or peek() != ")":
                return None
            take()
            return ("group", node)
        ident = licence_id(tok)
        if ident is None:
            return None
        take()
        if (peek() or "").upper() == "WITH":
            take()
            exc = SPDX_EXCEPTIONS.get((peek() or "").lower())
            if exc is None:
                return None
            take()
            return ("with", ident, exc)
        return ("id", ident)

    def chain(sub, op):
        first = sub()
        if first is None:
            return None
        items = [first]
        while (peek() or "").upper() == op:
            take()
            nxt = sub()
            if nxt is None:
                return None
            items.append(nxt)
        return items[0] if len(items) == 1 else (op.lower(), items)

    def conj():
        return chain(atom, "AND")

    def expr():
        return chain(conj, "OR")

    tree = expr()
    if tree is None or pos != len(toks):
        return None
    return tree, _render(tree)


def _render(node) -> str:
    kind = node[0]
    if kind == "id":
        return node[1]
    if kind == "with":
        return f"{node[1]} WITH {node[2]}"
    if kind == "group":
        return f"({_render(node[1])})"
    return f" {kind.upper()} ".join(_render(n) for n in node[1])


def is_spdx(text) -> bool:
    return _parse_spdx(text) is not None


def canonical_spdx(text) -> str | None:
    parsed = _parse_spdx(text)
    return parsed[1] if parsed else None


_ID_SHAPED = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+-]*$")
_OPERATORS = {"AND", "OR", "WITH"}


def unknown_ids(text) -> list[str]:
    """The identifiers that keep `text` from parsing only because SPDX_IDS
    does not list them: id-shaped tokens outside the list, returned when the
    text parses once they are replaced by a known id. Empty when the text
    parses already, or would not parse anyway (prose such as "MIT License")."""
    if not isinstance(text, str) or is_spdx(text):
        return []
    toks = _tokens(text)
    unknown = [
        t
        for t in toks
        if t not in "()"
        and t.upper() not in _OPERATORS
        and _ID_SHAPED.match(t)
        and SPDX_IDS.get(t.rstrip("+").lower()) is None
        and SPDX_EXCEPTIONS.get(t.lower()) is None
        and not _REF.match(t.rstrip("+"))
    ]
    if not unknown:
        return []
    swapped = " ".join("MIT" if t in unknown else t for t in toks)
    return list(dict.fromkeys(unknown)) if is_spdx(swapped) else []


def _licence_problem(text) -> str:
    unknown = unknown_ids(text)
    if unknown:
        ids = ", ".join(code(u) for u in unknown)
        if len(unknown) == 1:
            return f"{ids} is not an SPDX id this gate knows; if spdx.org/licenses lists it, add it to SPDX_IDS"
        return f"{ids} are not SPDX ids this gate knows; if spdx.org/licenses lists them, add them to SPDX_IDS"
    return "not an SPDX expression"


def licence_allowed(expression, allow) -> bool:
    """True when the expression can be satisfied from the allow-list: every
    term of an AND, at least one of an OR. A `WITH` term needs that exact
    `id WITH exception` on the list."""
    parsed = _parse_spdx(expression)
    if not parsed:
        return False
    allowed = set(allow)

    def ok(node):
        kind = node[0]
        if kind == "id":
            return node[1] in allowed
        if kind == "with":
            return f"{node[1]} WITH {node[2]}" in allowed
        if kind == "group":
            return ok(node[1])
        if kind == "and":
            return all(ok(n) for n in node[1])
        return any(ok(n) for n in node[1])

    return ok(parsed[0])


def resolve_licence(info: dict) -> tuple[str | None, str | None]:
    """(SPDX expression, where it came from): `license_expression` (PEP 639),
    else `license` when it parses as SPDX (it is often prose or the whole
    licence text), else the one SPDX licence the classifiers name, else
    (None, None). A non-empty `license_expression` that does not parse gives
    (None, 'license_expression'): the package declared its licence, and a
    classifier or prose field must not stand in for it, so the entry's
    `licence` has to say what it is."""
    info = info or {}
    expression = info.get("license_expression")
    if isinstance(expression, str) and expression.strip():
        found = canonical_spdx(expression)
        return (found, "license_expression") if found else (None, "license_expression")
    found = canonical_spdx(info.get("license"))
    if found:
        return found, "license"
    mapped = {CLASSIFIER_SPDX[c] for c in info.get("classifiers") or [] if c in CLASSIFIER_SPDX}
    if len(mapped) == 1:
        return mapped.pop(), "classifier"
    return None, None


# --- wheels ----------------------------------------------------------------


def _manylinux_ok(plat: str) -> bool:
    m = re.fullmatch(r"manylinux_(\d+)_(\d+)_x86_64", plat)
    if m:
        return (int(m.group(1)), int(m.group(2))) <= TARGET_GLIBC
    m = re.fullmatch(r"(manylinux1|manylinux2010|manylinux2014)_x86_64", plat)
    return bool(m) and LEGACY_MANYLINUX[m.group(1)] <= TARGET_GLIBC


def _wheel_tags(filename: str):
    if not filename.endswith(".whl"):
        return None
    parts = filename[: -len(".whl")].split("-")
    if len(parts) not in (5, 6):
        return None
    py, abi, plat = parts[-3:]
    return py.split("."), abi.split("."), plat.split(".")


def _interpreter_ok(py: str, abi: str) -> bool:
    if abi == "none":
        m = re.fullmatch(r"py3(\d*)", py)
        if m:
            return not m.group(1) or int(m.group(1)) <= TARGET_MINOR
        return py == f"cp3{TARGET_MINOR}"
    if abi == "abi3":
        m = re.fullmatch(r"cp3(\d+)", py)
        return bool(m) and 2 <= int(m.group(1)) <= TARGET_MINOR
    return py == abi == f"cp3{TARGET_MINOR}"


def target_compatible(filename: str) -> bool:
    """True when pip on the image (CPython 3.14, glibc 2.36, x86_64) would
    install this wheel: a pure `py3` wheel, a `cp314` or `abi3` build for
    manylinux x86_64, or a `py3`/`cp314` wheel with no ABI for any platform.
    The free-threaded `cp314t` ABI and musllinux are not the image's."""
    tags = _wheel_tags(filename)
    if not tags:
        return False
    pys, abis, plats = tags
    if not any(p == "any" or _manylinux_ok(p) for p in plats):
        return False
    return any(_interpreter_ok(py, abi) for py in pys for abi in abis)


def is_pure(filename: str) -> bool:
    tags = _wheel_tags(filename)
    if not tags:
        return False
    pys, abis, plats = tags
    return "any" in plats and "none" in abis and any(re.fullmatch(r"py3\d*", p) for p in pys)


# --- evidence --------------------------------------------------------------

UNSET = object()


def _time(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


@dataclass
class Evidence:
    name: str
    version: str
    last_release: datetime | None = None
    status: str | None = None
    yanked: bool | None = None
    yanked_reason: str | None = None
    owners: int | None = None
    organisation: str | None = None
    licence: str | None = None
    licence_source: str | None = None
    licence_note: str | None = None
    repository: str | None = None
    repository_source: str | None = None
    archived: bool | None = None
    github_org: bool | None = None
    repo_note: str | None = None
    pure_wheel: bool = False
    target_wheel: str | None = None
    attested_by: str | None = None
    times: dict[str, datetime] = field(default_factory=dict)

    def upload_time(self, version: str) -> datetime | None:
        """Earliest upload time over the version's files: when it could
        first be installed."""
        return self.times.get(version)


_GITHUB = re.compile(r"^https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/#?].*)?$", re.I)
_NOT_OWNERS = {"sponsors", "orgs", "users", "apps", "marketplace", "topics"}
_REPO_KEYS = ("repository", "source", "source code", "homepage", "code")


def _github_repo(url) -> str | None:
    m = _GITHUB.match(url.strip()) if isinstance(url, str) else None
    if not m or m.group(1).lower() in _NOT_OWNERS:
        return None
    return f"{m.group(1)}/{m.group(2)}"


def repository_from(project_urls: dict | None) -> str | None:
    """The first github.com/<owner>/<repo> among project_urls: the
    Repository, Source, Source Code, Homepage and Code keys first (any case),
    then any key."""
    urls = {str(k).strip().lower(): v for k, v in (project_urls or {}).items()}
    for key in _REPO_KEYS:
        repo = _github_repo(urls.get(key))
        if repo:
            return repo
    for value in urls.values():
        repo = _github_repo(value)
        if repo:
            return repo
    return None


def _ownership(doc) -> tuple[int | None, str | None]:
    own = doc.get("ownership") if isinstance(doc, dict) else None
    if not isinstance(own, dict) or not isinstance(own.get("roles"), list):
        return None, None
    users = {r.get("user") for r in own["roles"] if isinstance(r, dict) and r.get("user")}
    org = own.get("organization")
    return len(users), org if isinstance(org, str) and org else None


def gather(
    name: str,
    version: str,
    *,
    fetch=urllib_fetch,
    token: str | None = None,
    repository=UNSET,
    sleep=time.sleep,
) -> Evidence:
    """Evidence for `name` at `version`. `repository` is the register entry's
    field: leave it out to take the repository from project_urls, pass None
    (the entry's `"repository": null`) to skip GitHub, or `owner/name`."""
    pkg = urllib.parse.quote(normalise(name), safe="")
    ver = urllib.parse.quote(version, safe="")

    def get(url, headers=None):
        return fetch_json(url, fetch=fetch, headers=headers, sleep=sleep)

    ev = Evidence(name=normalise(name), version=version)

    project = get(f"{PYPI}/pypi/{pkg}/json")
    newest = None
    for v, files in (project.get("releases") or {}).items():
        stamps = [_time(f.get("upload_time_iso_8601")) for f in files or []]
        stamps = [t for t in stamps if t]
        if stamps:
            ev.times[v] = min(stamps)
        for f in files or []:
            t = _time(f.get("upload_time_iso_8601"))
            if t and not f.get("yanked") and (newest is None or t > newest):
                newest = t
    ev.last_release = newest
    ev.owners, ev.organisation = _ownership(project)

    release = get(f"{PYPI}/pypi/{pkg}/{ver}/json")
    info = release.get("info") or {}
    files = release.get("urls") or []
    if ev.owners is None:
        ev.owners, ev.organisation = _ownership(release)
    if version not in ev.times:
        stamps = [t for t in (_time(f.get("upload_time_iso_8601")) for f in files) if t]
        if stamps:
            ev.times[version] = min(stamps)
    ev.yanked = bool(info.get("yanked")) or (bool(files) and all(f.get("yanked") for f in files))
    ev.yanked_reason = info.get("yanked_reason") or next(
        (f.get("yanked_reason") for f in files if f.get("yanked_reason")), None
    )
    ev.licence, ev.licence_source = resolve_licence(info)
    if ev.licence is None and ev.licence_source == "license_expression":
        expression = info.get("license_expression")
        ev.licence_note = f"license_expression {code(expression)} not recognised: {_licence_problem(expression)}"
    usable = sorted(f["filename"] for f in files if f.get("filename") and not f.get("yanked"))
    ev.pure_wheel = any(is_pure(f) for f in usable)
    ev.target_wheel = next((f for f in usable if target_compatible(f)), None)

    simple = get(f"{PYPI}/simple/{pkg}/", {"Accept": SIMPLE_JSON})
    status = simple.get("project-status")
    # A status that is not a string is no status: read as missing, never as one.
    found_status = status.get("status") if isinstance(status, dict) else None
    ev.status = found_status if isinstance(found_status, str) and found_status else None
    mine = {f.get("filename") for f in files}
    provenance = sorted(
        (f["provenance"] for f in simple.get("files") or [] if f.get("filename") in mine and f.get("provenance")),
        key=lambda u: (not u.split("/")[-2].endswith(".whl"), u),
    )
    if provenance:
        url = provenance[0]
        if not url.startswith(f"{PYPI}/integrity/"):
            raise FetchError(f"provenance outside the Integrity API: {url}", url=url)
        try:
            bundle = get(url)
        except FetchError as err:
            if err.status not in (404, 410):
                raise
            bundle = {}
        for b in bundle.get("attestation_bundles") or []:
            pub = b.get("publisher") or {}
            if pub.get("repository"):
                ev.attested_by = f"{pub.get('kind')} {pub['repository']}, workflow {pub.get('workflow')}"
                break

    if repository is UNSET:
        ev.repository = repository_from(info.get("project_urls"))
        ev.repository_source = "project_urls" if ev.repository else None
        if not ev.repository:
            ev.repo_note = "no GitHub repository in project_urls"
    elif repository is None:
        ev.repo_note = "repository null in the register entry"
    else:
        ev.repository, ev.repository_source = repository, "entry"
    if ev.repository:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        owner, repo = (urllib.parse.quote(p, safe="") for p in ev.repository.split("/", 1))
        try:
            found = get(f"{GITHUB_API}/repos/{owner}/{repo}", headers)
            # A field GitHub did not send is not checked, never "no".
            archived = found.get("archived")
            ev.archived = archived if isinstance(archived, bool) else None
            owner_doc = found.get("owner")
            kind = owner_doc.get("type") if isinstance(owner_doc, dict) else None
            ev.github_org = kind == "Organization" if isinstance(kind, str) and kind else None
            if ev.archived is None:
                ev.repo_note = "GitHub did not say whether the repository is archived"
        except FetchError as err:
            # A repository that is gone is evidence, not a failure to gather it.
            if err.status not in (404, 410):
                raise
            ev.repo_note = "repository not found"
    return ev


# --- signals ---------------------------------------------------------------


def months_between(start: datetime, end: datetime) -> int:
    """Whole calendar months from start to end (monthsBetween in the npm gate)."""
    return (end.year - start.year) * 12 + (end.month - start.month) - (1 if end.day < start.day else 0)


def signals(evidence: Evidence, entry: dict | None, now: datetime, policy) -> dict:
    """Per criterion the reason the evidence says it cannot hold, or None:
    `maintained`, `maintainers`, `licence`, `footprint`. `fatal`: project
    status not active, the locked version yanked, or the repository archived;
    only `outcome: replace` with an open follow-up lets it through (the gate's
    rule). `required`: register fields this package needs and the entry lacks
    (`repository` when project_urls name no GitHub repository, `licence` when
    PyPI gives none that parses as SPDX); always blocking."""
    e = evidence
    entry = entry if isinstance(entry, dict) else None
    required: list[str] = []

    fatal = []
    if e.status is not None and e.status != "active":
        fatal.append(f"project status {code(e.status)}")
    if e.yanked:
        fatal.append(
            f"locked version {code(e.version)} yanked" + (f": {code(e.yanked_reason)}" if e.yanked_reason else "")
        )
    if e.archived is True:
        fatal.append("repository archived")

    stale = []
    if e.last_release is None:
        stale.append("no release date recorded")
    else:
        months = months_between(e.last_release, now)
        if months >= 12:
            stale.append(f"no release in {months} months")
    if e.status is None:
        stale.append("project status not available")
    stale.extend(fatal)
    if e.archived is None:
        stale.append(f"repository not checked ({e.repo_note})" if e.repo_note else "repository not checked")
    maintained = "; ".join(stale) or None

    # An organisation on PyPI (PEP 752) or owning the GitHub repository
    # clears it; as in the npm gate, "no organisation" is said only when
    # GitHub answered that a user owns the repository.
    if e.owners is None:
        maintainers = "ownership not available"
    elif e.owners <= 1 and not e.organisation and e.github_org is not True:
        who = "one owner" if e.owners == 1 else "no owner listed"
        org = "no organisation" if e.github_org is False else "organisation not checked"
        maintainers = f"{who}, {org}"
    else:
        maintainers = None

    licence = e.licence
    if licence is None and entry is not None and "licence" in entry:
        licence = canonical_spdx(entry["licence"])
        if licence is None:
            problem = _licence_problem(entry["licence"])
            required.append(f"licence: the entry's `licence` {code(entry['licence'])}: {problem}")
    elif licence is None and entry is not None:
        why = e.licence_note or "PyPI gives no licence that parses as SPDX"
        required.append(f"licence: {why}; the entry needs a `licence` field")
    if licence is None:
        licence_signal = f"no licence resolvable ({e.licence_note})" if e.licence_note else "no licence resolvable"
    elif not licence_allowed(licence, policy.allow_licenses):
        licence_signal = f"licence {code(licence)} not on the allow-list"
    else:
        licence_signal = None

    if entry is not None and "repository" not in entry and e.repository_source != "project_urls" and not e.repository:
        required.append(
            "repository: PyPI's project_urls name no GitHub repository; the entry needs a `repository` "
            "field (`owner/name`, or null with a repositoryWhy)"
        )

    footprint = (
        None
        if e.target_wheel
        else f"no wheel for CPython 3.14 on manylinux x86_64 for {code(e.version)}: builds from source"
    )

    return {
        "maintained": maintained,
        "maintainers": maintainers,
        "licence": licence_signal,
        "footprint": footprint,
        "fatal": "; ".join(fatal) or None,
        "required": required,
    }
