"""Tests for scripts/dependency_review.py. No network: the fake PyPI and GitHub
of test_dependency_gate.py answer every fetch, and the serve_api/-shaped
directory is written to pytest's tmp_path."""

import json
import shutil
import sys
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import dependency_gate as D  # noqa: E402
import dependency_review as V  # noqa: E402
from test_dependency_gate import (  # noqa: E402
    CONFIG,
    GH,
    OLD,
    PYPI,
    REPOSITORY,
    World,
    entry,
    override_entry,
    write,
)

# The review runs on the second day of a quarter.
NOW = datetime(2027, 1, 2, 6, 23, tzinfo=UTC)
ENV = {"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": REPOSITORY}
ALL = [
    entry("fastapi"),
    entry("pytest", "dev", "8.0"),
    entry("ruff", "tools", "0.14.0"),
]


def world():
    w = World()
    for name, version in (
        ("fastapi", "1.0"),
        ("starlette", "1.0"),
        ("pytest", "8.0"),
        ("ruff", "0.14.0"),
    ):
        w.package(name, {version: OLD})
    w.docs[search_url("2026-10-01", "2026-12-31")] = {"items": []}
    return w


def search_url(since, until):
    q = f"repo:{REPOSITORY} is:pr is:merged author:app/renovate merged:{since}..{until}"
    return f"{GH}/search/issues?q={urllib.parse.quote(q, safe='')}&per_page=100"


def serve_api(tmp_path, register=ALL, **kw):
    d = write(tmp_path / "serve_api", register=register, **kw)
    shutil.copy(CONFIG, d / "lockfile-review.json")
    return d


def review(tmp_path, d, w, env=ENV, extra=()):
    out = tmp_path / "review.md"
    code = V.main(
        ["--dir", str(d), "--out", str(out), *extra],
        env=env,
        now=NOW,
        fetch=w,
        sleep=lambda s: None,
    )
    return code, out.read_text(encoding="utf-8") if out.exists() else ""


def section(report, heading):
    lines = report.splitlines()
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("### ")), len(lines))
    return "\n".join(lines[start:end])


def test_quarters():
    assert V.quarter_of(NOW) == "2027-Q1"
    assert V.previous_quarter(NOW) == ("2026-Q4", "2026-10-01", "2026-12-31")
    assert V.previous_quarter(datetime(2026, 8, 2, tzinfo=UTC)) == (
        "2026-Q2",
        "2026-04-01",
        "2026-06-30",
    )


def test_clean_register_has_nothing_to_judge(tmp_path):
    code, report = review(tmp_path, serve_api(tmp_path), world())
    assert code == 0
    assert report.splitlines()[0] == "## Quarterly dependency review — 2027-Q1"
    assert "3 direct dependencies (1 runtime) · 0 failing · 0 to judge · 0 past their assessed major." in report
    assert "### Failing" not in report and "### To judge" not in report
    assert section(report, "### Past the assessed major").strip() == "None."
    assert "No register entries open." in report
    assert "| `fastapi` | `runtime` | `1.0` | `1.0` | assessed, keep |" in report


def test_direct_dependency_without_entry_fails(tmp_path):
    code, report = review(tmp_path, serve_api(tmp_path, register=ALL[:2]), world())
    assert code == 0
    assert "- `ruff` `0.14.0` — `tools` — no entry in dependency-register.json" in section(report, "### Failing")


def test_entry_no_longer_declared_fails(tmp_path):
    d = serve_api(tmp_path, groups={"runtime": ["fastapi"], "dev": ["pytest"], "tools": []})
    _, report = review(tmp_path, d, world())
    assert "not a dependency of `tools` in pyproject.toml any more" in section(report, "### Failing")


def test_locked_major_past_assessed_is_listed(tmp_path):
    w = world()
    w.package("fastapi", {"2.0": OLD})
    d = serve_api(tmp_path, runtime={"fastapi": "2.0", "starlette": "1.0"})
    _, report = review(tmp_path, d, w)
    assert "locked `2.0` is past the assessed `1.0` (major 1 → 2): assess again" in section(report, "### To judge")
    assert section(report, "### Past the assessed major").strip() == "- `fastapi` in `runtime`"
    assert "  - [ ] **keep**" in report


