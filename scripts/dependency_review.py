#!/usr/bin/env python3
"""dependency_review.py — the evidence for the quarterly dependency review.

ICTU recommendation 11 asks, once a quarter, whether each dependency is still
maintained, by the same points recommendation 1 asks before one is added (the
criteria: linked-data-explorer docs/dependency-criteria.md). Nothing else here
notices an abandoned package: it raises no advisory, so the daily audit is
silent, and it opens no Renovate pull request. This re-gathers the PyPI and
GitHub evidence for every direct dependency of serve_api/pyproject.toml and
every entry of serve_api/dependency-register.json, and flags what fails or
needs a judgement; a person decides, and records keep, replace or accept in
the issue .github/workflows/dependency-review.yml opens.

The Python counterpart of linked-data-explorer's scripts/dependency-review.mjs
(spec §4.1, docs/superpowers/specs/2026-11-28-dependency-register-gate-
design.md). It lists:

- every direct dependency with its register entry, the evidence and the
  signals of scripts/pypi_evidence.py, gathered again;
- entries whose locked major has moved past `assessed.version`;
- `replace` and `override` entries with the state of their issue;
- the register's `cooldownOverrides`, with the state of their issue;
- the previous quarter's merged Renovate pull requests: those labelled
  `security`, and the young pins the gate logged on any of them rather than
  blocked (the owner's decision (b), spec §4.5), read from each pull
  request's `<!-- requirements-review -->` comment.

Usage:
  python scripts/dependency_review.py [--dir serve_api] [--out review.md]
    [--quarter 2026-Q4]
The dir holds pyproject.toml, requirements.txt, requirements-dev.txt,
lockfile-review.json and dependency-register.json (a serve_api/ layout).

Environment: GITHUB_TOKEN (read-only use) and GITHUB_REPOSITORY. Without the
repository, issue states and the Renovate section are reported as not
checked; without the token, the Renovate section is.

Exit: 0 the review was written, whatever it found (a finding is for a person,
not a red run); 2 a file in the dir could not be used.

Standard library only.
"""

import os
import re
import sys
import time
import traceback
import urllib.parse
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dependency_gate as D  # noqa: E402
import gate_common as G  # noqa: E402
import pypi_evidence as E  # noqa: E402
import requirements_review as R  # noqa: E402

CRITERIA_URL = "https://github.com/sgort/linked-data-explorer/blob/acc/docs/dependency-criteria.md"
SIGNALLED = D.SIGNALLED
RENOVATE = D.RENOVATE
COMMENTER = "github-actions[bot]"
EXCEPTIONS_HEADING = D.EXCEPTIONS_HEADING


def quarter_of(t: datetime) -> str:
    return f"{t.year}-Q{(t.month - 1) // 3 + 1}"


