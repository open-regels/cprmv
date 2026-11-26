import os
from pytest import fail
from fastapi.testclient import TestClient
from ..src.serve import set_CPRMVMETHODSKG
from ..src.serve import app
from ..src.serve import CPRMV
from ..src.serve import CPRMVMETHODS
from ..src.serve import CPRMVSERVE
#from ..src.serve import detect_cprmv_serve_acknowledged_method
from ..src.serve import load_rule_set
from ..src.serve import get_rules
#from ..src.serve import get_mapping
#from ..src.serve import transform_jci_reference
from ..src.serve import detect_cprmv_serve_reference_method_and_transform
from rdflib import Literal
from urllib.parse import quote as urlquote
from datetime import datetime

client = TestClient(app)


def test_get_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"CPRMV Rules Serve API": "0.4.3"}

HEALTH_ENV = ("BUILD_SHA", "BUILD_RUN", "CPRMV_IMAGE_DIGEST", "CPRMV_ENVIRONMENT")


def test_health_reports_build_and_digest(monkeypatch):
    monkeypatch.setenv("BUILD_SHA", "abc123")
    monkeypatch.setenv("BUILD_RUN", "42")
    monkeypatch.setenv("CPRMV_IMAGE_DIGEST", "sha256:feed")
    monkeypatch.setenv("CPRMV_ENVIRONMENT", "acceptance")
    response = client.get("/health")
    assert response.status_code == 200
    assert list(response.json().keys()) == [
        "status", "version", "environment", "build", "image",
    ]
    assert response.json() == {
        "status": "ok",
        "version": "0.4.3",
        "environment": "acceptance",
        "build": {"sha": "abc123", "run": "42"},
        "image": {"digest": "sha256:feed"},
    }


def test_health_reports_null_when_unset(monkeypatch):
    for name in HEALTH_ENV:
        monkeypatch.delenv(name, raising=False)
    body = client.get("/health").json()
    assert body["environment"] is None
    assert body["build"] == {"sha": None, "run": None}
    assert body["image"] == {"digest": None}


def test_health_treats_empty_as_null(monkeypatch):
    for name in HEALTH_ENV:
        monkeypatch.setenv(name, "")
    body = client.get("/health").json()
    assert body["environment"] is None
    assert body["build"] == {"sha": None, "run": None}
    assert body["image"] == {"digest": None}

#def test_get_mapping():
#    result = get_mapping(CPRMVMETHODS.juriconnect)
#    expected = {'aanwijzing': 'Aanwijzing', 'afdeling': 'Afdeling', 'artikel': 'Artikel', 'bijlage': 'Bijlage', 'boek': 'Boek', 'deel': 'Deel', 'enig': 'enig', 'hoofdstuk': 'Hoofdstuk', 'inhoudsopgave': 'Inhoudsopgave', 'nummer': 'nummer', 'paragraaf': 'Paragraaf', 'sub-paragraaf': 'Paragraaf', 'titeldeel': 'Titeldeel', 'taal': 'taal', 'verdragsonderdeel': 'Verdragsonderdeel', 'lid': 'lid', 'o': 'onderdeel', 'volzin': 'volzin', 'https://cprmv.open-regels.nl/0.4.3/serve-api/reference-mapping-valid-on': #'g', 'https://cprmv.open-regels.nl/0.4.3/serve-api/reference-mapping-seen-on': 'z'}
#    assert result == expected
#    assert get_mapping(CPRMVMETHODS.eli) == {}
#    assert get_mapping(CPRMVMETHODS.cprmvapi) == {}
#    assert get_mapping(CPRMVMETHODS.bwb) == {}

#def test_transform_jci_reference():
 #   assert transform_jci_reference(CPRMVMETHODS.juriconnect, {'subversion' : '2', 'bwbid' : 'R1234567', 'locatie-string' : 'hoofdstuk=5&artikel=20&g=2026-01-01&z=2026-01-01'}) == None
 #   assert transform_jci_reference(CPRMVMETHODS.juriconnect, {'subversion' : '31', 'bwbid' : 'R1234567', 'locatie-string' : 'hoofdstuk=5&artikel=20&g=2026-01-01&z=2026-01-01'}) == '/rules/BWBR1234567_2026-01-01_2026-01-01%2CHoofdstuk%205%2CArtikel%2020'
 #   assert transform_jci_reference(CPRMVMETHODS.juriconnect, {'subversion' : '3', 'bwbid' : 'R1234567', 'locatie-string' : 'hoofdstuk=5&artikel=20&g=2026-01-01'}) == '/rules/BWBR1234567_2026-01-01_latest%2CHoofdstuk%205%2CArtikel%2020'