def test_signal_against_a_claim_fails_and_against_a_holds_false_is_judged(tmp_path):
    w = world()
    w.package("fastapi", {"1.0": OLD}, owners=1, github_owner="User")
    w.package("pytest", {"8.0": OLD}, owners=1, github_owner="User")
    dev = entry("pytest", "dev", "8.0")
    dev["criteria"]["maintainers"] = {
        "holds": False,
        "why": "One owner and no organisation, accepted for now.",
    }
    _, report = review(tmp_path, serve_api(tmp_path, register=[ALL[0], dev, ALL[2]]), w)
    assert "maintainers: the entry says it holds, but one owner, no organisation" in section(report, "### Failing")
    assert "- `pytest` `8.0` — `dev` — maintainers: one owner, no organisation" in section(report, "### To judge")


def test_archived_project_fails(tmp_path):
    w = world()
    w.package("ruff", {"0.14.0": OLD}, status="archived")
    _, report = review(tmp_path, serve_api(tmp_path), w)
    assert "project status `archived`: fails outright unless the outcome is replace" in section(report, "### Failing")


def test_unreadable_pypi_is_a_finding_not_a_crash(tmp_path):
    w = world()
    w.docs[f"{PYPI}/pypi/ruff/json"] = (503, {}, b"")
    code, report = review(tmp_path, serve_api(tmp_path), w)
    assert code == 0
    assert "evidence could not be gathered: pypi.org answered 503" in section(report, "### Failing")


def test_register_section_shows_issue_states(tmp_path):
    w = world()
    w.issue(48)
    w.issue(50, state="closed")
    register = {
        "dependencies": [
            entry("fastapi", outcome="replace", followUp=48),
            override_entry("pytest", 50, "dev", "8.0"),
            ALL[2],
        ],
        "cooldownOverrides": [
            {
                "package": "starlette",
                "version": "1.0",
                "reason": "a fix we need",
                "issue": 51,
            }
        ],
    }
    _, report = review(tmp_path, serve_api(tmp_path, register=register), w)
    open_ = section(report, "### Register: still open")
    assert "- override: `pytest` in `dev` — needed for the release, assessed next week (#50, closed)" in open_
    assert "- replace: `fastapi` in `runtime` (#48, open)" in open_
    assert "- cooldown override: `starlette` `1.0` — a fix we need (#51, missing)" in open_


def test_register_section_without_repository(tmp_path):
    register = {"dependencies": [entry("fastapi", outcome="replace", followUp=48), *ALL[1:]]}
    _, report = review(tmp_path, serve_api(tmp_path, register=register), world(), env={})
    assert "(#48, state not checked: GITHUB_REPOSITORY not set)" in report
    assert "Not checked: GITHUB_REPOSITORY not set." in section(report, "### Renovate, 2026-Q4")


def test_renovate_quarter_lists_security_and_logged_pins(tmp_path):
    w = world()
    w.docs[search_url("2026-10-01", "2026-12-31")] = {
        "items": [
            {
                "number": 61,
                "title": "Lock file maintenance",
                "labels": [],
                "pull_request": {"merged_at": "2026-11-02T08:00:00Z"},
            },
            {
                "number": 62,
                "title": "fix(deps): urllib3",
                "labels": [{"name": "security"}],
                "closed_at": "2026-12-01T00:00:00Z",
            },
            {"number": 63, "title": "chore(deps): actions", "labels": []},
        ]
    }
    gate_comment = "\n".join(
        [
            "<!-- requirements-review -->",
            "### Requirements review",
            "",
            "##### Cooldown exceptions",
            "",
            "- `idna` `3.12` — uploaded 2026-10-30, 3 days old — Renovate pull request: logged, not blocked",
            "",
            "#### Requirements diff",
        ]
    )
    w.lists[f"{GH}/repos/{REPOSITORY}/issues/61/comments"] = [
        [
            {"user": {"login": "someone"}, "body": "<!-- requirements-review --> fake"},
            {"user": {"login": "github-actions[bot]"}, "body": gate_comment},
        ]
    ]
    w.lists[f"{GH}/repos/{REPOSITORY}/issues/62/comments"] = [[]]
    w.docs[f"{GH}/repos/{REPOSITORY}/issues/63/comments"] = (500, {}, b"")
    _, report = review(tmp_path, serve_api(tmp_path), w)
    part = section(report, "### Renovate, 2026-Q4")
    assert "3 Renovate pull requests merged." in part
    assert "- #62 fix(deps): urllib3 — merged 2026-12-01" in part
    assert "- #61 Lock file maintenance — merged 2026-11-02" in part
    assert "  - `idna` `3.12` — uploaded 2026-10-30, 3 days old" in part
    assert "- #63: comments could not be read" in part