def quarter_start(t: datetime) -> datetime:
    return datetime(t.year, (t.month - 1) // 3 * 3 + 1, 1, tzinfo=UTC)


def previous_quarter(t: datetime) -> tuple[str, str, str]:
    """The calendar quarter before the one `t` is in: (name, first day, last
    day). The review runs on the second day of a quarter, so the quarter that
    has just ended is the one with something to list."""
    end = quarter_start(t) - timedelta(days=1)
    return (
        quarter_of(end),
        quarter_start(end).strftime("%Y-%m-%d"),
        end.strftime("%Y-%m-%d"),
    )


def text(s) -> str:
    return D.flat(s)


# --- the rows --------------------------------------------------------------


@dataclass
class Row:
    name: str
    group: str
    entry: dict | None
    declared: bool
    locked: str | None = None
    evidence: E.Evidence | None = None
    sig: dict | None = None
    error: str | None = None
    fail: list[str] = field(default_factory=list)
    judge: list[str] = field(default_factory=list)


def requirements_file(group: str) -> str:
    return "requirements.txt" if group == "runtime" else "requirements-dev.txt"


def rows_of(groups: dict[str, set[str]], register: G.Register, scans: dict) -> list[Row]:
    """One row per direct dependency and per register entry, by (name, group)."""
    entries = {(G.normalise(e["name"]), e["manifest"]): e for e in register.dependencies}
    keys = {(n, g) for g, names in groups.items() for n in names} | set(entries)
    rows = []
    for name, group in sorted(keys, key=lambda k: (k[1], k[0])):
        row = Row(name, group, entries.get((name, group)), name in groups.get(group, set()))
        pin = scans[requirements_file(group)].pins.get(name)
        row.locked = pin.version if pin else None
        rows.append(row)
    return rows


def gather_row(row: Row, now: datetime, policy: G.Policy, *, token, fetch, sleep) -> None:
    if not row.locked:
        return
    repository = row.entry["repository"] if row.entry and "repository" in row.entry else E.UNSET
    try:
        row.evidence = E.gather(
            row.name,
            row.locked,
            fetch=fetch,
            token=token,
            repository=repository,
            sleep=sleep,
        )
    except E.FetchError as err:
        row.error = f"evidence could not be gathered: {err}"
        return
    row.sig = E.signals(row.evidence, row.entry, now, policy)


def assess(row: Row) -> None:
    """`fail`: what blocks the gate today, or evidence that is missing.
    `judge`: what a person looks at. Missing evidence is said, never read as
    fine."""
    entry = row.entry
    if not row.declared:
        row.fail.append(f"register entry, but not a dependency of {G.code(row.group)} in pyproject.toml any more")
    if entry is None:
        row.fail.append(f"no entry in {D.REGISTER}")
    if row.locked is None:
        row.fail.append(f"no pin in {G.code(requirements_file(row.group))}")
    if row.error:
        row.fail.append(row.error)
    if entry is not None and row.locked:
        assessed = (entry.get("assessed") or {}).get("version")
        if assessed and D.major(assessed) != D.major(row.locked):
            row.judge.append(
                f"locked {G.code(row.locked)} is past the assessed {G.code(assessed)} (major "
                f"{D.major(assessed)} → {D.major(row.locked)}): assess again"
            )
    sig = row.sig
    if not sig:
        return
    if sig.get("fatal"):
        replace = entry is not None and entry.get("outcome") == "replace"
        row.fail.append(f"{sig['fatal']}" + ("" if replace else ": fails outright unless the outcome is replace"))
    row.fail.extend(sig.get("required") or [])
    for c in SIGNALLED:
        if not sig.get(c):
            continue
        claims = entry is not None and entry["status"] == "assessed" and entry["criteria"][c]["holds"] is True
        if claims:
            row.fail.append(f"{c}: the entry says it holds, but {sig[c]}")
        else:
            row.judge.append(f"{c}: {sig[c]}")


# --- register and issues ---------------------------------------------------


def register_issues(register: G.Register) -> set[int]:
    issues = set()
    for e in register.dependencies:
        if e.get("outcome") == "replace" and "followUp" in e:
            issues.add(e["followUp"])
        if e.get("status") == "override":
            issues.add(e["override"]["issue"])
    for o in register.cooldown_overrides:
        issues.add(o["issue"])
    return issues


def states_of(issues: set[int], env, *, fetch, sleep) -> tuple[dict[int, str], str | None]:
    if not issues:
        return {}, None
    if not env.get("GITHUB_REPOSITORY"):
        return {}, "GITHUB_REPOSITORY not set"
    try:
        return D.issue_states(issues, env, fetch=fetch, sleep=sleep), None
    except (E.FetchError, G.InputError) as err:
        return {}, str(err)


def issue_text(n, states: dict[int, str], error: str | None) -> str:
    if n is None:
        return ""
    if error:
        return f" (#{n}, state not checked: {text(error)})"
    return f" (#{n}, {states.get(n, 'missing')})"


def register_section(register: G.Register, states, error) -> list[str]:
    deps = register.dependencies
    overrides = [e for e in deps if e.get("status") == "override"]
    replaces = [e for e in deps if e.get("outcome") == "replace"]
    cooldown = register.cooldown_overrides
    lines = ["### Register: still open", ""]
    if not overrides and not replaces and not cooldown:
        return [*lines, "No register entries open.", ""]

    def where(e):
        return f"{G.code(e['name'])} in {G.code(e['manifest'])}"

    for e in overrides:
        o = e["override"]
        lines.append(f"- override: {where(e)} — {text(o['reason'])}{issue_text(o['issue'], states, error)}")
    for e in replaces:
        lines.append(f"- replace: {where(e)}{issue_text(e.get('followUp'), states, error)}")
    for o in cooldown:
        lines.append(
            f"- cooldown override: {G.code(o['package'])} {G.code(o['version'])} — {text(o['reason'])}"
            f"{issue_text(o['issue'], states, error)}"
        )
    return [*lines, ""]


# --- Renovate's previous quarter -------------------------------------------


@dataclass
class Merged:
    number: int
    title: str
    merged: str
    security: bool
    logged: list[str] = field(default_factory=list)
    note: str | None = None


def logged_pins(body: str) -> list[str]:
    """The lines under the gate's "Cooldown exceptions" heading."""
    lines = body.splitlines()
    try:
        start = lines.index(EXCEPTIONS_HEADING) + 1
    except ValueError:
        return []
    out = []
    for line in lines[start:]:
        if line.startswith(("#", "<")):
            break
        if line.startswith("- "):
            out.append(line[2:])
    return out


@dataclass
class Quarter:
    """What renovate_quarter found: the pull requests, why nothing could be
    listed (`error`), or why the list is incomplete (`partial`)."""

    merged: list[Merged] = field(default_factory=list)
    error: str | None = None
    partial: str | None = None


def partial_note(found: dict, listed: int) -> str | None:
    """Why one page of search results is not the whole quarter, or None. The
    search answers at most 100 items a page, and GitHub flags a search that
    timed out as incomplete."""
    total = found.get("total_count")
    if isinstance(total, int) and not isinstance(total, bool) and total > listed:
        return f"the search returned {listed} of {total} merged Renovate pull requests; check the rest by hand"
    if found.get("incomplete_results") is True:
        return "GitHub marked the search results incomplete; check the quarter's Renovate pull requests by hand"
    return None


def renovate_quarter(env, since: str, until: str, *, fetch, sleep) -> Quarter:
    """Renovate's pull requests merged between two days (inclusive), and per
    pull request the young pins the gate logged in its comment. A failed
    search is said in the report, never a crash: the review is a report."""
    repo, token = env.get("GITHUB_REPOSITORY"), env.get("GITHUB_TOKEN")
    if not repo:
        return Quarter(error="GITHUB_REPOSITORY not set")
    if not token:
        return Quarter(error="no GITHUB_TOKEN")
    headers = D.github_headers(env)
    q = f"repo:{repo} is:pr is:merged author:app/renovate merged:{since}..{until}"
    url = f"{E.GITHUB_API}/search/issues?q={urllib.parse.quote(q, safe='')}&per_page=100"
    try:
        found = E.fetch_json(url, fetch=fetch, headers=headers, sleep=sleep)
    except E.FetchError as err:
        return Quarter(error=f"the search failed: {err}")
    items = found.get("items") if isinstance(found.get("items"), list) else []
    partial = partial_note(found, len(items))
    out = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("number"), int):
            continue
        labels = [lb.get("name") for lb in item.get("labels") or [] if isinstance(lb, dict)]
        merged = (item.get("pull_request") or {}).get("merged_at") or item.get("closed_at") or ""
        m = Merged(
            item["number"],
            str(item.get("title") or ""),
            str(merged)[:10],
            "security" in labels,
        )
        try:
            comments = D.all_pages(
                f"{E.GITHUB_API}/repos/{repo}/issues/{m.number}/comments",
                headers,
                fetch=fetch,
                sleep=sleep,
            )
        except E.FetchError as err:
            m.note = f"comments could not be read: {err}"
        else:
            mine = [
                c
                for c in comments
                if isinstance(c, dict)
                and (c.get("user") or {}).get("login") == COMMENTER
                and str(c.get("body") or "").startswith(D.MARKER)
            ]
            if not mine:
                m.note = "no requirements-review comment (no requirements change)"
            else:
                m.logged = logged_pins(str(mine[0].get("body") or ""))
        out.append(m)
    return Quarter(sorted(out, key=lambda m: m.number), None, partial)


