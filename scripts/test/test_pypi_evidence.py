"""Tests for scripts/pypi_evidence.py. No network: PyPI answers come from
trimmed real responses in fixtures/pypi/ (fetched 2026-11-28), GitHub answers
are written here, and every fetch goes through a fake."""

import http.client
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("pypi_evidence", SCRIPTS / "pypi_evidence.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)
import gate_common as G  # noqa: E402

FIX = HERE / "fixtures" / "pypi"
NOW = datetime(2026, 11, 28, tzinfo=UTC)
POLICY = G.parse_policy((SCRIPTS.parent / "serve_api" / "lockfile-review.json").read_text(encoding="utf-8"))
LOCKED = {"fastapi": "0.142.2", "lxml": "6.1.3", "vulture": "2.16", "bandit": "1.9.4"}
GITHUB = {
    "fastapi/fastapi": {"archived": False, "owner": {"type": "Organization"}},
    "lxml/lxml": {"archived": False, "owner": {"type": "Organization"}},
    "jendrikseipp/vulture": {"archived": False, "owner": {"type": "User"}},
    "PyCQA/bandit": {"archived": False, "owner": {"type": "Organization"}},
}


def fixture(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


class FakeFetch:
    """A fetch(url, headers, timeout) -> (status, headers, body) over a URL map.
    `overrides` replaces or adds documents; a URL not in the map answers 404."""

    def __init__(self, overrides=None, github=None):
        self.docs = {}
        for name, version in LOCKED.items():
            self.docs[f"https://pypi.org/pypi/{name}/json"] = fixture(f"{name}.project.json")
            self.docs[f"https://pypi.org/pypi/{name}/{version}/json"] = fixture(f"{name}-{version}.json")
            self.docs[f"https://pypi.org/simple/{name}/"] = fixture(f"{name}.simple.json")
        self.docs["https://pypi.org/pypi/bandit/1.6.3/json"] = fixture("bandit-1.6.3.json")
        self.docs["https://pypi.org/integrity/bandit/1.9.4/bandit-1.9.4-py3-none-any.whl/provenance"] = fixture(
            "bandit-1.9.4-provenance.json"
        )
        for repo, doc in (GITHUB if github is None else github).items():
            self.docs[f"https://api.github.com/repos/{repo}"] = doc
        self.docs.update(overrides or {})
        self.calls = []

    def __call__(self, url, headers, timeout):
        self.calls.append((url, headers))
        doc = self.docs.get(url)
        if doc is None:
            return 404, {}, b'{"message": "Not Found"}'
        if isinstance(doc, tuple):
            return doc
        return 200, {}, json.dumps(doc).encode()


def gather(name, version=None, fetch=None, **kw):
    return E.gather(name, version or LOCKED[name], fetch=fetch or FakeFetch(), token="t", **kw)


def assessed(**criteria):
    holds = {c: {"holds": True} for c in G.CRITERIA}
    holds.update(criteria)
    return {"name": "x", "manifest": "runtime", "status": "assessed", "criteria": holds, "outcome": "keep"}


# --- fetch_json ------------------------------------------------------------


class Scripted:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0

    def __call__(self, url, headers, timeout):
        self.calls += 1
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


def test_fetch_json_retries_429_twice_then_succeeds():
    waits = []
    f = Scripted([(429, {"Retry-After": "3"}, b""), (503, {}, b""), (200, {}, b'{"ok": 1}')])
    assert E.fetch_json("https://pypi.org/x", fetch=f, sleep=waits.append) == {"ok": 1}
    assert f.calls == 3
    assert waits == [3, 5]


def test_fetch_json_gives_up_after_three():
    f = Scripted([(429, {}, b"")] * 3)
    with pytest.raises(E.FetchError) as err:
        E.fetch_json("https://pypi.org/x", fetch=f, sleep=lambda s: None)
    assert err.value.status == 429
    assert f.calls == 3


def test_fetch_json_retry_after_capped_at_60():
    waits = []
    f = Scripted([(429, {"retry-after": "3600"}, b""), (200, {}, b"{}")])
    E.fetch_json("https://pypi.org/x", fetch=f, sleep=waits.append)
    assert waits == [60]


def test_fetch_json_retries_timeouts():
    f = Scripted([TimeoutError("slow"), (200, {}, b'{"a": 1}')])
    assert E.fetch_json("https://pypi.org/x", fetch=f, sleep=lambda s: None) == {"a": 1}


def test_fetch_json_retries_http_exceptions():
    f = Scripted([http.client.IncompleteRead(b"x"), http.client.RemoteDisconnected("gone"), (200, {}, b"{}")])
    assert E.fetch_json("https://pypi.org/x", fetch=f, sleep=lambda s: None) == {}
    f = Scripted([http.client.RemoteDisconnected("gone")] * 3)
    with pytest.raises(E.FetchError) as err:
        E.fetch_json("https://pypi.org/x", fetch=f, sleep=lambda s: None)
    assert err.value.status is None


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "NaN"])
def test_fetch_json_non_finite_retry_after_uses_default_wait(value):
    waits = []
    f = Scripted([(429, {"Retry-After": value}, b""), (200, {}, b"{}")])
    E.fetch_json("https://pypi.org/x", fetch=f, sleep=waits.append)
    assert waits == [2]
    assert E.retry_after(value) is None


