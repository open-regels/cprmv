#!/usr/bin/env python3
"""dependency_gate.py — a new direct dependency cannot merge without its
assessment, and a pin cannot merge before its cooldown.

The Python counterpart of linked-data-explorer's scripts/dependency-gate.mjs
(spec §4.1-4.6, docs/superpowers/specs/2026-11-28-dependency-register-gate-
design.md; the criteria: linked-data-explorer docs/dependency-criteria.md).

For every direct dependency new to a group of serve_api/pyproject.toml
(`runtime`, `dev`, `tools`), and for every entry serve_api/dependency-
register.json adds or changes, the entry is checked against evidence gathered
from PyPI and GitHub (scripts/pypi_evidence.py): an entry may not claim a
criterion holds that the evidence says does not, a judgement needs a sentence
of at least 40 characters, distinct within the entry, the assessed major must
be the locked one, a cited issue must be an open issue, and a field the
evidence makes necessary (`licence`, `repository`) must be there; nothing
excuses that last one. A project status other than active, a yanked locked
version or an archived repository fails outright unless the outcome is
replace with an open follow-up.

Every pin either requirements file adds or changes must have been uploaded
at least minReleaseAgeDays (lockfile-review.json) before the run, counted from
the earliest upload of that version's files. The ways through, each logged in
the report: a cooldownOverrides entry with an open issue; a Renovate security
update (author renovate[bot] and the `security` label applied by
renovate[bot]); and, the owner's decision (b) of spec §4.5, any pull request
whose author is renovate[bot], because hosted Renovate cannot be given a
cutoff for the transitive pins it re-resolves. A Renovate security update also
turns a missing register entry into a warning, as in the npm gate.

Usage:
  python scripts/dependency_gate.py <base-dir> <head-dir>
    [--config lockfile-review.json] [--register dependency-register.json]
    [--out gate.md]
  python scripts/dependency_gate.py --check-register [--register file]
  python scripts/dependency_gate.py --combine <part.md> <status> [<part.md> <status> ...]
    --out comment.md [--summary summary.md]
Each dir holds pyproject.toml, requirements.txt, requirements-dev.txt and
optionally dependency-register.json and lockfile-review.json (a serve_api/
layout); --config and --register default to the head dir's copies. The base
register is the base dir's.

Environment: GITHUB_TOKEN (read-only) and GITHUB_REPOSITORY for the GitHub
API; PR_AUTHOR, set by the workflow from the event, and PR_NUMBER when the
author is renovate[bot]. The label is read from the GitHub API, never from
the event payload.

Exit: 0 nothing blocking, 1 a blocking finding, 2 the input, the register,
PyPI or the GitHub API could not be used, which must never read as clean.
`--combine` exits with the worst status of its parts.

Standard library only.
"""

import html
import os
import re
import sys
import time
import traceback
import urllib.parse
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_common as G  # noqa: E402
import pypi_evidence as E  # noqa: E402
import requirements_review as R  # noqa: E402

TITLE = "Dependency gate"
MARKER = "<!-- requirements-review -->"
COMMENT_LIMIT = 65536
RENOVATE = "renovate[bot]"
SIGNALLED = ("maintained", "maintainers", "licence", "footprint")
JUDGEMENT = "none: a judgement"
LABEL_WAIT = 60
LABEL_POLL = 5
MAX_PAGES = 30
REGISTER = "dependency-register.json"
POLICY = "lockfile-review.json"
# The heading the cooldown exceptions are listed under. dependency_review.py
# reads the logged pins back from a merged pull request's comment by it.
EXCEPTIONS_HEADING = "##### Cooldown exceptions"


def flat(s) -> str:
    return re.sub(r"[\r\n]+", " ", str(s))


def cell(s) -> str:
    """A table cell: one line, a pipe cannot end the cell early, and HTML in
    it (a register `why` with `<!--` or `</details>`) cannot hide what follows
    or open and close a fold."""
    return html.escape(flat(s), quote=False).replace("|", "\\|")