def renovate_section(quarter: str, found: Quarter) -> list[str]:
    lines = [f"### Renovate, {quarter}", ""]
    if found.error:
        return [*lines, f"Not checked: {text(found.error)}.", ""]
    merged = found.merged
    if found.partial:
        lines += [f"**Partial: {text(found.partial)}.**", ""]
    security = [m for m in merged if m.security]
    logged = [m for m in merged if m.logged]
    lines += [
        f"{len(merged)} Renovate pull request{'' if len(merged) == 1 else 's'} merged.",
        "",
    ]
    lines += ["#### Security exceptions", ""]
    if not security:
        lines.append("None.")
    for m in security:
        lines.append(f"- #{m.number} {text(m.title)} — merged {m.merged}")
    lines += ["", "#### Young pins logged, not blocked", ""]
    lines.append(
        "The cooldown is enforced on people's changes and logged on Renovate's (owner's decision (b), spec §4.5)."
    )
    lines.append("")
    if not logged:
        lines.append("None.")
    for m in logged:
        lines.append(f"- #{m.number} {text(m.title)} — merged {m.merged}")
        lines += [f"  - {text(p)}" for p in m.logged]
    unread = [m for m in merged if m.note and not m.note.startswith("no requirements-review")]
    for m in unread:
        lines.append(f"- #{m.number}: {text(m.note)}")
    return [*lines, ""]