def test_detect_cprmv_serve_reference_method_and_transform():
    assert detect_cprmv_serve_reference_method_and_transform('') == None
    assert detect_cprmv_serve_reference_method_and_transform('jci1.31:c:BWBR0015703&hoofdstuk=3&paragraaf=3.2&artikel=20&z=2025-07-01&g=2025-07-01') == '/rules/BWBR0015703_2025-07-01_2025-07-01%2CHoofdstuk%203%2CParagraaf%203.2%2CArtikel%2020'
    assert detect_cprmv_serve_reference_method_and_transform('jci1.3:c:BWBR0015703&hoofdstuk=3&paragraaf=3.2&artikel=20&g=2025-07-01') == '/rules/BWBR0015703_2025-07-01_latest%2CHoofdstuk%203%2CParagraaf%203.2%2CArtikel%2020'

#def test_detect_cprmv_serve_acknowledged_method_unknown_identifier():
#    try:
#        method = detect_cprmv_serve_acknowledged_method("UNKNOWN")
#    except Exception as e:
#        fail(
#            f"detect_cprmv_serve_acknowledged_method() should not raise any Exception. It did: {e}"
#        )
#    assert (
#        method is None
#    ), f"Passing an unknown identifier to detect_cprmv_serve_acknowledged_method() not matching any AnalysisMethods (default) should return 'None'. It did not: {method}"

#def test_detect_cprmv_serve_acknowledged_method_DMN_identifier():
#    try:
#        method = detect_cprmv_serve_acknowledged_method("DMN1.3_A_B_C", CPRMVMETHODS.formalisationmethods)
#    except Exception as e:
#        fail(
#            f"detect_cprmv_serve_acknowledged_method() should not raise any Exception. It did: {e}"
#        )
#    assert (
#        method is not None
#    ), "Passing a syntactically valid DMN1.3 identifier to detect_cprmv_serve_acknowledged_method() should not return 'None'. It did."
#    assert method[CPRMV.label] == Literal("DMN 1.3 on operaton.open-regels.nl (experimental)")
#    assert method[CPRMVSERVE["publication-format"]] == Literal("xml")
#    assert method[CPRMVSERVE["publication-id-format"]] == Literal(
#        "DMN1.3_{deploymentid}R{resourceid}_{date}_{index}"
#    )
#    assert method[CPRMVSERVE["repository-publication-location-format"]] == Literal(
#        "https://operaton.open-regels.nl/engine-rest/deployment/{deploymentid}/resources/{resourceid}/data"
#    )
#    assert method[CPRMVSERVE["xslt"]] == Literal("data/dmn13operaton2cprmv.xsl")
#    assert method[CPRMVSERVE["id_parts"]] == {
#        "rulesetid": "A",
#        "date": "B",
#        "index": "C",
#        "cprmvid": "DMN1.3_A_B_C"
#    }

#def test_detect_cprmv_serve_acknowledged_method_BWB_identifier():
#    try:
#        method = detect_cprmv_serve_acknowledged_method("BWBAA_BB_CC")
#    except Exception as e:
#        fail(
#            f"detect_cprmv_serve_acknowledged_method() should not raise any Exception. It did: {e}"
#        )
#    assert (
#        method is not None
#    ), "Passing a syntactically valid BWB identifier to detect_cprmv_serve_acknowledged_method() should not return 'None'. It did."
#    assert method[CPRMV.label] == Literal("BWB (NL)")
#    assert method[CPRMVSERVE["publication-format"]] == Literal("xml")
#    assert method[CPRMVSERVE["publication-id-format"]] == Literal(
#        "BWB{rulesetid}_{date}_{index}"
#    )
#    assert method[CPRMVSERVE["repository-publication-location-format"]] == Literal(
#        "https://repository.officiele-overheidspublicaties.nl/bwb/BWB{rulesetid}/{date}_{index}/xml/BWB{rulesetid}_{date}_{index}.xml"
#    )
#    assert method[CPRMVSERVE["xslt"]] == Literal("data/bwb2cprmv.xsl")
#    assert method[CPRMVSERVE["id_parts"]] == {
#        "rulesetid": "AA",
#        "date": "BB",
#        "index": "CC",
#        "cprmvid": "BWBAA_BB_CC"
#    }