@pytest.mark.parametrize("body", [b"[1]", b'"text"', b"null", b"3"])
def test_fetch_json_non_object_body_is_fetch_error(body):
    with pytest.raises(E.FetchError) as err:
        E.fetch_json("https://pypi.org/x", fetch=Scripted([(200, {}, body)]), sleep=lambda s: None)
    assert err.value.status == 200


def test_gather_non_object_github_answer_is_fetch_error():
    fetch = FakeFetch({"https://api.github.com/repos/fastapi/fastapi": (200, {}, b"[]")})
    with pytest.raises(E.FetchError):
        gather("fastapi", fetch=fetch)


def test_fetch_json_404_not_retried():
    f = Scripted([(404, {}, b"")])
    with pytest.raises(E.FetchError) as err:
        E.fetch_json("https://pypi.org/x", fetch=f, sleep=lambda s: None)
    assert err.value.status == 404
    assert f.calls == 1


def test_fetch_json_bad_json_is_fetch_error():
    with pytest.raises(E.FetchError):
        E.fetch_json("https://pypi.org/x", fetch=Scripted([(200, {}, b"<html>")]), sleep=lambda s: None)


# --- resolve_licence -------------------------------------------------------


def test_licence_expression_first():
    assert E.resolve_licence(fixture("fastapi-0.142.2.json")["info"]) == ("MIT", "license_expression")


def test_licence_field_when_it_parses_as_spdx():
    assert E.resolve_licence(fixture("lxml-6.1.3.json")["info"]) == ("BSD-3-Clause", "license")
    assert E.resolve_licence(fixture("bandit-1.9.4.json")["info"]) == ("Apache-2.0", "license")


def test_review_focus_2_vulture_licence_text_falls_to_classifier():
    info = fixture("vulture-2.16.json")["info"]
    assert not E.is_spdx(info["license"])
    assert E.resolve_licence(info) == ("MIT", "classifier")


def test_review_focus_2_neither_needs_entry_licence():
    ev = gather("vulture")
    ev.licence, ev.licence_source = E.resolve_licence({**fixture("vulture-2.16.json")["info"], "classifiers": []})
    assert ev.licence is None
    s = E.signals(ev, assessed(), NOW, POLICY)
    assert s["licence"]
    assert any("`licence`" in r for r in s["required"])
    ok = E.signals(ev, {**assessed(), "licence": "MIT"}, NOW, POLICY)
    assert ok["licence"] is None
    assert not any("licence" in r for r in ok["required"])


@pytest.mark.parametrize(
    "classifier,spdx",
    [
        ("License :: OSI Approved :: MIT License", "MIT"),
        ("License :: OSI Approved :: Apache Software License", "Apache-2.0"),
        ("License :: OSI Approved :: ISC License (ISCL)", "ISC"),
        ("License :: OSI Approved :: Python Software Foundation License", "PSF-2.0"),
        ("License :: OSI Approved :: BSD License", None),
    ],
)
def test_classifier_mapping(classifier, spdx):
    got = E.resolve_licence({"license": None, "license_expression": None, "classifiers": [classifier]})
    assert got == ((spdx, "classifier") if spdx else (None, None))


