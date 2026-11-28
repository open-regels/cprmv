"""Tests for scripts/dependency_gate.py. No network: a fake PyPI and GitHub
answer every fetch, and the serve_api/-shaped directories are written to
pytest's tmp_path."""

import json
import sys
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
REPO = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import dependency_gate as D  # noqa: E402
import gate_common as G  # noqa: E402

NOW = datetime(2026, 11, 28, 12, tzinfo=UTC)
OLD = NOW - timedelta(days=200)
YOUNG = NOW - timedelta(days=3)
PYPI = "https://pypi.org"
GH = "https://api.github.com"
REPOSITORY = "open-regels/cprmv"
CONFIG = REPO / "serve_api" / "lockfile-review.json"
HASH = "--hash=sha256:" + "b" * 64
PERSON = {"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": REPOSITORY, "PR_AUTHOR": "someone", "PR_NUMBER": "0"}
RENOVATE = {**PERSON, "PR_AUTHOR": "renovate[bot]", "PR_NUMBER": "12"}


def iso(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


class World:
    """PyPI and GitHub as a URL map. GitHub list endpoints page by 100."""

    def __init__(self):
        self.docs = {}
        self.lists = {}
        self.calls = []

    def package(
        self,
        name,
        versions,
        *,
        licence="MIT",
        repo="",
        owners=2,
        org=None,
        status="active",
        wheel="py3-none-any",
        yanked=(),
        github_owner="Organization",
        archived=False,
        release_key=True,
    ):
        """`versions`: {version: upload time, or a list of upload times, one per file}."""
        repo = f"{name}-org/{name}" if repo == "" else repo
        releases = {}
        for v, t in versions.items():
            stamps = t if isinstance(t, list) else [t]
            files = [
                {
                    "filename": f"{name}-{v}-{wheel}.whl" if i == 0 else f"{name}-{v}.tar.gz",
                    "upload_time_iso_8601": iso(s),
                    "yanked": v in yanked,
                }
                for i, s in enumerate(stamps)
            ]
            releases[v] = files
        urls = {"Source": f"https://github.com/{repo}"} if repo else {"Documentation": f"https://{name}.example/"}
        self.docs[f"{PYPI}/pypi/{name}/json"] = {
            "info": {"name": name},
            "releases": releases if release_key else {},
            "ownership": {"roles": [{"role": "Owner", "user": f"u{i}"} for i in range(owners)], "organization": org},
        }
        for v, files in releases.items():
            self.docs[f"{PYPI}/pypi/{name}/{v}/json"] = {
                "info": {"license_expression": licence, "project_urls": urls, "yanked": v in yanked},
                "urls": files,
            }
        self.docs[f"{PYPI}/simple/{name}/"] = {
            "project-status": {"status": status},
            "files": [{"filename": f["filename"], "provenance": None} for fs in releases.values() for f in fs],
        }
        if repo:
            self.docs[f"{GH}/repos/{repo}"] = {"archived": archived, "owner": {"type": github_owner}}

    def issue(self, n, state="open", pull_request=False):
        doc = {"number": n, "state": state}
        if pull_request:
            doc["pull_request"] = {"url": "x"}
        self.docs[f"{GH}/repos/{REPOSITORY}/issues/{n}"] = doc

    def pr(self, n, labels, events):
        """`labels`: a list, or a list of lists answered in turn (Renovate
        labelling after the run started)."""
        self.lists[f"{GH}/repos/{REPOSITORY}/issues/{n}/labels"] = (
            labels if labels and isinstance(labels[0], list) else [labels]
        )
        self.lists[f"{GH}/repos/{REPOSITORY}/issues/{n}/events"] = [events]

    def __call__(self, url, headers, timeout):
        self.calls.append(url)
        split = urllib.parse.urlsplit(url)
        bare = f"{split.scheme}://{split.netloc}{split.path}"
        if bare in self.lists:
            q = urllib.parse.parse_qs(split.query)
            assert q["per_page"] == ["100"], url
            page = int(q["page"][0])
            answers = self.lists[bare]
            items = answers[0]
            if page == 1 and len(answers) > 1:
                answers.pop(0)
            return 200, {}, json.dumps(items[(page - 1) * 100 : page * 100]).encode()
        doc = self.docs.get(url)
        if doc is None:
            return 404, {}, b'{"message": "Not Found"}'
        if isinstance(doc, tuple):
            return doc
        return 200, {}, json.dumps(doc).encode()


def labelled(label, by):
    return {"event": "labeled", "label": {"name": label}, "actor": {"login": by}}


def base_world():
    w = World()
    for name, version in (("fastapi", "1.0"), ("starlette", "1.0"), ("pytest", "8.0"), ("ruff", "0.14.0")):
        w.package(name, {version: OLD})
    return w


WHY = {c: f"The {c} criterion: a sentence that is long enough to pass." for c in G.CRITERIA}


def entry(name, group="runtime", version="1.0", **over):
    e = {
        "name": name,
        "manifest": group,
        "status": "assessed",
        "assessed": {"version": version, "date": "2026-11-28"},
        "criteria": {c: {"holds": True, "why": WHY[c]} for c in G.CRITERIA},
        "outcome": "keep",
    }
    e.update(over)
    return e


def override_entry(name, issue, group="runtime", version="1.0"):
    return {
        "name": name,
        "manifest": group,
        "status": "override",
        "assessed": {"version": version},
        "override": {"reason": "needed for the release, assessed next week", "issue": issue},
    }


def req(pins):
    lines = ["#", "# autogenerated by pip-compile", "#"]
    for name, version in sorted(pins.items()):
        lines += [f"{name}=={version} \\", f"    {HASH}"]
    return "\n".join(lines) + "\n"


BASE_GROUPS = {"runtime": ["fastapi"], "dev": ["pytest"], "tools": ["ruff"]}
BASE_RUNTIME = {"fastapi": "1.0", "starlette": "1.0"}
BASE_DEV = {**BASE_RUNTIME, "pytest": "8.0", "ruff": "0.14.0"}


def write(path, groups=None, runtime=None, dev=None, register=None):
    groups = BASE_GROUPS if groups is None else groups
    path.mkdir(parents=True, exist_ok=True)
    extras = "\n".join(f"{g} = {json.dumps(n)}" for g, n in groups.items() if g != "runtime")
    (path / "pyproject.toml").write_text(
        f'[project]\nname = "x"\ndependencies = {json.dumps(groups.get("runtime", []))}\n\n'
        f"[project.optional-dependencies]\n{extras}\n",
        encoding="utf-8",
    )
    (path / "requirements.txt").write_text(req(BASE_RUNTIME if runtime is None else runtime), encoding="utf-8")
    (path / "requirements-dev.txt").write_text(req(BASE_DEV if dev is None else dev), encoding="utf-8")
    if register is not None:
        doc = register if isinstance(register, dict) else {"dependencies": register}
        (path / "dependency-register.json").write_text(json.dumps(doc), encoding="utf-8")
    return path


def gate(tmp_path, base, head, world, env=PERSON, extra=(), sleep=None):
    out = tmp_path / "gate.md"
    sleeps = []
    code = D.main(
        [str(base), str(head), "--config", str(CONFIG), "--out", str(out), *extra],
        env=env,
        now=NOW,
        fetch=world,
        sleep=sleep or sleeps.append,
    )
    return code, out.read_text(encoding="utf-8")


def add_rdflib(tmp_path, world, register=None, version="7.0", group="runtime", when=OLD, **pkg):
    """Head adds rdflib to `group`, pinned in the files that group uses."""
    world.package("rdflib", {version: when}, **pkg)
    groups = {g: list(n) for g, n in BASE_GROUPS.items()}
    groups[group].append("rdflib")
    runtime = {**BASE_RUNTIME, "rdflib": version} if group == "runtime" else BASE_RUNTIME
    dev = {**BASE_DEV, "rdflib": version}
    base = write(tmp_path / "base")
    head = write(tmp_path / "head", groups, runtime, dev, register)
    return base, head


# --- new direct dependencies ------------------------------------------------


def test_no_change_is_clean(tmp_path):
    base, head = write(tmp_path / "base"), write(tmp_path / "head")
    code, report = gate(tmp_path, base, head, base_world())
    assert code == 0
    assert "No new direct dependencies" in report


def test_missing_entry_blocks(tmp_path):
    w = base_world()
    base, head = add_rdflib(tmp_path, w)
    code, report = gate(tmp_path, base, head, w)
    assert code == 1
    assert "no entry in dependency-register.json for `rdflib` in `runtime`" in report


def test_complete_entry_passes(tmp_path):
    w = base_world()
    base, head = add_rdflib(tmp_path, w, register=[entry("rdflib", version="7.0")])
    code, report = gate(tmp_path, base, head, w)
    assert code == 0, report
    assert "**✓ `rdflib` in `runtime`**" in report
    assert "| maintained |" in report


def test_entry_contradicting_a_signal_blocks(tmp_path):
    w = base_world()
    base, head = add_rdflib(tmp_path, w, register=[entry("rdflib", version="7.0")], owners=1, github_owner="User")
    code, report = gate(tmp_path, base, head, w)
    assert code == 1
    assert "maintainers: the entry says it holds, but one owner, no organisation" in report


def test_holds_false_with_why_passes(tmp_path):
    w = base_world()
    e = entry("rdflib", version="7.0")
    e["criteria"]["maintainers"] = {"holds": False, "why": "One person publishes rdflib; we accept that for now."}
    base, head = add_rdflib(tmp_path, w, register=[e], owners=1, github_owner="User")
    code, report = gate(tmp_path, base, head, w)
    assert code == 0, report


def test_why_rules(tmp_path):
    w = base_world()
    e = entry("rdflib", version="7.0")
    e["criteria"]["needed"] = {"holds": True}
    e["criteria"]["footprint"]["why"] = WHY["licence"]
    base, head = add_rdflib(tmp_path, w, register=[e])
    code, report = gate(tmp_path, base, head, w)
    assert code == 1
    assert "needed: needs a why of at least 40 characters" in report
    assert "footprint: why is identical to the one for licence" in report


def test_assessed_major_must_be_locked_major(tmp_path):
    w = base_world()
    base, head = add_rdflib(tmp_path, w, register=[entry("rdflib", version="6.3")])
    code, report = gate(tmp_path, base, head, w)
    assert code == 1
    assert "different major than the locked `7.0`" in report


def test_required_field_blocks_even_with_replace_and_open_follow_up(tmp_path):
    w = base_world()
    w.issue(30)
    e = entry("rdflib", version="7.0", outcome="replace", followUp=30)
    e["criteria"]["maintained"] = {"holds": False, "why": "No GitHub repository to check; replacing it in #30."}
    base, head = add_rdflib(tmp_path, w, register=[e], repo=None)
    code, report = gate(tmp_path, base, head, w)
    assert code == 1
    assert "repository: PyPI's project_urls name no GitHub repository" in report


def test_required_field_blocks_an_override_too(tmp_path):
    w = base_world()
    w.issue(31)
    base, head = add_rdflib(tmp_path, w, register=[override_entry("rdflib", 31, version="7.0")], licence=None)
    code, report = gate(tmp_path, base, head, w)
    assert code == 1
    assert "licence: PyPI gives no licence that parses as SPDX" in report


def test_yanked_needs_replace_with_open_follow_up(tmp_path):
    w = base_world()
    w.issue(32)
    e = entry("rdflib", version="7.0")
    e["criteria"]["maintained"] = {"holds": False, "why": "The locked version was yanked; moving off it soon."}
    # Its yanked files are no wheel to install either.
    e["criteria"]["footprint"] = {"holds": False, "why": "Every file of the yanked version is yanked as well."}
    base, head = add_rdflib(tmp_path, w, register=[e], yanked=("7.0",))
    code, report = gate(tmp_path, base, head, w)
    assert code == 1
    assert "yanked: fails outright unless the outcome is replace with an open followUp" in report
    e2 = {**e, "outcome": "replace", "followUp": 32}
    base, head = add_rdflib(tmp_path / "2", w, register=[e2], yanked=("7.0",))
    code, report = gate(tmp_path, base, head, w)
    assert code == 0, report


def test_entry_repository_is_passed_to_gather(tmp_path):
    w = base_world()
    w.docs[f"{GH}/repos/elsewhere/rdflib"] = {"archived": True, "owner": {"type": "Organization"}}
    base, head = add_rdflib(tmp_path, w, register=[entry("rdflib", version="7.0", repository="elsewhere/rdflib")])
    code, report = gate(tmp_path, base, head, w)
    assert f"{GH}/repos/elsewhere/rdflib" in w.calls
    assert f"{GH}/repos/rdflib-org/rdflib" not in w.calls
    assert code == 1 and "repository archived" in report


def test_entry_repository_null_skips_github(tmp_path):
    w = base_world()
    e = entry("rdflib", version="7.0", repository=None, repositoryWhy="The source lives on a self-hosted forge.")
    e["criteria"]["maintained"] = {"holds": False, "why": "Not on GitHub, so archived cannot be checked here."}
    base, head = add_rdflib(tmp_path, w, register=[e])
    code, report = gate(tmp_path, base, head, w)
    assert not any(u.startswith(f"{GH}/repos/rdflib-org") for u in w.calls)
    assert code == 0, report


# --- issues ------------------------------------------------------------------


def test_override_with_open_issue_passes_with_warning(tmp_path):
    w = base_world()
    w.issue(40)
    base, head = add_rdflib(tmp_path, w, register=[override_entry("rdflib", 40, version="7.0")])
    code, report = gate(tmp_path, base, head, w)
    assert code == 0, report
    assert "warning: override: `needed for the release, assessed next week` (issue #40)" in report


def test_pull_request_number_as_issue_blocks(tmp_path):
    w = base_world()
    w.issue(41, pull_request=True)
    base, head = add_rdflib(tmp_path, w, register=[override_entry("rdflib", 41, version="7.0")])
    code, report = gate(tmp_path, base, head, w)
    assert code == 1
    assert "override issue #41 is a pull request, not an issue" in report


@pytest.mark.parametrize("state", ["closed", "missing"])
def test_closed_or_missing_issue_blocks(tmp_path, state):
    w = base_world()
    if state == "closed":
        w.issue(42, state="closed")
    base, head = add_rdflib(tmp_path, w, register=[override_entry("rdflib", 42, version="7.0")])
    code, report = gate(tmp_path, base, head, w)
    assert code == 1
    assert "override issue #42 is not open" in report


def test_issue_lookup_needs_github_repository(tmp_path):
    w = base_world()
    base, head = add_rdflib(tmp_path, w, register=[override_entry("rdflib", 40, version="7.0")])
    env = {k: v for k, v in PERSON.items() if k != "GITHUB_REPOSITORY"}
    code, report = gate(tmp_path, base, head, w, env=env)
    assert code == 2 and "GITHUB_REPOSITORY" in report


# --- register changes --------------------------------------------------------


def test_changed_register_entry_is_judged_without_requirements_change(tmp_path):
    w = base_world()
    w.package("fastapi", {"1.0": OLD}, owners=1, github_owner="User")
    stale = entry("fastapi")  # says maintainers holds; the evidence says one owner
    base = write(tmp_path / "base", register=[stale])
    same = write(tmp_path / "same", register=[stale])
    code, report = gate(tmp_path, base, same, w)
    assert code == 0, report  # unchanged entries are not re-judged
    edited = entry("fastapi")
    edited["criteria"]["needed"]["why"] = "FastAPI serves the whole API; nothing else would."
    head = write(tmp_path / "head", register=[edited])
    code, report = gate(tmp_path, base, head, w)
    assert code == 1
    assert "`fastapi` in `runtime`** (register entry changed)" in report
    assert "maintainers: the entry says it holds" in report


def test_added_register_entry_is_judged(tmp_path):
    w = base_world()
    base = write(tmp_path / "base")
    head = write(tmp_path / "head", register=[entry("fastapi"), entry("pytest", "dev", "8.0")])
    code, report = gate(tmp_path, base, head, w)
    assert code == 0, report
    assert "`fastapi` in `runtime`** (register entry added)" in report
    assert "`pytest` in `dev`** (register entry added)" in report


def test_entry_for_a_package_not_in_its_group_is_a_warning(tmp_path):
    w = base_world()
    base = write(tmp_path / "base")
    head = write(tmp_path / "head", register=[entry("pytest", "runtime", "8.0")])
    code, report = gate(tmp_path, base, head, w)
    assert code == 0
    assert "not a direct dependency of `runtime`" in report


# --- cooldown ----------------------------------------------------------------


def young_transitive(tmp_path, w, dev_only=False):
    w.package("anyio", {"4.0": OLD, "4.1": YOUNG})
    base = write(tmp_path / "base", runtime={**BASE_RUNTIME, "anyio": "4.0"}, dev={**BASE_DEV, "anyio": "4.0"})
    runtime = {**BASE_RUNTIME, "anyio": "4.0" if dev_only else "4.1"}
    head = write(tmp_path / "head", runtime=runtime, dev={**BASE_DEV, "anyio": "4.1"})
    return base, head


def test_review_focus_4_person_young_pin_blocks(tmp_path):
    w = base_world()
    base, head = young_transitive(tmp_path, w)
    code, report = gate(tmp_path, base, head, w)
    assert code == 1
    assert "`anyio` `4.1`: uploaded 2026-11-25, 3 days ago, under the 14-day cooldown (no exception)" in report


def test_review_focus_4_renovate_routine_young_pin_is_logged(tmp_path):
    w = base_world()
    w.pr(12, [{"name": "dependencies"}], [labelled("dependencies", "renovate[bot]")])
    base, head = young_transitive(tmp_path, w)
    code, report = gate(tmp_path, base, head, w, env=RENOVATE)
    assert code == 0, report
    assert "##### Cooldown exceptions" in report
    assert "`anyio` `4.1` — uploaded 2026-11-25, 3 days old — Renovate pull request" in report


def test_renovate_route_needs_a_pr_number(tmp_path):
    w = base_world()
    base, head = young_transitive(tmp_path, w)
    code, report = gate(tmp_path, base, head, w, env={**RENOVATE, "PR_NUMBER": "0"})
    assert code == 2 and "PR_NUMBER" in report


def test_cooldown_uses_earliest_file_upload(tmp_path):
    w = base_world()
    # The wheel came 3 days ago, the sdist 30 days ago: old enough.
    w.package("anyio", {"4.0": OLD, "4.1": [YOUNG, NOW - timedelta(days=30)]})
    base = write(tmp_path / "base", runtime={**BASE_RUNTIME, "anyio": "4.0"})
    head = write(tmp_path / "head", runtime={**BASE_RUNTIME, "anyio": "4.1"})
    code, report = gate(tmp_path, base, head, w)
    assert code == 0, report


def test_cooldown_falls_back_to_version_endpoint(tmp_path):
    w = base_world()
    w.package("anyio", {"4.0": OLD, "4.1": YOUNG}, release_key=False)
    base = write(tmp_path / "base", runtime={**BASE_RUNTIME, "anyio": "4.0"})
    head = write(tmp_path / "head", runtime={**BASE_RUNTIME, "anyio": "4.1"})
    code, report = gate(tmp_path, base, head, w)
    assert f"{PYPI}/pypi/anyio/4.1/json" in w.calls
    assert code == 1 and "3 days ago" in report


def test_cooldown_no_upload_time_blocks(tmp_path):
    w = base_world()
    w.package("anyio", {"4.0": OLD, "4.1": YOUNG})
    w.docs[f"{PYPI}/pypi/anyio/json"]["releases"]["4.1"] = []
    w.docs[f"{PYPI}/pypi/anyio/4.1/json"]["urls"] = []
    base = write(tmp_path / "base", runtime={**BASE_RUNTIME, "anyio": "4.0"})
    head = write(tmp_path / "head", runtime={**BASE_RUNTIME, "anyio": "4.1"})
    code, report = gate(tmp_path, base, head, w)
    assert code == 1 and "no upload time to check the cooldown against" in report


def test_cooldown_override_with_open_issue(tmp_path):
    w = base_world()
    w.issue(50)
    w.issue(51, pull_request=True)
    w.package("anyio", {"4.0": OLD, "4.1": YOUNG})
    reg = {
        "dependencies": [],
        "cooldownOverrides": [{"package": "anyio", "version": "4.1", "reason": "CVE fix", "issue": 50}],
    }
    base = write(tmp_path / "base", runtime={**BASE_RUNTIME, "anyio": "4.0"})
    head = write(tmp_path / "head", runtime={**BASE_RUNTIME, "anyio": "4.1"}, register=reg)
    code, report = gate(tmp_path, base, head, w)
    assert code == 0, report
    assert "override: `CVE fix` (#50)" in report
    reg["cooldownOverrides"][0]["issue"] = 51
    head = write(tmp_path / "head2", runtime={**BASE_RUNTIME, "anyio": "4.1"}, register=reg)
    code, report = gate(tmp_path, base, head, w)
    assert code == 1 and "override issue #51 is a pull request, not an issue" in report


def test_old_pins_pass_cooldown(tmp_path):
    w = base_world()
    w.package("anyio", {"4.0": OLD, "4.1": NOW - timedelta(days=14)})
    base = write(tmp_path / "base", runtime={**BASE_RUNTIME, "anyio": "4.0"})
    head = write(tmp_path / "head", runtime={**BASE_RUNTIME, "anyio": "4.1"})
    code, report = gate(tmp_path, base, head, w)
    assert code == 0, report
    assert "Every changed pin is old enough or excepted." in report


# --- Renovate security route --------------------------------------------------


def test_renovate_security_missing_entry_warns(tmp_path):
    w = base_world()
    w.pr(12, [{"name": "dependencies"}, {"name": "security"}], [labelled("security", "renovate[bot]")])
    base, head = add_rdflib(tmp_path, w)
    code, report = gate(tmp_path, base, head, w, env=RENOVATE)
    assert code == 0, report
    assert "Renovate security update with no register entry: still to assess" in report


def test_security_label_by_a_person_does_not_count(tmp_path):
    w = base_world()
    w.pr(12, [{"name": "security"}], [labelled("security", "someone")])
    base, head = add_rdflib(tmp_path, w)
    code, report = gate(tmp_path, base, head, w, env=RENOVATE)
    assert code == 1
    assert "no entry in dependency-register.json" in report


def test_persons_pr_never_asks_for_labels_even_with_a_renovate_security_label(tmp_path):
    w = base_world()
    w.pr(13, [{"name": "security"}], [labelled("security", "renovate[bot]")])
    base, head = add_rdflib(tmp_path, w)
    code, report = gate(tmp_path, base, head, w, env={**PERSON, "PR_NUMBER": "13"})
    assert code == 1
    assert not any("/labels" in u for u in w.calls)


def test_events_are_paged(tmp_path):
    w = base_world()
    noise = [labelled("dependencies", "renovate[bot]")] * 150
    w.pr(12, [{"name": "security"}], noise + [labelled("security", "renovate[bot]")])
    base, head = add_rdflib(tmp_path, w)
    code, report = gate(tmp_path, base, head, w, env=RENOVATE)
    assert code == 0, report
    assert any(u.endswith("/events?per_page=100&page=2") for u in w.calls)


def test_labels_polled_at_most_60_seconds(tmp_path):
    w = base_world()
    w.pr(12, [], [])
    base, head = young_transitive(tmp_path, w)
    sleeps = []
    code, report = gate(tmp_path, base, head, w, env=RENOVATE, sleep=sleeps.append)
    assert sum(sleeps) <= 60 and len(sleeps) >= 1
    assert code == 0  # routine Renovate: the young pin is logged


def test_labels_arriving_late_are_seen(tmp_path):
    w = base_world()
    w.pr(12, [[], [], [{"name": "security"}]], [labelled("security", "renovate[bot]")])
    base, head = add_rdflib(tmp_path, w)
    code, report = gate(tmp_path, base, head, w, env=RENOVATE)
    assert code == 0, report
    assert "Renovate security update" in report


# --- Review Focus 5: a requirements-dev.txt-only change -----------------------


def test_review_focus_5_dev_only_change(tmp_path):
    w = base_world()
    w.package("ruff", {"0.14.0": OLD, "0.14.1": YOUNG})
    w.package("black", {"25.1": OLD})
    w.pr(12, [{"name": "dependencies"}], [])
    base = write(tmp_path / "base")
    groups = {**BASE_GROUPS, "tools": ["ruff", "black"]}
    head = write(tmp_path / "head", groups, BASE_RUNTIME, {**BASE_DEV, "ruff": "0.14.1", "black": "25.1"})
    code, report = gate(tmp_path, base, head, w, env=RENOVATE)
    assert code == 1
    assert "no entry in dependency-register.json for `black` in `tools`" in report
    assert "`ruff` `0.14.1` — uploaded 2026-11-25, 3 days old — Renovate pull request" in report
    # The tool's locked version comes from requirements-dev.txt.
    assert f"{PYPI}/pypi/black/25.1/json" in w.calls
    head = write(
        tmp_path / "head2",
        groups,
        BASE_RUNTIME,
        {**BASE_DEV, "ruff": "0.14.1", "black": "25.1"},
        register=[entry("black", "tools", "25.1")],
    )
    code, report = gate(tmp_path, base, head, w, env=RENOVATE)
    assert code == 0, report


def test_new_dependency_without_a_pin_blocks(tmp_path):
    w = base_world()
    base = write(tmp_path / "base")
    head = write(tmp_path / "head", {**BASE_GROUPS, "runtime": ["fastapi", "rdflib"]}, register=[entry("rdflib")])
    code, report = gate(tmp_path, base, head, w)
    assert code == 1
    assert "`rdflib` has no pin in `requirements.txt`" in report


# --- exit 2 and --check-register ---------------------------------------------


def test_fetch_failure_is_exit_2_with_could_not_run_section(tmp_path):
    w = base_world()
    base, head = add_rdflib(tmp_path, w)
    w.docs[f"{PYPI}/pypi/rdflib/json"] = (503, {}, b"")
    code, report = gate(tmp_path, base, head, w)
    assert code == 2
    assert "**✗ The dependency gate could not run** — the check fails." in report
    assert "pypi.org answered 503" in report


def test_unexpected_exception_is_exit_2(tmp_path, monkeypatch):
    w = base_world()
    base, head = add_rdflib(tmp_path, w)

    def boom(*a, **k):
        raise ValueError("surprise")

    monkeypatch.setattr(D, "evaluate", boom)
    code, report = gate(tmp_path, base, head, w)
    assert code == 2 and "ValueError: surprise" in report


def test_malformed_head_register_is_exit_2(tmp_path):
    w = base_world()
    base = write(tmp_path / "base")
    head = write(tmp_path / "head")
    (head / "dependency-register.json").write_text('{"dependencies": [{"name": "x"}]}', encoding="utf-8")
    code, report = gate(tmp_path, base, head, w)
    assert code == 2 and "manifest missing" in report


def check(tmp_path, text=None, capsys=None):
    path = tmp_path / "dependency-register.json"
    if text is not None:
        path.write_text(text, encoding="utf-8")
    return D.main(["--check-register", "--register", str(path)], env={}, fetch=World())


def test_check_register_absent_is_a_note(tmp_path, capsys):
    assert check(tmp_path) == 0
    assert "no dependency-register.json at" in capsys.readouterr().out


def test_check_register_valid(tmp_path, capsys):
    assert check(tmp_path, json.dumps({"dependencies": [entry("fastapi")]})) == 0
    assert "1 entries, 0 cooldown overrides" in capsys.readouterr().out


@pytest.mark.parametrize(
    "text", ["{", '{"dependencies": {}}', '{"dependencies": [{"name": "x", "manifest": "runtime"}]}']
)
def test_check_register_malformed_is_exit_2(tmp_path, text, capsys):
    assert check(tmp_path, text) == 2
    assert "dependency-register.json" in capsys.readouterr().err


def test_check_register_makes_no_network_call(tmp_path):
    w = World()
    path = tmp_path / "r.json"
    path.write_text(json.dumps({"dependencies": [entry("fastapi")]}), encoding="utf-8")
    assert D.main(["--check-register", "--register", str(path)], env={}, fetch=w) == 0
    assert w.calls == []


# --- combine_comment ---------------------------------------------------------


def test_combine_comment_marker_once_and_verdicts_first():
    review = "#### Requirements diff\n\n**✓ No blocking findings.**\n\n<!-- requirements-review -->\n"
    gate_text = "#### Dependency gate\n\n- ✗ something\n"
    text = D.combine_comment([("Requirements diff", review), ("Dependency gate", gate_text)], [0, 1])
    assert text.count(D.MARKER) == 1
    assert text.startswith(D.MARKER)
    head = text.split("#### Requirements diff", 1)[0]
    assert "- ✓ Requirements diff: no blocking findings." in head
    assert "- ✗ Dependency gate: blocks — the check fails." in head
    assert text.index("#### Requirements diff") < text.index("#### Dependency gate")


def test_combine_comment_could_not_run_verdict():
    text = D.combine_comment([("Requirements diff", "x"), ("Dependency gate", "y")], [0, 2])
    assert "- ✗ Dependency gate: could not run — the check fails." in text


def test_combine_comment_truncation_keeps_verdict_list():
    huge = "#### Requirements diff\n\n<details>\n<summary>Added</summary>\n\n" + "- `pkg` `1.0`\n" * 20000
    text = D.combine_comment([("Requirements diff", huge), ("Dependency gate", "#### Dependency gate\n")], [1, 0])
    assert len(text) <= D.COMMENT_LIMIT
    assert text.startswith(D.MARKER)
    assert "- ✗ Requirements diff: blocks — the check fails." in text
    assert "- ✓ Dependency gate: no blocking findings." in text
    assert "Cut to fit a GitHub comment" in text
    assert text.count("<details>") == text.count("</details>")
    full = D.combine_comment([("Requirements diff", huge)], [1], limit=None)
    assert len(full) > D.COMMENT_LIMIT


def test_combine_cli(tmp_path):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text("#### Requirements diff\n\nfine\n", encoding="utf-8")
    b.write_text("#### Dependency gate\n\nblocked\n", encoding="utf-8")
    comment, summary = tmp_path / "c.md", tmp_path / "s.md"
    code = D.main(
        ["--combine", str(a), "0", str(b), "1", "--out", str(comment), "--summary", str(summary)], env={}, fetch=World()
    )
    assert code == 1  # the worst status
    text = comment.read_text(encoding="utf-8")
    assert "- ✗ Dependency gate: blocks" in text and "blocked" in text
    assert summary.read_text(encoding="utf-8") == text


def test_combine_cli_missing_part_is_exit_2_with_a_comment(tmp_path):
    comment = tmp_path / "c.md"
    code = D.main(["--combine", str(tmp_path / "nope.md"), "0", "--out", str(comment)], env={}, fetch=World())
    assert code == 2
    text = comment.read_text(encoding="utf-8")
    assert text.count(D.MARKER) == 1 and "could not run" in text


def test_combine_cli_failure_also_writes_the_summary(tmp_path):
    comment, summary = tmp_path / "c.md", tmp_path / "s.md"
    argv = ["--combine", str(tmp_path / "nope.md"), "0", "--out", str(comment), "--summary", str(summary)]
    assert D.main(argv, env={}, fetch=World()) == 2
    assert summary.read_text(encoding="utf-8") == comment.read_text(encoding="utf-8")
    assert "could not run" in summary.read_text(encoding="utf-8")


# --- register text in the table -----------------------------------------------


def why_report(tmp_path, why):
    w = base_world()
    e = entry("rdflib", version="7.0")
    e["criteria"]["needed"]["why"] = why
    base, head = add_rdflib(tmp_path, w, register=[e])
    code, report = gate(tmp_path, base, head, w)
    assert code == 0, report
    return report


def test_why_with_html_comment_cannot_hide_sections(tmp_path):
    report = why_report(tmp_path, "Needed for TOML output <!-- and everything after it is hidden")
    assert "<!--" not in report
    assert "&lt;!-- and everything after it is hidden" in report
    assert "##### Cooldown" in report


def test_why_with_details_tags_cannot_upset_the_details_count(tmp_path):
    report = why_report(tmp_path, "Needed for TOML output </details><details> & more text here")
    assert "<details>" not in report and "</details>" not in report
    assert "&lt;/details&gt;&lt;details&gt; &amp; more" in report
    text = D.combine_comment([("Dependency gate", report)], [0])
    assert text.count("<details>") == text.count("</details>") == 0


def test_cell_escapes_html_and_pipes():
    assert D.cell("a <b> & c | d\ne") == "a &lt;b&gt; &amp; c \\| d e"


# --- moving between groups -----------------------------------------------------


def test_moving_ruff_from_tools_to_dev_needs_a_dev_entry(tmp_path):
    w = base_world()
    tools_entry = entry("ruff", "tools", "0.14.0")
    base = write(tmp_path / "base", register=[tools_entry])
    groups = {**BASE_GROUPS, "dev": ["pytest", "ruff"], "tools": []}
    head = write(tmp_path / "head", groups, register=[tools_entry])
    code, report = gate(tmp_path, base, head, w)
    assert code == 1
    assert "no entry in dependency-register.json for `ruff` in `dev`" in report
    assert "**✗ `ruff` in `dev`** (new direct dependency)" in report