def day(t: datetime | None) -> str:
    return t.strftime("%Y-%m-%d") if t else "—"


def major(v) -> str:
    return str(v or "").split(".")[0]


# --- GitHub ----------------------------------------------------------------


def github_headers(env) -> dict:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if env.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {env['GITHUB_TOKEN']}"
    return headers


def repository_of(env, why: str) -> str:
    repo = env.get("GITHUB_REPOSITORY")
    if not repo:
        raise G.InputError(f"GITHUB_REPOSITORY is needed to {why}")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise G.InputError(f'GITHUB_REPOSITORY is not "owner/repo": {repo}')
    return repo


def all_pages(url: str, headers: dict, *, fetch, sleep) -> list:
    """Every item of a paginated GitHub list."""
    items: list = []
    for page in range(1, MAX_PAGES + 1):
        batch = E.fetch_json(f"{url}?per_page=100&page={page}", fetch=fetch, headers=headers, sleep=sleep, expect=list)
        items.extend(batch)
        if len(batch) < 100:
            return items
    raise E.FetchError(f"{url} has more than {MAX_PAGES * 100} items", url=url)


def is_renovate_security(author, labels, events) -> bool:
    """The author is renovate[bot], the `security` label is on the pull
    request now, and renovate[bot] is the one that put it there. A person
    adding the label does not count."""
    if author != RENOVATE or "security" not in labels:
        return False
    return any(
        isinstance(e, dict)
        and e.get("event") == "labeled"
        and (e.get("label") or {}).get("name") == "security"
        and (e.get("actor") or {}).get("login") == RENOVATE
        for e in events
    )


def renovate_security(env, *, fetch, sleep, wait=LABEL_WAIT, poll=LABEL_POLL) -> bool:
    """Whether this run is a Renovate security update, asked of the GitHub
    API at run time. Renovate labels a pull request a second or so after
    opening it, so a run started by `opened` can get here first: wait until
    the pull request carries any label, up to `wait` seconds, then decide
    with what is there. Asked only when PR_AUTHOR is renovate[bot]."""
    if env.get("PR_AUTHOR") != RENOVATE:
        return False
    number = env.get("PR_NUMBER") or ""
    if not re.fullmatch(r"[1-9]\d*", number):
        raise G.InputError(
            f'PR_NUMBER must be the pull request\'s number when PR_AUTHOR is {RENOVATE} (got "{number}")'
        )
    repo = repository_of(env, "check a Renovate pull request's labels")
    url = f"{E.GITHUB_API}/repos/{repo}/issues/{number}"
    headers = github_headers(env)
    try:
        labels = all_pages(f"{url}/labels", headers, fetch=fetch, sleep=sleep)
        waited = 0
        while not labels and waited < wait:
            sleep(poll)
            waited += poll
            labels = all_pages(f"{url}/labels", headers, fetch=fetch, sleep=sleep)
        events = all_pages(f"{url}/events", headers, fetch=fetch, sleep=sleep)
    except E.FetchError as err:
        raise E.FetchError(f"GitHub pull request #{number}: {err}", err.status, err.url) from err
    names = [label.get("name") for label in labels if isinstance(label, dict)]
    return is_renovate_security(env.get("PR_AUTHOR"), names, events)


def issue_states(numbers, env, *, fetch, sleep) -> dict[int, str]:
    """'open', 'closed', 'pull request' or 'missing' per issue number."""
    states: dict[int, str] = {}
    if not numbers:
        return states
    repo = repository_of(env, "look up issues")
    headers = github_headers(env)
    for n in sorted(numbers):
        try:
            issue = E.fetch_json(f"{E.GITHUB_API}/repos/{repo}/issues/{n}", fetch=fetch, headers=headers, sleep=sleep)
        except E.FetchError as err:
            # A missing or deleted issue is simply not open.
            if err.status in (404, 410):
                states[n] = "missing"
                continue
            raise E.FetchError(f"GitHub issue #{n}: {err}", err.status, err.url) from err
        # The issues endpoint answers for pull requests too.
        states[n] = "pull request" if issue.get("pull_request") else str(issue.get("state"))
    return states