def test_two_mapped_classifiers_are_ambiguous():
    info = {
        "classifiers": ["License :: OSI Approved :: MIT License", "License :: OSI Approved :: Apache Software License"]
    }
    assert E.resolve_licence(info) == (None, None)


@pytest.mark.parametrize(
    "text,ok",
    [
        ("MIT", True),
        ("mit", True),
        ("Apache-2.0 OR MIT", True),
        ("(MIT AND BSD-3-Clause) OR Apache-2.0", True),
        ("GPL-2.0-or-later WITH Classpath-exception-2.0", True),
        ("LicenseRef-Proprietary", True),
        ("MIT License", False),
        ("BSD", False),
        ("MIT AND", False),
        ("(MIT", False),
        ("", False),
        (None, False),
    ],
)
def test_is_spdx(text, ok):
    assert E.is_spdx(text) is ok


def test_licence_canonical_case():
    assert E.resolve_licence({"license": "apache-2.0 or mit"}) == ("Apache-2.0 OR MIT", "license")


# --- gather ----------------------------------------------------------------


def test_gather_fastapi():
    ev = gather("fastapi")
    assert ev.status == "active"
    assert ev.yanked is False
    assert ev.owners == 1 and ev.organisation is None
    assert ev.licence == "MIT"
    assert ev.repository == "fastapi/fastapi" and ev.archived is False and ev.github_org is True
    assert ev.pure_wheel is True and ev.target_wheel == "fastapi-0.142.2-py3-none-any.whl"
    assert ev.attested_by is None
    assert ev.upload_time("0.142.2") == datetime(2026, 9, 30, 9, 51, 9, 800102, tzinfo=UTC)
    assert ev.last_release > ev.upload_time("0.142.2")


def test_gather_sends_github_token_and_simple_accept():
    f = FakeFetch()
    gather("fastapi", fetch=f)
    headers = dict(f.calls)
    assert headers["https://api.github.com/repos/fastapi/fastapi"]["Authorization"] == "Bearer t"
    assert headers["https://pypi.org/simple/fastapi/"]["Accept"] == "application/vnd.pypi.simple.v1+json"


def test_gather_bandit_attestation_and_source_code_url():
    ev = gather("bandit")
    assert ev.repository == "PyCQA/bandit"
    assert ev.organisation == "PyCQA" and ev.owners == 3
    assert ev.attested_by == "GitHub PyCQA/bandit, workflow publish-to-pypi.yml"


def test_gather_last_release_skips_yanked_files():
    ev = gather("bandit")
    assert ev.last_release == datetime(2026, 2, 25, 6, 44, 15, 503849, tzinfo=UTC)


def test_gather_lxml_target_wheel_not_pure():
    ev = gather("lxml")
    assert ev.pure_wheel is False
    assert ev.target_wheel == "lxml-6.1.3-cp314-cp314-manylinux2014_x86_64.manylinux_2_17_x86_64.whl"
    assert E.signals(ev, assessed(), NOW, POLICY)["footprint"] is None


def test_lxml_without_target_wheel_builds_from_source():
    version = fixture("lxml-6.1.3.json")
    version["urls"] = [
        u for u in version["urls"] if not ("cp314-cp314-manylinux" in u["filename"] and "x86_64" in u["filename"])
    ]
    ev = gather("lxml", fetch=FakeFetch({"https://pypi.org/pypi/lxml/6.1.3/json": version}))
    assert ev.target_wheel is None
    assert "builds from source" in E.signals(ev, assessed(), NOW, POLICY)["footprint"]


@pytest.mark.parametrize(
    "filename,ok",
    [
        ("x-1-py3-none-any.whl", True),
        ("x-1-py2.py3-none-any.whl", True),
        ("x-1-cp314-cp314-manylinux_2_17_x86_64.whl", True),
        ("x-1-cp314-cp314-manylinux1_x86_64.whl", True),
        ("x-1-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", True),
        ("x-1-cp314-cp314t-manylinux_2_17_x86_64.whl", False),
        ("x-1-cp314-cp314-manylinux_2_17_aarch64.whl", False),
        ("x-1-cp314-cp314-musllinux_1_2_x86_64.whl", False),
        ("x-1-cp314-cp314-manylinux_2_39_x86_64.whl", False),
        ("x-1-cp313-cp313-manylinux_2_17_x86_64.whl", False),
        ("x-1-py2-none-any.whl", False),
        ("x-1.tar.gz", False),
    ],
)
def test_target_compatible(filename, ok):
    assert E.target_compatible(filename) is ok