# --- the report ------------------------------------------------------------


def flagged(row: Row, reasons: list[str]) -> list[str]:
    version = G.code(row.locked or "?")
    return [
        f"- {G.code(row.name)} {version} — {G.code(row.group)} — {'; '.join(text(r) for r in reasons)}",
        "  - [ ] **keep**: the criteria still hold well enough; say why below",
        "  - [ ] **replace**: open an issue for it and link it here",
        "  - [ ] **accept**: keep it despite the finding; say why below",
    ]


def table_row(row: Row) -> str:
    e = row.evidence
    entry = row.entry
    said = "—" if entry is None else entry["status"] + (f", {entry['outcome']}" if entry.get("outcome") else "")
    assessed = (entry or {}).get("assessed", {}).get("version") if entry else None
    flags = "; ".join(text(f) for f in [*row.fail, *row.judge]) or "✓"
    if e is None:
        evidence = ["—"] * 5
    else:
        facts = D.facts_of(e)
        evidence = [
            D.day(e.last_release),
            facts["maintainers"],
            facts["licence"],
            facts["footprint"],
            facts["releasePolicy"],
        ]
    cells = [
        G.code(row.name),
        G.code(row.group),
        G.code(row.locked or "?"),
        G.code(assessed) if assessed else "—",
        said,
        *evidence,
        flags,
    ]
    return "| " + " | ".join(D.cell(c) for c in cells) + " |"


