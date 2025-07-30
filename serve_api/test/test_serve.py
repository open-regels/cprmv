import os
from pytest import fail
from fastapi.testclient import TestClient
from ..serve import setCPRMVMETHODSKG
from ..serve import app
from ..serve import CPRMV
from ..serve import CPRMVMETHODS
from ..serve import CPRMVSERVE
from ..serve import detectCPRMVServeAnalysisMethod
from ..serve import loadRuleSet
from rdflib import Literal
from urllib.parse import quote as urlquote

client = TestClient(app)

def test_get_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {'CPRMV Rules Serve API': '0.3.1'}

def test_detectCPRMVServeAnalysisMethod_unknown_identifier():
    try:
        method = detectCPRMVServeAnalysisMethod("UNKNOWN")
    except Exception as e:
        fail(f"detectCPRMVServeAnalysisMethod() should not raise any Exception. It did: {e}")
    assert method == None, f"Passing an unknown identifier to detectCPRMVServeAnalysisMethod() not matching any AnalysisMethods should return 'None'. It did not: {method}"

def test_detectCPRMVServeAnalysisMethod_BWB_identifier():
    try:
        method = detectCPRMVServeAnalysisMethod("BWBAA_BB_CC")
    except Exception as e:
        fail(f"detectCPRMVServeAnalysisMethod() should not raise any Exception. It did: {e}")
    assert method != None, f"Passing a syntactically valid BWB identifier to detectCPRMVServeAnalysisMethod() should not return 'None'. It did."
    assert method[CPRMV.label] == Literal('BWB (NL)')
    assert method[CPRMVSERVE['publication-format']] == Literal('xml')
    assert method[CPRMVSERVE['publication-id-format']] == Literal('BWB{bwbid}_{date}_{index}')
    assert method[CPRMVSERVE['frbr-repository']] == Literal("https://repository.officiele-overheidspublicaties.nl/bwb/BWB{bwbid}/{date}_{index}/xml/BWB{bwbid}_{date}_{index}.xml")
    assert method[CPRMVSERVE['xslt']] == Literal("data/bwb2cprmv.xsl")
    assert method[CPRMVSERVE['id_parts']] == {'bwbid' : 'AA', 'date' : 'BB', 'index' : 'CC'}

def test_detectCPRMVServeAnalysisMethod_CVDR_identifier():
    try:
        method = detectCPRMVServeAnalysisMethod("CVDAA_CC")
    except Exception as e:
        fail(f"detectCPRMVServeAnalysisMethod() should not raise any Exception. It did: {e}")
    assert method != None, f"Passing a syntactically valid CVDR identifier to detectCPRMVServeAnalysisMethod() should not return 'None'. It did."
    assert method[CPRMV.label] == Literal('CVDR (NL)')
    assert method[CPRMVSERVE['publication-format']] == Literal('xml')
    assert method[CPRMVSERVE['publication-id-format']] == Literal('CVD{cvdrid}_{index}')
    assert method[CPRMVSERVE['frbr-repository']] == Literal("https://repository.officiele-overheidspublicaties.nl/cvdr/CVD{cvdrid}/{index}/xml/CVD{cvdrid}_{index}.xml")
    assert method[CPRMVSERVE['xslt']] == Literal("data/cvdr2cprmv.xsl")
    assert method[CPRMVSERVE['id_parts']] == {'cvdrid' : 'AA', 'index' : 'CC'}
    
def test_detectCPRMVServeAnalysisMethod_FMX4_identifier():
    try:
        method = detectCPRMVServeAnalysisMethod("CFMX4AA_BB")
    except Exception as e:
        fail(f"detectCPRMVServeAnalysisMethod() should not raise any Exception. It did: {e}")
    assert method != None, f"Passing a syntactically valid CFMX4 identifier to detectCPRMVServeAnalysisMethod() should not return 'None'. It did."
    assert method[CPRMV.label] == Literal('CELLAR Formex v4 (EU)')
    assert method[CPRMVSERVE['publication-format']] == Literal('xml')
    assert method[CPRMVSERVE['publication-id-format']] == Literal('CFMX4{cellarid}_{docid}')
    assert method[CPRMVSERVE['frbr-repository']] == Literal("https://publications.europa.eu/resource/cellar/{cellarid}/{docid}")
    assert method[CPRMVSERVE['xslt']] == Literal("data/fmx4cellar2cprmv.xsl")
    assert method[CPRMVSERVE['id_parts']] == {'cellarid' : 'AA', 'docid' : 'BB'}

def test_loadRuleSet_unknown_method():
    try:
        loadRuleSet('UNKNOWN')
    except Exception as e:
        assert str(e) == 'No supported publication repository use identifiers with the format of the given Ruleset Id.'
        return
    fail('loadRuleSet() should raise an exception when passing a identifier that does not syntactically match a supported AnalysisMethod')

def test_get_rules():
    # add extra cprmvmethod knowledge for local testing (using a test frbr repository setting referring to a fixed publication sourcefile)
    tm = setCPRMVMETHODSKG('./test/cprmvmethods.ttl')
    # update relative path to file:// url with absolute path
    path = tm.value(CPRMVMETHODS.test001bwb, CPRMVSERVE['frbr-repository'])
    path = 'file://'+urlquote(os.path.abspath(str(path)))
    tm.set((CPRMVMETHODS.test001bwb, CPRMVSERVE['frbr-repository'],Literal(path)))
    
    # note that onderdeel a) should match onderdeel a., id's in the path should match looking only
    # at alphanumeric characters (especially ignoring comparing the whitespace character with the
    # non breaking space character and so on, but also any other non alpha numeric character
    # (uses python's isalnum())
    response = client.get("/rules/TEST001BWBR0015703_2025-07-01_0, Artikel\xa021, onderdeel\xa0a)", params={'unformat':'{situatie:paramvalue}: € {norm:paramvalue};'})
    assert response.status_code == 200
    assert response.json() == {
        'http://www.w3.org/1999/02/22-rdf-syntax-ns#type': 'https://cprmv.open-regels.nl/0.3.0/Rule',
        'https://cprmv.open-regels.nl/0.3.0/definition': 'een alleenstaande of een alleenstaande ouder zonder kostendelende medebewoners: €\xa01.369,06;',
        'https://cprmv.open-regels.nl/0.3.0/id': 'onderdeel a.',
        'norm': '1.369,06',
        'ruleidpath': 'TEST001BWBR0015703_2025-07-01_0, Artikel\xa021, onderdeel\xa0a)',
        'rulesetid': 'TEST001BWBR0015703_2025-07-01_0',
        'situatie': 'een alleenstaande of een alleenstaande ouder zonder kostendelende medebewoners',
    }
    
