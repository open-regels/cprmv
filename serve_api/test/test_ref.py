"""/ref redirects: no copied request headers (issue #1), no open redirect.

These tests run offline. The ELI reference method queries EU CELLAR, so its
urlopen is replaced in every test that could reach it.
"""
import io
import json
import sys

import pytest
from fastapi.testclient import TestClient

from ..src.serve import app
from ..src.serve import detect_cprmv_serve_reference_method_and_transform

client = TestClient(app)
serve_module = sys.modules[detect_cprmv_serve_reference_method_and_transform.__module__]

JCI = "jci1.31:c:BWBR0015703&artikel=20&z=2025-07-01&g=2025-07-01"
ELI = "http://data.europa.eu/eli/reg/2018/1805/oj"
CELLAR_ITEM = "http://publications.europa.eu/resource/cellar/0b3f2c5e-1234-11e8-a8b3-01aa75ed71a1.0006.01/DOC_1"


def eli_module():
    # load_methods imports methods/eli.py as the top-level module "eli"
    return sys.modules["eli"]


@pytest.fixture
def no_cellar(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("the ELI reference method must not query CELLAR here")

    monkeypatch.setattr(eli_module(), "urlopen", refuse)


def cellar_answering(monkeypatch, item):
    calls = []

    def fake_urlopen(url, *args, **kwargs):
        calls.append(url)
        body = {"results": {"bindings": [{"item": {"value": item}}]}}
        return io.BytesIO(json.dumps(body).encode("utf-8"))

    monkeypatch.setattr(eli_module(), "urlopen", fake_urlopen)
    return calls


def get_ref(reference, **kwargs):
    return client.get("/ref", params={"reference": reference}, follow_redirects=False, **kwargs)


# issue #1: the redirect carries none of the request's headers


def test_ref_redirect_does_not_echo_request_headers(no_cellar):
    response = get_ref(JCI, headers={"x-api-key": "secret-key", "x-custom": "custom-value"})
    assert response.status_code == 307
    assert response.headers["location"].startswith("/rules/BWBR0015703_")
    assert "x-api-key" not in response.headers
    assert "x-custom" not in response.headers
    assert "secret-key" not in str(response.headers)


# the ELI method validates before it queries CELLAR


@pytest.mark.parametrize(
    "reference",
    [
        "",
        "not a reference",
        "https://example.org/eli/reg/2018/1805/oj",
        ELI + '"',
        ELI + '%22 . } SELECT ?item WHERE { BIND(<https://evil.example/> AS ?item) } #',
        'http://data.europa.eu/eli/reg/2018/1805/oj" . }',
        "http://data.europa.eu/eli/reg/2018/1805/<oj>",
        "http://data.europa.eu/eli/reg/2018/1805/oj\n",
    ],
)
def test_unrecognised_references_never_reach_cellar(no_cellar, reference):
    assert detect_cprmv_serve_reference_method_and_transform(reference) is None


def test_valid_eli_reference_queries_cellar(monkeypatch):
    calls = cellar_answering(monkeypatch, CELLAR_ITEM)
    assert detect_cprmv_serve_reference_method_and_transform(ELI) == CELLAR_ITEM
    assert len(calls) == 1
    assert calls[0].startswith("https://publications.europa.eu/webapi/rdf/sparql?")


# /ref redirects only to a relative path or to CELLAR


def test_ref_redirects_to_a_cellar_item(monkeypatch):
    cellar_answering(monkeypatch, CELLAR_ITEM)
    response = get_ref(ELI)
    assert response.status_code == 307
    assert response.headers["location"] == CELLAR_ITEM


@pytest.mark.parametrize(
    "target",
    [
        "https://evil.example/phish",
        "//evil.example/phish",
        "/\\evil.example/phish",
        "https://publications.europa.eu@evil.example/phish",
        "https://publications.europa.eu.evil.example/phish",
        "javascript:alert(1)",
        "ftp://publications.europa.eu/resource",
    ],
)
def test_ref_refuses_to_redirect_elsewhere(monkeypatch, target):
    monkeypatch.setattr(serve_module, "detect_cprmv_serve_reference_method_and_transform", lambda reference: target)
    response = get_ref("anything")
    assert response.status_code == 200
    assert "location" not in response.headers
    assert response.json() == {"error": "not a valid or supported reference..."}


def test_ref_refuses_a_cellar_answer_pointing_elsewhere(monkeypatch):
    cellar_answering(monkeypatch, "https://evil.example/phish")
    response = get_ref(ELI)
    assert response.status_code == 200
    assert "location" not in response.headers