# --- PyPI upload times -----------------------------------------------------


def _earliest(files) -> datetime | None:
    stamps = [E._time(f.get("upload_time_iso_8601")) for f in files or [] if isinstance(f, dict)]
    stamps = [t for t in stamps if t]
    return min(stamps) if stamps else None


class UploadTimes:
    """When each version could first be installed: the earliest upload over
    its files, from the project endpoint's `releases`, else the version
    endpoint. Project documents are fetched once per package."""

    def __init__(self, *, fetch, sleep):
        self.fetch, self.sleep = fetch, sleep
        self.projects: dict[str, dict] = {}

    def get(self, name: str, version: str) -> datetime | None:
        pkg = urllib.parse.quote(name, safe="")
        if name not in self.projects:
            try:
                self.projects[name] = E.fetch_json(f"{E.PYPI}/pypi/{pkg}/json", fetch=self.fetch, sleep=self.sleep)
            except E.FetchError as err:
                raise E.FetchError(f"PyPI {name}: {err}", err.status, err.url) from err
        found = _earliest((self.projects[name].get("releases") or {}).get(version))
        if found:
            return found
        ver = urllib.parse.quote(version, safe="")
        try:
            doc = E.fetch_json(f"{E.PYPI}/pypi/{pkg}/{ver}/json", fetch=self.fetch, sleep=self.sleep)
        except E.FetchError as err:
            if err.status in (404, 410):
                return None  # not on PyPI: no upload time, which blocks
            raise E.FetchError(f"PyPI {name} {version}: {err}", err.status, err.url) from err
        return _earliest(doc.get("urls"))


# --- evaluation ------------------------------------------------------------


@dataclass
class Ctx:
    renovate: bool = False
    renovate_security: bool = False
    issues: dict[int, str] = field(default_factory=dict)

    def issue_problem(self, n: int) -> str | None:
        state = self.issues.get(n, "missing")
        if state == "open":
            return None
        if state == "pull request":
            return f"#{n} is a pull request, not an issue"
        return f"#{n} is not open"


def evaluate(name: str, group: str, entry: dict | None, sig: dict | None, locked: str, ctx: Ctx):
    """The rules of spec §4.3 for one entry (the npm gate's
    evaluateNewDependency): (blocking, warnings)."""
    blocking: list[str] = []
    warnings: list[str] = []
    if entry is None:
        if ctx.renovate_security:
            warnings.append("Renovate security update with no register entry: still to assess")
        else:
            blocking.append(f"no entry in {REGISTER} for {G.code(name)} in {G.code(group)}")
        return blocking, warnings
    assessed = (entry.get("assessed") or {}).get("version")
    if assessed and major(assessed) != major(locked):
        blocking.append(
            f"assessed version {G.code(assessed)} is a different major than the locked {G.code(locked)}: assess again"
        )
    # Fields the evidence makes necessary: nothing excuses a missing one.
    blocking.extend((sig or {}).get("required") or [])
    if entry["status"] == "override":
        problem = ctx.issue_problem(entry["override"]["issue"])
        if problem:
            blocking.append(f"override issue {problem}")
        warnings.append(
            f"override: {G.code(entry['override']['reason'])} (issue #{entry['override']['issue']}), "
            "to be replaced by an assessment"
        )
        return blocking, warnings
    criteria = entry["criteria"]
    for c in SIGNALLED:
        if sig and sig.get(c) and criteria[c]["holds"] is True:
            blocking.append(f"{c}: the entry says it holds, but {sig[c]}")
    first: dict[str, str] = {}
    for c in G.CRITERIA:
        why = (criteria[c].get("why") or "").strip()
        if (c == "needed" or criteria[c]["holds"] is False) and len(why) < G.MIN_WHY:
            has = f" (has {len(why)})" if why else ""
            blocking.append(f"{c}: needs a why of at least {G.MIN_WHY} characters{has}")
        if why:
            if why in first:
                blocking.append(f"{c}: why is identical to the one for {first[why]}")
            else:
                first[why] = c
    if "followUp" in entry:
        problem = ctx.issue_problem(entry["followUp"])
        if problem:
            blocking.append(f"follow-up issue {problem}")
    if sig and sig.get("fatal") and entry.get("outcome") != "replace":
        blocking.append(f"{sig['fatal']}: fails outright unless the outcome is replace with an open followUp")
    return blocking, warnings