def render(*, repository, quarter, date, rows, register, states, issues_error, renovate) -> str:
    failing = [r for r in rows if r.fail]
    judge = [r for r in rows if not r.fail and r.judge]
    moved = [r for r in rows if any("past the assessed" in j for j in r.judge)]
    runtime = sum(1 for r in rows if r.group == "runtime")
    prev_quarter, found = renovate
    lines = [
        f"## Quarterly dependency review — {quarter}",
        "",
        f"{G.code(repository or 'local')}, generated {date.strftime('%Y-%m-%d')} from `serve_api/` on the "
        "default branch.",
        "",
        f"{len(rows)} direct {'dependency' if len(rows) == 1 else 'dependencies'} ({runtime} runtime) · "
        f"{len(failing)} failing · {len(judge)} to judge · {len(moved)} past their assessed major.",
        "",
        f"Apply the [dependency criteria]({CRITERIA_URL}) (ICTU recommendations 1 and 11). For every package "
        "below, tick one outcome and add the reason. Close the issue when each has one; a replacement gets "
        "its own issue, and a changed assessment is a pull request to `serve_api/dependency-register.json`.",
        "",
    ]
    if failing:
        lines += [
            "### Failing",
            "",
            *[ln for r in failing for ln in flagged(r, r.fail + r.judge)],
            "",
        ]
    if judge:
        lines += [
            "### To judge",
            "",
            *[ln for r in judge for ln in flagged(r, r.judge)],
            "",
        ]
    lines += ["### Past the assessed major", ""]
    lines += [f"- {G.code(r.name)} in {G.code(r.group)}" for r in moved] or ["None."]
    lines.append("")
    lines += register_section(register, states, issues_error)
    lines += renovate_section(prev_quarter, found)
    lines += [
        "<details>",
        f"<summary>All direct dependencies ({len(rows)})</summary>",
        "",
        "| package | group | locked | assessed | entry | last release | maintainers | licence | footprint "
        "| release policy | findings |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *[table_row(r) for r in rows],
        "",
        "</details>",
    ]
    return "\n".join(lines).rstrip() + "\n"


# --- the command line ------------------------------------------------------


def run(argv, env, now: datetime, *, fetch, sleep) -> str:
    directory = Path(R.option(argv, "--dir") or "serve_api")
    quarter = R.option(argv, "--quarter") or quarter_of(now)
    if not re.fullmatch(r"\d{4}-Q[1-4]", quarter):
        raise G.InputError(f"--quarter must look like 2026-Q4, not {quarter!r}")
    policy = G.parse_policy(R.read_text(directory, D.POLICY, "the review dir"), str(directory / D.POLICY))
    groups = G.direct_groups(R.read_text(directory, "pyproject.toml", "the review dir"))
    scans = R.scan_dir(directory, "the review dir")
    register = D.load_register(directory / D.REGISTER)
    rows = rows_of(groups, register, scans)
    token = env.get("GITHUB_TOKEN") or None
    for row in rows:
        gather_row(row, now, policy, token=token, fetch=fetch, sleep=sleep)
        assess(row)
    states, issues_error = states_of(register_issues(register), env, fetch=fetch, sleep=sleep)
    prev, since, until = previous_quarter(now)
    found = renovate_quarter(env, since, until, fetch=fetch, sleep=sleep)
    return render(
        repository=env.get("GITHUB_REPOSITORY"),
        quarter=quarter,
        date=now,
        rows=rows,
        register=register,
        states=states,
        issues_error=issues_error,
        renovate=(prev, found),
    )


def main(
    argv,
    *,
    env=None,
    now: datetime | None = None,
    fetch=E.urllib_fetch,
    sleep=time.sleep,
) -> int:
    env = os.environ if env is None else env
    now = now or datetime.now(UTC)
    try:
        out = R.option(argv, "--out")
        report = run(argv, env, now, fetch=fetch, sleep=sleep)
    except Exception as err:  # the review could not be written: exit 2, never an empty report
        if not isinstance(err, (G.InputError, E.FetchError)):
            traceback.print_exc()
        print(f"dependency_review: {D.describe(err)}", file=sys.stderr)
        return 2
    if out:
        Path(out).write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