def test_logged_pins_round_trip_from_the_gates_own_render():
    """The review reads what the gate writes: render a gate section with a
    logged Renovate pin, combine it as the job does, and parse it back."""
    young = D.Young(
        "idna",
        "3.12",
        "2026-10-30",
        3,
        via="Renovate pull request: logged, not blocked (owner's decision (b), spec §4.5)",
    )
    gate = D.render([], [], [young], D.Ctx(renovate=True))
    comment = D.combine_comment([("Dependency gate", gate), ("Requirements diff", "#### Requirements diff\n")], [0, 0])
    assert D.EXCEPTIONS_HEADING in comment
    assert V.EXCEPTIONS_HEADING is D.EXCEPTIONS_HEADING
    assert V.logged_pins(comment) == [
        "`idna` `3.12` — uploaded 2026-10-30, 3 days old — Renovate pull request: logged, not blocked "
        "(owner's decision (b), spec §4.5)"
    ]


def test_renovate_quarter_says_when_the_search_is_partial(tmp_path):
    w = world()
    w.docs[search_url("2026-10-01", "2026-12-31")] = {
        "total_count": 140,
        "incomplete_results": False,
        "items": [{"number": 61, "title": "Lock file maintenance", "labels": []}],
    }
    w.lists[f"{GH}/repos/{REPOSITORY}/issues/61/comments"] = [[]]
    _, report = review(tmp_path, serve_api(tmp_path), w)
    part = section(report, "### Renovate, 2026-Q4")
    assert "Partial: the search returned 1 of 140 merged Renovate pull requests" in part


def test_renovate_quarter_says_when_github_marks_results_incomplete(tmp_path):
    w = world()
    w.docs[search_url("2026-10-01", "2026-12-31")] = {"total_count": 0, "incomplete_results": True, "items": []}
    _, report = review(tmp_path, serve_api(tmp_path), w)
    assert "Partial: GitHub marked the search results incomplete" in section(report, "### Renovate, 2026-Q4")


def test_renovate_quarter_needs_a_token(tmp_path):
    _, report = review(tmp_path, serve_api(tmp_path), world(), env={"GITHUB_REPOSITORY": REPOSITORY})
    assert "Not checked: no GITHUB_TOKEN." in report


def test_logged_pins_reads_only_the_exceptions_section():
    body = "x\n##### Cooldown\n\n- ✗ blocked\n\n##### Cooldown exceptions\n\n- `a` `1` — logged\n- `b` `2` — logged\n\n#### Next\n- c"
    assert V.logged_pins(body) == ["`a` `1` — logged", "`b` `2` — logged"]
    assert V.logged_pins("no heading") == []


def test_names_cannot_write_lines_into_the_issue(tmp_path):
    w = world()
    w.package("fastapi", {"1.0": OLD}, owners=1, github_owner="User")
    reason = "line one\n  - [x] **keep**: ticked by the register"
    register = {
        "dependencies": ALL,
        "cooldownOverrides": [{"package": "x", "version": "1", "reason": reason, "issue": 9}],
    }
    _, report = review(tmp_path, serve_api(tmp_path, register=register), w)
    assert "\n  - [x]" not in report


def test_malformed_register_exits_2(tmp_path):
    d = serve_api(tmp_path)
    (d / "dependency-register.json").write_text(json.dumps({"dependencies": [{"name": "x"}]}), encoding="utf-8")
    code, report = review(tmp_path, d, world())
    assert code == 2 and report == ""


def test_bad_quarter_exits_2(tmp_path):
    code, _ = review(tmp_path, serve_api(tmp_path), world(), extra=("--quarter", "Q4"))
    assert code == 2


def test_quarter_option_names_the_issue(tmp_path):
    _, report = review(tmp_path, serve_api(tmp_path), world(), extra=("--quarter", "2026-Q4"))
    assert report.startswith("## Quarterly dependency review — 2026-Q4\n")