@dataclass
class Young:
    name: str
    version: str
    uploaded: str
    age: int
    via: str = ""
    issue: int | None = None


def evaluate_cooldown(changed, times: dict, now: datetime, min_days: int, overrides: list, ctx: Ctx):
    """(blocking, exceptions) for the changed pins: each must be at least
    `min_days` old, unless excepted. A missing upload time blocks."""
    blocking: list[str] = []
    exceptions: list[Young] = []
    for name, version in changed:
        uploaded = times.get((name, version))
        if uploaded is None:
            blocking.append(f"{G.code(name)} {G.code(version)}: no upload time to check the cooldown against")
            continue
        age = now - uploaded
        if age.total_seconds() >= min_days * 86400:
            continue
        young = Young(name, version, day(uploaded), age.days)
        override = next(
            (o for o in overrides if G.normalise(o["package"]) == name and o["version"] == version),
            None,
        )
        problem = ctx.issue_problem(override["issue"]) if override else None
        if ctx.renovate_security:
            young.via = "Renovate security update"
        elif override and not problem:
            young.via, young.issue = f"override: {G.code(override['reason'])}", override["issue"]
        elif ctx.renovate:
            young.via = "Renovate pull request: logged, not blocked (owner's decision (b), spec §4.5)"
        else:
            why = f"override issue {problem}" if override else "no exception"
            blocking.append(
                f"{G.code(name)} {G.code(version)}: uploaded {young.uploaded}, {young.age} days ago, "
                f"under the {min_days}-day cooldown ({why})"
            )
            continue
        exceptions.append(young)
    return blocking, exceptions


# --- the report ------------------------------------------------------------


@dataclass
class Row:
    name: str
    group: str
    reason: str
    entry: dict | None
    locked: str | None = None
    evidence: E.Evidence | None = None
    blocking: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def facts_of(e: E.Evidence) -> dict[str, str]:
    if e.archived is True:
        repo = "repository archived"
    elif e.archived is False:
        repo = "repository not archived"
    else:
        repo = f"repository not checked ({e.repo_note})" if e.repo_note else "repository not checked"
    owner = {True: "repository owned by an organisation", False: "repository owned by a user"}.get(
        e.github_org, "GitHub owner not checked"
    )
    owners = "?" if e.owners is None else str(e.owners)
    org = f"PyPI organisation {G.code(e.organisation)}" if e.organisation else "no PyPI organisation"
    if e.licence:
        licence = f"{G.code(e.licence)} ({e.licence_source or 'entry'})"
    else:
        licence = f"none resolvable ({e.licence_note})" if e.licence_note else "none resolvable"
    if e.pure_wheel:
        footprint = "pure wheel"
    elif e.target_wheel:
        footprint = f"wheel {G.code(e.target_wheel)}"
    else:
        footprint = "no wheel for CPython 3.14 on manylinux x86_64: builds from source"
    yanked = (
        f"locked version yanked{f': {G.code(e.yanked_reason)}' if e.yanked_reason else ''}"
        if e.yanked
        else "not yanked"
    )
    return {
        "maintained": "; ".join(
            [
                f"last release {day(e.last_release)}",
                f"project status {G.code(e.status or 'not available')}",
                yanked,
                repo,
            ]
        ),
        "maintainers": f"{owners} PyPI owner{'' if e.owners == 1 else 's'}, {org}; {owner}",
        "licence": licence,
        "releasePolicy": f"trusted publisher: {G.code(e.attested_by)}"
        if e.attested_by
        else f"{JUDGEMENT} (no attestation)",
        "footprint": footprint,
        "needed": JUDGEMENT,
    }