#def test_detect_cprmv_serve_acknowledged_method_BWB_identifier_with_latest():
#    # add extra cprmvmethod knowledge for local testing (using a test frbr repository setting referring to a fixed publication sourcefile)
#    tm = set_CPRMVMETHODSKG("./test/cprmvmethods.test.ttl", False)
#    tm = set_CPRMVMETHODSKG("./data/cprmv.ttl", True)
#
#    # update relative paths to file:// url with absolute paths
#    path = tm.value(CPRMVMETHODS.test001bwb, CPRMVSERVE["frbr-repository-sru-url"])
#    path = "file://" + urlquote(os.path.abspath(str(path)))
#    tm.set((CPRMVMETHODS.test001bwb, CPRMVSERVE["frbr-repository-sru-url"], Literal(path)))
#
#    try:
#        method = detect_cprmv_serve_acknowledged_method("TEST001BWBAA_2025-09-15_latest")
#    except Exception as e:
#        fail(
#            f"detect_cprmv_serve_acknowledged_method() should not raise any Exception. It did: {e}"
#        )
#
#    # note that in this test, the index of the publication is set to "Publication"
#    assert method[CPRMVSERVE["id_parts"]] == {
#        "rulesetid": "AA",
#        "date": "2025-07-01",
#        "index": "Publication",
#        "cprmvid": "TEST001BWBAA_2025-07-01_Publication",
#        "valid-on": "2025-09-15"
#    }

#def test_detect_cprmv_serve_acknowledged_method_BWB_identifier_with_implicit_latest():
#    # add extra cprmvmethod knowledge for local testing (using a test frbr repository setting referring to a fixed publication sourcefile)
#    tm = set_CPRMVMETHODSKG("./test/cprmvmethods.test.ttl", False)
#    # update relative paths to file:// url with absolute paths
#    path = tm.value(CPRMVMETHODS.test001bwb, CPRMVSERVE["frbr-repository-sru-url"])
#    path = "file://" + urlquote(os.path.abspath(str(path)))
#    tm.set((CPRMVMETHODS.test001bwb, CPRMVSERVE["frbr-repository-sru-url"], Literal(path)))

#    try:
#        method = detect_cprmv_serve_acknowledged_method("TEST001BWBAA")
#    except Exception as e:
#        fail(
#            f"detect_cprmv_serve_acknowledged_method() should not raise any Exception. It did: {e}"
#        )

    # note that in this test, the index of the publication is set to "Publication"
#    assert method[CPRMVSERVE["id_parts"]] == {
#        "rulesetid": "AA",
#        "date": "2025-07-01",
#        "index": "Publication",
#        "cprmvid": "TEST001BWBAA_2025-07-01_Publication",
#        "valid-on": datetime.now().strftime('%Y-%m-%d')
#    }

#def test_detect_cprmv_serve_acknowledged_method_CVDR_identifier():
#    try:
#        method = detect_cprmv_serve_acknowledged_method("CVDAA_CC")
#    except Exception as e:
#        fail(
#            f"detect_cprmv_serve_acknowledged_method() should not raise any Exception. It did: {e}"
#        )
#    assert (
#        method is not None
#    ), "Passing a syntactically valid CVDR identifier to detect_cprmv_serve_analysis_method() should not return 'None'. It did."
#    assert method[CPRMV.label] == Literal("CVDR (NL)")
#    assert method[CPRMVSERVE["publication-format"]] == Literal("xml")
#    assert method[CPRMVSERVE["publication-id-format"]] == Literal("CVD{rulesetid}_{index}")
#    assert method[CPRMVSERVE["repository-publication-location-format"]] == Literal(
#        "https://repository.officiele-overheidspublicaties.nl/cvdr/CVD{rulesetid}/{index}/xml/CVD{rulesetid}_{index}.xml"
#    )
#    assert method[CPRMVSERVE["xslt"]] == Literal("data/cvdr2cprmv.xsl")
#    assert method[CPRMVSERVE["id_parts"]] == {"rulesetid": "AA", "index": "CC", "cprmvid": "CVDAA_CC", "date" : "na"}