def test_review_focus_1_docs_site_urls_need_repository_field():
    project = fixture("bandit.project.json")
    version = fixture("bandit-1.9.4.json")
    docs_only = {"Documentation": "https://bandit.readthedocs.io/", "Homepage": "https://bandit.readthedocs.io/"}
    version["info"]["project_urls"] = docs_only
    project["info"]["project_urls"] = docs_only
    fetch = FakeFetch(
        {"https://pypi.org/pypi/bandit/json": project, "https://pypi.org/pypi/bandit/1.9.4/json": version}
    )
    ev = gather("bandit", fetch=fetch)
    assert ev.repository is None
    assert ev.archived is None
    assert not any("api.github.com" in u for u, _ in fetch.calls)
    s = E.signals(ev, assessed(), NOW, POLICY)
    assert any("`repository`" in r for r in s["required"])
    assert s["maintained"]


def test_entry_repository_overrides_project_urls():
    fetch = FakeFetch(github={**GITHUB, "PyCQA/bandit-fork": {"archived": True, "owner": {"type": "User"}}})
    ev = gather("bandit", fetch=fetch, repository="PyCQA/bandit-fork")
    assert ev.repository == "PyCQA/bandit-fork" and ev.archived is True
    s = E.signals(ev, {**assessed(), "repository": "PyCQA/bandit-fork"}, NOW, POLICY)
    assert s["fatal"] == "repository archived"
    assert not s["required"]


def test_entry_repository_null_skips_github():
    fetch = FakeFetch()
    ev = gather("bandit", fetch=fetch, repository=None)
    assert ev.repository is None and ev.archived is None
    assert not any("api.github.com" in u for u, _ in fetch.calls)
    s = E.signals(ev, {**assessed(), "repository": None, "repositoryWhy": "y" * 40}, NOW, POLICY)
    assert not s["required"]
    assert "repository not checked" in s["maintained"]


def test_github_404_is_evidence():
    ev = gather("fastapi", fetch=FakeFetch(github={}))
    assert ev.archived is None and ev.repo_note == "repository not found"
    assert "repository not checked (repository not found)" in E.signals(ev, assessed(), NOW, POLICY)["maintained"]


def test_github_500_is_fetch_error():
    fetch = FakeFetch({"https://api.github.com/repos/fastapi/fastapi": (500, {}, b"")})
    with pytest.raises(E.FetchError):
        E.gather("fastapi", "0.142.2", fetch=fetch, token="t", sleep=lambda s: None)


def test_pypi_404_is_fetch_error():
    with pytest.raises(E.FetchError):
        gather("fastapi", "9.9.9")


def test_integrity_404_means_no_attestation():
    simple = fixture("bandit.simple.json")
    for f in simple["files"]:
        if f["provenance"]:
            f["provenance"] = "https://pypi.org/integrity/bandit/1.9.4/missing/provenance"
    ev = gather("bandit", fetch=FakeFetch({"https://pypi.org/simple/bandit/": simple}))
    assert ev.attested_by is None


# --- signals ---------------------------------------------------------------


def test_clean_signals_for_bandit():
    s = E.signals(gather("bandit"), assessed(), NOW, POLICY)
    assert s == {
        "maintained": None,
        "maintainers": None,
        "licence": None,
        "footprint": None,
        "fatal": None,
        "required": [],
    }


def test_one_owner_github_organisation_clears_maintainers():
    # fastapi: one PyPI owner and no PyPI organisation, but an organisation
    # owns fastapi/fastapi on GitHub.
    ev = gather("fastapi")
    assert ev.owners == 1 and ev.organisation is None and ev.github_org is True
    assert E.signals(ev, assessed(), NOW, POLICY)["maintainers"] is None


def test_one_owner_github_user_is_maintainers_signal():
    ev = gather("vulture")
    assert ev.owners == 1 and ev.organisation is None and ev.github_org is False
    assert E.signals(ev, assessed(), NOW, POLICY)["maintainers"] == "one owner, no organisation"


