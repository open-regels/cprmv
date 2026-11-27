"""Tests for scripts/write-sbom.py. No network: the CycloneDX tool's output is a
fixture, and the project is a temporary directory. One test runs the real tool
when it is installed."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "write-sbom.py"
spec = importlib.util.spec_from_file_location("write_sbom", SCRIPT)
W = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W)

REPO = SCRIPT.parent.parent


def raw_doc(extra_component=None):
    """What `cyclonedx-py requirements --output-reproducible` returns, cut down:
    line-numbered bom-refs, a description quoting the line, a tool entry."""
    comps = [
        {
            "bom-ref": "requirements-L20",
            "description": "requirements line 20: zeta==2.0",
            "name": "zeta",
            "purl": "pkg:pypi/zeta@2.0",
            "type": "library",
            "version": "2.0",
        },
        {
            "bom-ref": "requirements-L7",
            "description": "requirements line 7: alpha==1.0",
            "name": "alpha",
            "purl": "pkg:pypi/alpha@1.0",
            "type": "library",
            "version": "1.0",
        },
    ]
    if extra_component:
        comps.append(extra_component)
    return {
        "$schema": "http://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": "urn:uuid:11111111-1111-1111-1111-111111111111",
        "version": 1,
        "metadata": {
            "timestamp": "2026-11-27T10:00:00+00:00",
            "tools": {"components": [{"name": "cyclonedx-py", "version": "8.0.1"}]},
            "component": {"bom-ref": "root-component", "name": "x", "type": "application"},
        },
        "components": comps,
        "dependencies": [{"ref": "requirements-L20"}, {"ref": "requirements-L7"}],
    }


@pytest.fixture
def state():
    return {"doc": raw_doc()}


@pytest.fixture
def repo(tmp_path, monkeypatch, state):
    """A project root with a pyproject and a requirements file, and the tool
    replaced by the fixture. `state` lets a test change what the tool returns."""
    (tmp_path / "serve_api").mkdir()
    (tmp_path / "serve_api" / "pyproject.toml").write_text(
        '[project]\nname = "cprmv"\nversion = "9.9.9"\n', encoding="utf-8"
    )
    (tmp_path / "serve_api" / "requirements.txt").write_text("", encoding="utf-8")
    monkeypatch.setattr(W, "run_tool", lambda root: json.loads(json.dumps(state["doc"])))
    return tmp_path


def sbom_file(repo):
    return repo / "docs" / "sbom" / "cprmv-api-9.9.9.cdx.json"


def test_output_path_carries_the_version_from_pyproject(repo, capsys):
    assert W.project(repo) == ("cprmv", "9.9.9")
    assert W.output_path("9.9.9") == "docs/sbom/cprmv-api-9.9.9.cdx.json"
    assert W.main(["--write"], repo) == 0
    assert sbom_file(repo).exists()


def test_the_real_pyproject_version_is_used():
    _, version = W.project(REPO)
    assert W.output_path(version).endswith(f"-{version}.cdx.json")


def test_normalise_removes_volatile_fields_and_sorts():
    doc = W.normalise(raw_doc(), "cprmv", "9.9.9")
    assert "serialNumber" not in doc
    assert "timestamp" not in doc["metadata"]
    refs = [c["bom-ref"] for c in doc["components"]]
    assert refs == ["pkg:pypi/alpha@1.0", "pkg:pypi/zeta@2.0"]
    assert all("description" not in c for c in doc["components"])
    assert doc["metadata"]["component"]["bom-ref"] == "cprmv@9.9.9"
    assert doc["dependencies"][0] == {"ref": "cprmv@9.9.9", "dependsOn": refs}
    assert [d["ref"] for d in doc["dependencies"][1:]] == refs


def test_normalise_ignores_input_order_and_line_numbers():
    shuffled = raw_doc()
    shuffled["components"].reverse()
    shuffled["components"][0]["bom-ref"] = "requirements-L999"
    assert W.serialise(W.normalise(shuffled, "cprmv", "9.9.9")) == W.serialise(
        W.normalise(raw_doc(), "cprmv", "9.9.9")
    )


def test_normalise_rejects_a_duplicate_package():
    dup = raw_doc(extra_component=dict(raw_doc()["components"][0]))
    with pytest.raises(ValueError):
        W.normalise(dup, "cprmv", "9.9.9")


def test_output_is_stable_json_with_trailing_newline(repo):
    W.main([], repo)
    text = sbom_file(repo).read_bytes().decode()
    assert text.endswith("}\n") and "\r" not in text
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


def test_check_passes_on_a_fresh_file(repo, capsys):
    W.main([], repo)
    assert W.main(["--check"], repo) == 0


def test_check_fails_when_missing(repo, capsys):
    assert W.main(["--check"], repo) == 1
    assert "is missing" in capsys.readouterr().err


def test_check_fails_when_stale(repo, state, capsys):
    W.main([], repo)
    state["doc"] = raw_doc(
        {
            "bom-ref": "requirements-L30",
            "name": "new",
            "purl": "pkg:pypi/new@1.0",
            "type": "library",
            "version": "1.0",
        }
    )
    assert W.main(["--check"], repo) == 1
    assert "does not match" in capsys.readouterr().err


def test_check_ignores_tool_version_and_timestamp(repo, state):
    W.main([], repo)
    other = raw_doc()
    other["metadata"]["tools"]["components"][0]["version"] = "9.0.0"
    other["metadata"]["timestamp"] = "2030-01-01T00:00:00+00:00"
    other["serialNumber"] = "urn:uuid:22222222-2222-2222-2222-222222222222"
    state["doc"] = other
    assert W.main(["--check"], repo) == 0


def test_verify_release_fails_only_on_missing(repo, state, capsys):
    assert W.main(["--verify-release"], repo) == 1
    assert "is missing" in capsys.readouterr().err

    W.main([], repo)
    state["doc"] = raw_doc({**raw_doc()["components"][0], "purl": "pkg:pypi/zeta@3.0",
                                 "version": "3.0"})
    assert W.main(["--verify-release"], repo) == 0
    assert "::warning::" in capsys.readouterr().out


def test_print_path_prints_the_path_without_running_the_tool(repo, capsys, monkeypatch):
    monkeypatch.setattr(W, "run_tool", lambda root: pytest.fail("tool must not run"))
    assert W.main(["--print-path"], repo) == 0
    assert capsys.readouterr().out.strip() == "docs/sbom/cprmv-api-9.9.9.cdx.json"
    assert not (repo / "docs").exists()


@pytest.mark.skipif(shutil.which("cyclonedx-py") is None, reason="cyclonedx-py not installed")
def test_real_tool_on_a_hashed_requirements_file(tmp_path):
    (tmp_path / "serve_api").mkdir()
    (tmp_path / "serve_api" / "pyproject.toml").write_text(
        '[project]\nname = "cprmv"\nversion = "1.2.3"\n', encoding="utf-8"
    )
    (tmp_path / "serve_api" / "requirements.txt").write_text(
        "idna==3.10 \\\n    --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8"
    )
    first = W.generate(tmp_path)
    assert first == W.generate(tmp_path)
    doc = json.loads(first)
    assert doc["specVersion"] == "1.6"
    assert [c["purl"] for c in doc["components"]] == ["pkg:pypi/idna@3.10"]