def evidence_table(row: Row) -> list[str]:
    e = row.evidence
    facts = facts_of(e)
    repo = (
        f"repository {G.code(e.repository)} ({e.repository_source})."
        if e.repository
        else "no GitHub repository recorded."
    )
    lines = [
        f"Locked {G.code(row.locked)}, {repo}",
        "",
        "| criterion | evidence | register entry | |",
        "| --- | --- | --- | :-: |",
    ]
    for c in G.CRITERIA:
        said, mark = "—", "—"
        if row.entry and row.entry["status"] == "override":
            said = "override"
        elif row.entry:
            crit = row.entry["criteria"][c]
            said = ("holds" if crit["holds"] else "does not hold") + (f": {crit['why']}" if crit.get("why") else "")
            mark = "✗" if any(b.startswith(f"{c}:") for b in row.blocking) else "✓"
        lines.append(f"| {c} | {cell(facts[c])} | {cell(said)} | {mark} |")
    return [*lines, ""]


def render(rows: list[Row], cooldown_blocking, exceptions, ctx: Ctx) -> str:
    lines = [f"#### {TITLE}", ""]
    if ctx.renovate_security:
        lines += [
            "Renovate security update: young pins are logged, not blocked, and a new dependency without an "
            "entry is a warning.",
            "",
        ]
    elif ctx.renovate:
        lines += [
            "Renovate pull request: young pins are logged, not blocked (owner's decision (b), spec §4.5); "
            "the new-dependency rules apply.",
            "",
        ]
    if not rows:
        lines += ["No new direct dependencies and no register entries added or changed.", ""]
    for row in rows:
        mark = "✗" if row.blocking else "✓"
        lines += [f"**{mark} {G.code(row.name)} in {G.code(row.group)}** ({row.reason})", ""]
        if row.evidence:
            lines += evidence_table(row)
        lines += [f"- ✗ {flat(b)}" for b in row.blocking]
        lines += [f"- warning: {flat(w)}" for w in row.warnings]
        if row.blocking or row.warnings:
            lines.append("")
    lines += ["##### Cooldown", ""]
    if not cooldown_blocking:
        lines.append("Every changed pin is old enough or excepted.")
    lines += [f"- ✗ {flat(b)}" for b in cooldown_blocking]
    if exceptions:
        lines += ["", EXCEPTIONS_HEADING, ""]
        for x in exceptions:
            issue = f" (#{x.issue})" if x.issue is not None else ""
            lines.append(
                f"- {G.code(x.name)} {G.code(x.version)} — uploaded {x.uploaded}, {x.age} days old — {flat(x.via)}{issue}"
            )
    return "\n".join(lines).rstrip() + "\n"


def render_failure(message: str) -> str:
    return "\n".join(
        [f"#### {TITLE}", "", "**✗ The dependency gate could not run** — the check fails.", "", G.code(message), ""]
    )


# --- the combined comment --------------------------------------------------

_VERDICT = {0: "✓ {}: no blocking findings.", 1: "✗ {}: blocks — the check fails."}
_NOTE = "\n\n_Cut to fit a GitHub comment. The full report is in the `requirements-review` job summary._\n"
_CLOSE = "\n</details>\n"


def combine_comment(sections, statuses, limit: int | None = COMMENT_LIMIT) -> str:
    """One comment from the parts' sections: the marker once, a verdict per
    part at the top, then the sections in order. Cut from the end to fit
    `limit` characters, so the verdict list always survives; None keeps the
    whole text (the job summary)."""
    verdicts = [
        "- " + _VERDICT.get(status, "✗ {}: could not run — the check fails.").format(title)
        for (title, _), status in zip(sections, statuses, strict=True)
    ]
    head = "\n".join([MARKER, "### Requirements review", "", *verdicts, ""]) + "\n"
    # A section cannot carry the marker: the comment job finds its comment by it.
    escaped = MARKER.replace("<", "&lt;").replace(">", "&gt;")
    body = "\n\n".join(str(text).replace(MARKER, escaped).strip() for _, text in sections) + "\n"
    full = head + body
    if limit is None or len(full) <= limit:
        return full
    room = body[: max(limit - len(head) - len(_NOTE) - len(_CLOSE), 0)]
    cut = room[: room.rfind("\n")] if "\n" in room else ""
    unclosed = cut.count("<details>") - cut.count("</details>")
    return head + cut + (_CLOSE if unclosed > 0 else "") + _NOTE