def test_one_owner_github_not_checked_is_maintainers_signal():
    ev = gather("fastapi", fetch=FakeFetch(github={}))
    assert ev.github_org is None
    assert E.signals(ev, assessed(), NOW, POLICY)["maintainers"] == "one owner, organisation not checked"
    ev = gather("vulture", repository=None)
    assert E.signals(ev, assessed(), NOW, POLICY)["maintainers"] == "one owner, organisation not checked"


def test_github_answer_without_fields_is_not_checked():
    fetch = FakeFetch(github={"fastapi/fastapi": {"full_name": "fastapi/fastapi"}})
    ev = gather("fastapi", fetch=fetch)
    assert ev.archived is None and ev.github_org is None
    s = E.signals(ev, assessed(), NOW, POLICY)
    assert "repository not checked" in s["maintained"]
    assert s["maintainers"] == "one owner, organisation not checked"
    fetch = FakeFetch(github={"fastapi/fastapi": {"archived": "no", "owner": {"type": None}}})
    ev = gather("fastapi", fetch=fetch)
    assert ev.archived is None and ev.github_org is None


def test_unparseable_licence_expression_does_not_fall_through():
    info = {
        "license_expression": "MIT AND HPND-sell-variant",
        "license": "MIT",
        "classifiers": ["License :: OSI Approved :: MIT License"],
    }
    assert E.resolve_licence(info) == (None, "license_expression")
    version = fixture("vulture-2.16.json")
    version["info"] = {**version["info"], **info}
    ev = gather("vulture", fetch=FakeFetch({"https://pypi.org/pypi/vulture/2.16/json": version}))
    assert ev.licence is None and ev.licence_source == "license_expression"
    assert "license_expression `MIT AND HPND-sell-variant` not recognised" in ev.licence_note
    s = E.signals(ev, assessed(), NOW, POLICY)
    assert "not recognised" in s["licence"]
    assert any("`licence` field" in r and "not recognised" in r for r in s["required"])
    ok = E.signals(ev, {**assessed(), "licence": "MIT"}, NOW, POLICY)
    assert ok["licence"] is None and not ok["required"]


def test_empty_licence_expression_falls_through():
    info = {"license_expression": "  ", "license": "MIT"}
    assert E.resolve_licence(info) == ("MIT", "license")


def test_entry_licence_unknown_id_names_spdx_ids():
    ev = gather("vulture")
    ev.licence, ev.licence_source = None, None
    s = E.signals(ev, {**assessed(), "licence": "MIT AND HPND-sell-variant"}, NOW, POLICY)
    assert any(
        "`HPND-sell-variant` is not an SPDX id this gate knows; if spdx.org/licenses lists it, add it to SPDX_IDS" in r
        for r in s["required"]
    )
    # Prose words get the same neutral wording: no claim that they are ids.
    s = E.signals(ev, {**assessed(), "licence": "BSD"}, NOW, POLICY)
    assert any("`BSD` is not an SPDX id this gate knows; if spdx.org/licenses lists it" in r for r in s["required"])
    s = E.signals(ev, {**assessed(), "licence": "GPLv3 AND UNKNOWN"}, NOW, POLICY)
    assert any("`GPLv3`, `UNKNOWN` are not SPDX ids this gate knows" in r for r in s["required"])
    assert E.unknown_ids("MIT License") == []
    assert E.unknown_ids("MIT") == []


def test_register_rejects_repository_without_exactly_one_slash():
    for repo in ("PyCQA", "PyCQA/bandit/extra", "https://github.com/PyCQA/bandit"):
        doc = {"dependencies": [{**assessed(), "assessed": {"version": "1.0"}, "repository": repo}]}
        doc["dependencies"][0]["criteria"]["needed"]["why"] = "w" * 40
        with pytest.raises(G.InputError, match="repository must be owner/name"):
            G.parse_register(json.dumps(doc))


def test_ownership_unavailable_is_maintainers_signal():
    ev = gather("bandit")
    ev.owners = None
    assert "not available" in E.signals(ev, assessed(), NOW, POLICY)["maintainers"]