#def test_detect_cprmv_serve_acknowledged_method_FMX4_identifier():
#    try:
#        method = detect_cprmv_serve_acknowledged_method("CFMX4AA_DOC_2")
#    except Exception as e:
#        fail(
#            f"detect_cprmv_serve_acknowledged_method() should not raise any Exception. It did: {e}"
#        )
#    assert (
#        method is not None
#    ), "Passing a syntactically valid CFMX4 identifier to detect_cprmv_serve_analysis_method() should not return 'None'. It did."
#    assert method[CPRMV.label] == Literal("CELLAR Formex v4 (EU)")
#    assert method[CPRMVSERVE["publication-format"]] == Literal("xml")
#    assert method[CPRMVSERVE["publication-id-format"]] == Literal(
#        "CFMX4{rulesetid}_{docid}"
#    )
#    assert method[CPRMVSERVE["repository-publication-location-format"]] == Literal(
#        "https://publications.europa.eu/resource/cellar/{rulesetid}/{docid}"
#    )
#    assert method[CPRMVSERVE["xslt"]] == Literal("data/fmx4cellar2cprmv.xsl")
    # note that in the current implementation the api will prepend "na"
#    assert method[CPRMVSERVE["id_parts"]] == {"rulesetid": "AA", "docid": "DOC_2", "cprmvid": "CFMX4AA_DOC_2"}


def test_detect_cprmv_serve_unknown_method():
    result = get_rules("UNKNOWN")
    assert result == '{"error": "No supported publication repository use identifiers with the format of the given Ruleset Id."}'


#def test_get_rules():
#    # add extra cprmvmethod knowledge for local testing (using a test frbr repository setting referring to a fixed publication sourcefile)
#    tm = set_CPRMVMETHODSKG("./test/cprmvmethods.test.ttl", False)
#    # update relative path to file:// url with absolute path
#    path = tm.value(CPRMVMETHODS.test001bwb, CPRMVSERVE["repository-publication-location-format"])
#    path = path.replace('{index}','Publication')
#    path = "file://" + urlquote(os.path.abspath(str(path)))
#    print("publoc path set: "+path)
#    tm.set((CPRMVMETHODS.test001bwb, CPRMVSERVE["repository-publication-location-format"], Literal(path)))

    # note that onderdeel a) should match onderdeel a., id's in the path should match looking only
    # at alphanumeric characters (especially ignoring comparing the whitespace character with the
    # non breaking space character and so on, but also any other non alpha numeric character
    # (uses python's isalnum())
#    response = client.get(
#        "/rules/TEST001BWBR0015703_2025-07-01_0, Artikel\xa021, onderdeel\xa0a)",
#        params={"unformat": "{situatie:param_value}: € {norm:param_value};"},
#    )
#    assert response.status_code == 200
#    resp = response.json()
#    resp['https://standaarden.open-regels.nl/standards/cprmv/0.4.3#isOutputOf'] = ''
#    print(resp)
#    assert resp == {'http://www.w3.org/1999/02/22-rdf-syntax-ns#type': 'https://standaarden.open-regels.nl/standards/cprmv/0.4.3#RuleSet', 'http://www.w3.org/ns/prov#wasDerivedFrom': path, 'https://standaarden.open-regels.nl/standards/cprmv/0.4.3#id': 'TEST001BWBR0015703_2025-07-01_0', 'https://standaarden.open-regels.nl/standards/cprmv/0.4.3#validFrom': '2025-07-01', 'https://standaarden.open-regels.nl/standards/cprmv/0.4.3#hasMethod': 'https://cprmv.open-regels.nl/0.4.3/methods/bwb', 'https://standaarden.open-regels.nl/standards/cprmv/0.4.3#isOutputOf': '', 'https://identifier.overheid.nl/tooi/thes/bwbid': 'TEST001BWBR0015703', 'https://identifier.overheid.nl/tooi/thes/bwbinwerkingtreding': '2025-07-01', 'https://standaarden.open-regels.nl/standards/cprmv/0.4.3#hasPart': {'onderdeel a.': {'http://www.w3.org/1999/02/22-rdf-syntax-ns#type': 'https://standaarden.open-regels.nl/standards/cprmv/0.4.3#Rule', 'https://standaarden.open-regels.nl/standards/cprmv/0.4.3#id': 'onderdeel a.', 'https://standaarden.open-regels.nl/standards/cprmv/0.4.3#definition': 'een alleenstaande of een alleenstaande ouder zonder kostendelende medebewoners: €\xa01.369,06;', 'http://cprmv.open-regels.nl/situatie': 'een alleenstaande of een alleenstaande ouder zonder kostendelende medebewoners', 'http://cprmv.open-regels.nl/norm': '1.369,06', 'http://cprmv.open-regels.nl/rulesetid': 'TEST001BWBR0015703_2025-07-01_0', 'http://cprmv.open-regels.nl/rule_id_path': 'TEST001BWBR0015703_2025-07-01_0, Artikel\xa021, onderdeel\xa0a)'}}}