def combine(args: list[str]) -> tuple[int, str, str]:
    i = args.index("--combine")
    parts = []
    for a in args[i + 1 :]:
        if a.startswith("--"):
            break
        parts.append(a)
    if not parts or len(parts) % 2:
        raise G.InputError("usage: dependency_gate.py --combine <part.md> <status> [...] --out file [--summary file]")
    sections, statuses = [], []
    for path, status in zip(parts[::2], parts[1::2], strict=True):
        if not re.fullmatch(r"\d+", status):
            raise G.InputError(f"--combine: status of {path} must be a number, not {status!r}")
        text = R.read_text(Path(path).parent, Path(path).name, "--combine")
        heading = next((ln[5:].strip() for ln in text.splitlines() if ln.startswith("#### ")), Path(path).stem)
        sections.append((heading, text))
        statuses.append(min(int(status), 2))
    return max(statuses), combine_comment(sections, statuses), combine_comment(sections, statuses, limit=None)


# --- the command line ------------------------------------------------------


def load_register(path: Path) -> G.Register:
    if not path.exists():
        return G.Register([], [])
    return G.parse_register(R.read_text(path.parent, path.name, "register"), str(path))


def run(args, env, now: datetime, *, fetch, sleep) -> tuple[int, str]:
    pos = R.positionals(args)
    if len(pos) != 2:
        raise G.InputError(
            "usage: dependency_gate.py <base-dir> <head-dir> [--config file] [--register file] [--out file]"
            " | --check-register [--register file] | --combine <part.md> <status> ..."
        )
    base_dir, head_dir = (Path(p) for p in pos)
    config = Path(R.option(args, "--config") or head_dir / POLICY)
    policy = G.parse_policy(R.read_text(config.parent, config.name, "config"), str(config))
    base_groups = G.direct_groups(R.read_text(base_dir, "pyproject.toml", "base"))
    head_groups = G.direct_groups(R.read_text(head_dir, "pyproject.toml", "head"))
    base_scan, head_scan = R.scan_dir(base_dir, "base"), R.scan_dir(head_dir, "head")
    base_reg = load_register(base_dir / REGISTER)
    head_reg = load_register(Path(R.option(args, "--register") or head_dir / REGISTER))

    ctx = Ctx(renovate=env.get("PR_AUTHOR") == RENOVATE)
    ctx.renovate_security = renovate_security(env, fetch=fetch, sleep=sleep)

    def key(e):
        return (G.normalise(e["name"]), e["manifest"])

    base_entries = {key(e): e for e in base_reg.dependencies}
    head_entries = {key(e): e for e in head_reg.dependencies}
    reasons: dict[tuple[str, str], str] = {}
    for name, group in G.new_direct(base_groups, head_groups):
        reasons[(name, group)] = "new direct dependency"
    for k, e in head_entries.items():
        if k not in reasons and base_entries.get(k) != e:
            reasons[k] = "register entry added" if k not in base_entries else "register entry changed"

    changed: list[tuple[str, str]] = []
    for f in R.FILES:
        d = R.diff_pins(base_scan[f].pins, head_scan[f].pins)
        for pin in d.added:
            changed.append((pin.name, pin.version))
        for u in d.updated:
            changed.append((u.name, u.new))
    changed = sorted(set(changed))

    issues: set[int] = set()
    for k in reasons:
        e = head_entries.get(k)
        if e and "followUp" in e:
            issues.add(e["followUp"])
        if e and e.get("status") == "override":
            issues.add(e["override"]["issue"])
    for o in head_reg.cooldown_overrides:
        if (G.normalise(o["package"]), o["version"]) in changed:
            issues.add(o["issue"])
    ctx.issues = issue_states(issues, env, fetch=fetch, sleep=sleep)

    token = env.get("GITHUB_TOKEN") or None
    rows: list[Row] = []
    for (name, group), reason in sorted(reasons.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        row = Row(name, group, reason, head_entries.get((name, group)))
        rows.append(row)
        if name not in head_groups.get(group, set()):
            row.warnings.append(
                f"{G.code(name)} is not a direct dependency of {G.code(group)} in pyproject.toml: entry not judged"
            )
            continue
        file = "requirements.txt" if group == "runtime" else "requirements-dev.txt"
        pin = head_scan[file].pins.get(name)
        if pin is None:
            row.blocking.append(f"{G.code(name)} has no pin in {G.code(file)}: recompile the requirements")
            continue
        row.locked = pin.version
        repository = row.entry["repository"] if row.entry and "repository" in row.entry else E.UNSET
        row.evidence = E.gather(name, pin.version, fetch=fetch, token=token, repository=repository, sleep=sleep)
        sig = E.signals(row.evidence, row.entry, now, policy)
        row.blocking, row.warnings = evaluate(name, group, row.entry, sig, pin.version, ctx)

    upload = UploadTimes(fetch=fetch, sleep=sleep)
    times = {}
    for name, version in changed:
        gathered = next((r.evidence for r in rows if r.evidence and r.name == name), None)
        found = gathered.upload_time(version) if gathered else None
        times[(name, version)] = found or upload.get(name, version)
    cooldown_blocking, exceptions = evaluate_cooldown(
        changed, times, now, policy.min_release_age_days, head_reg.cooldown_overrides, ctx
    )
    report = render(rows, cooldown_blocking, exceptions, ctx)
    blocking = any(r.blocking for r in rows) or bool(cooldown_blocking)
    return (1 if blocking else 0), report


def describe(err: BaseException) -> str:
    if isinstance(err, (G.InputError, E.FetchError)):
        return str(err)
    return f"{type(err).__name__}: {err}"


def main(argv, *, env=None, now: datetime | None = None, fetch=E.urllib_fetch, sleep=time.sleep) -> int:
    env = os.environ if env is None else env
    now = now or datetime.now(UTC)
    out = summary = None
    try:
        out, summary = R.option(argv, "--out"), R.option(argv, "--summary")
        if "--check-register" in argv:
            path = Path(R.option(argv, "--register") or Path("serve_api") / REGISTER)
            if not path.exists():
                print(f"no {REGISTER} at {path}")
                return 0
            reg = load_register(path)
            print(f"{path}: {len(reg.dependencies)} entries, {len(reg.cooldown_overrides)} cooldown overrides")
            return 0
        if "--combine" in argv:
            status, comment, full = combine(argv)
            if out:
                Path(out).write_text(comment, encoding="utf-8")
            else:
                sys.stdout.write(comment)
            if summary:
                Path(summary).write_text(full, encoding="utf-8")
            return status
        status, report = run(argv, env, now, fetch=fetch, sleep=sleep)
    except Exception as err:  # anything unexpected is exit 2 too: a crash must not read as clean
        if not isinstance(err, (G.InputError, E.FetchError)):
            traceback.print_exc()
        print(f"dependency_gate: {describe(err)}", file=sys.stderr)
        if "--check-register" in argv or "--combine" in argv:
            if "--combine" in argv:
                failure = "\n".join(
                    [
                        "#### Comment",
                        "",
                        "**✗ The report could not be combined** — the check fails.",
                        "",
                        G.code(describe(err)),
                    ]
                )
                text = combine_comment([("Comment", failure)], [2])
                # The job summary says why as well, not only the comment.
                for file in (out, summary):
                    if file:
                        Path(file).write_text(text, encoding="utf-8")
            return 2
        report, status = render_failure(describe(err)), 2
    if out:
        Path(out).write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