def test_no_release_in_13_months_is_maintained_signal():
    ev = gather("vulture")
    later = datetime(2027, 4, 26, tzinfo=UTC)
    assert "no release in 13 months" in E.signals(ev, assessed(), later, POLICY)["maintained"]
    assert E.signals(ev, assessed(), NOW, POLICY)["maintained"] is None


def test_upload_times_unavailable_is_maintained_signal():
    ev = gather("vulture")
    ev.last_release = None
    assert "no release date" in E.signals(ev, assessed(), NOW, POLICY)["maintained"]


@pytest.mark.parametrize("status", ["archived", "deprecated", "quarantined"])
def test_status_not_active_is_fatal(status):
    simple = fixture("bandit.simple.json")
    simple["project-status"] = {"status": status}
    ev = gather("bandit", fetch=FakeFetch({"https://pypi.org/simple/bandit/": simple}))
    s = E.signals(ev, assessed(), NOW, POLICY)
    assert s["fatal"] == f"project status `{status}`"
    assert status in s["maintained"]


def test_status_is_a_code_span():
    simple = fixture("bandit.simple.json")
    simple["project-status"] = {"status": "archived`\n**✓ approved**"}
    ev = gather("bandit", fetch=FakeFetch({"https://pypi.org/simple/bandit/": simple}))
    s = E.signals(ev, assessed(), NOW, POLICY)
    assert s["fatal"] == "project status `archived' **✓ approved**`"


@pytest.mark.parametrize("status", [5, True, ["archived"], {"x": 1}])
def test_status_not_a_string_is_missing(status):
    simple = fixture("bandit.simple.json")
    simple["project-status"] = {"status": status}
    ev = gather("bandit", fetch=FakeFetch({"https://pypi.org/simple/bandit/": simple}))
    assert ev.status is None
    s = E.signals(ev, assessed(), NOW, POLICY)
    assert s["fatal"] is None
    assert "project status not available" in s["maintained"]


def test_status_missing_is_maintained_signal_not_fatal():
    simple = fixture("bandit.simple.json")
    del simple["project-status"]
    ev = gather("bandit", fetch=FakeFetch({"https://pypi.org/simple/bandit/": simple}))
    assert ev.status is None
    s = E.signals(ev, assessed(), NOW, POLICY)
    assert s["fatal"] is None
    assert "project status not available" in s["maintained"]


def test_review_focus_3_yanked_locked_version_is_fatal():
    ev = gather("bandit", "1.6.3")
    assert ev.yanked is True
    assert "dropped py2" in ev.yanked_reason
    s = E.signals(ev, assessed(), NOW, POLICY)
    assert s["fatal"].startswith("locked version `1.6.3` yanked")
    assert "yanked" in s["maintained"]
    # The exception (outcome replace with an open follow-up) is the gate's,
    # as in the npm gate: signals keep the fatal either way.
    assert E.signals(ev, {**assessed(), "outcome": "replace", "followUp": 7}, NOW, POLICY)["fatal"]


def test_licence_off_allow_list():
    ev = gather("bandit")
    ev.licence = "MPL-2.0"
    assert E.signals(ev, assessed(), NOW, POLICY)["licence"] == "licence `MPL-2.0` not on the allow-list"


@pytest.mark.parametrize(
    "expr,ok",
    [
        ("MIT", True),
        ("MIT OR GPL-3.0-only", True),
        ("MIT AND GPL-3.0-only", False),
        ("(Apache-2.0 OR MIT) AND BSD-3-Clause", True),
        ("GPL-2.0-only WITH Classpath-exception-2.0", False),
    ],
)
def test_licence_allowed(expr, ok):
    assert E.licence_allowed(expr, POLICY.allow_licenses) is ok


def test_entry_licence_not_spdx_is_required():
    ev = gather("vulture")
    ev.licence = None
    s = E.signals(ev, {**assessed(), "licence": "MIT License"}, NOW, POLICY)
    assert any("not an SPDX expression" in r for r in s["required"])


def test_signals_without_entry():
    s = E.signals(gather("bandit"), None, NOW, POLICY)
    assert s["fatal"] is None and s["required"] == []


def test_months_between():
    a = datetime(2025, 11, 28, tzinfo=UTC)
    assert E.months_between(a, datetime(2026, 11, 28, tzinfo=UTC)) == 12
    assert E.months_between(a, datetime(2026, 11, 27, tzinfo=UTC)) == 11
