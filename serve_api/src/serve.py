from fastapi_mcp import FastApiMCP
from rdflib import Graph, BNode, URIRef
from rdflib.term import Literal
from rdflib.namespace import RDF
from typing import Union
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.responses import PlainTextResponse
from parse import parse, search, with_pattern, Result, Match
from urllib.request import Request, urlopen
from urllib.error import URLError
from lxml import etree
import shutil
import ssl
import tempfile
import os
import ciso8601
import json
from datetime import datetime
from pathlib import Path
import time

import locale
from .utils.constants import (
    CPRMV,
    CPRMVMETHODS,
    CPRMVSERVE,
    FORMAT,
    LANGUAGE,
    UNFORMAT,
    PATH_DELIMITER,
    RULE_ID_PATH,
)


type Definition = dict[str, Union[str, dict]]


# --- TLS trust fix -----------------------------------------------------------
# repository.officiele-overheidspublicaties.nl serves an incomplete certificate
# chain: it omits the "certSIGN Web CA" intermediate that signed its leaf
# certificate (it presents the unrelated "certSIGN Web CA G2" intermediate
# instead). OpenSSL/Python therefore cannot build a trust path and every upstream
# fetch fails with "unable to get local issuer certificate". Browsers hide this by
# downloading the missing intermediate via the leaf's AIA extension; urllib does
# not. We bundle the intermediate (certs/certsign-webca.crt) and add it to the
# default trust store here, so the fix is OS-independent and works for both local
# runs and the Docker image without any system-level certificate installation.
# See certs/README.md and SSL_FIX.md for provenance and details.
_BUNDLED_INTERMEDIATE = Path(__file__).resolve().parent.parent / "certs" / "certsign-webca.crt"


def _build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if _BUNDLED_INTERMEDIATE.is_file():
        ctx.load_verify_locations(cafile=str(_BUNDLED_INTERMEDIATE))
    return ctx


SSL_CONTEXT = _build_ssl_context()


try:
    locale.setlocale(
        locale.LC_ALL, "nl_NL.UTF-8"
    )  # todo, find out whether locale has effect on the parse module at all, and if so, make NL not the hard coded locale but dependent on language arguments
    print("Dutch locale (nl_NL.UTF-8) set successfully")
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, "nl_NL")
        print("Dutch locale (nl_NL) set successfully")
    except locale.Error:
        print("Warning: Dutch locale not available, using system default")

app = FastAPI(
    title="CPRMV Rules Serve API",
    description="This experimental API allows fetching single CPRMV Rules from locally provided CPRMV RuleSets in a desired RDF format.",
    version="0.4.2",
    contact={
        "name": "Bas Kaptijn",
        "url": "http://git.open-regels.nl/standards/cprmv",
        "email": "Bas.Kaptijn@ictu.nl",
    },
    license_info={
        "name": "EUPL",
        "url": "https://git.open-regels.nl/standards/cprmv/-/blob/main/LICENSE?ref_type=heads",
    },
)


def set_CPRMVMETHODSKG(path, additive=True):
    print("loading cprmvmethods.ttl from path: "+path)
    if not additive:
        _cprmvMethods = Graph()
    else:
        _cprmvMethods = app.cprmvsettings["CPRMVMETHODS_KG"]
    _cprmvMethods.parse(path, format="turtle")
    app.cprmvsettings = {"CPRMVMETHODS_KG": _cprmvMethods}
    return app.cprmvsettings["CPRMVMETHODS_KG"]


set_CPRMVMETHODSKG("./data/cprmvmethods.ttl", False)
set_CPRMVMETHODSKG("./data/cprmv.ttl", True)

@app.get("/")
def cprmv_info():
    """
    returns basic app information (title and version)
    """
    return {app.title: app.version}


app.mount("/respec", StaticFiles(directory="respec", html=True, follow_symlink=True), name="respec")

@app.get("/methods")
def methods(format: str = "json-ld"):
    if format in ["json-ld", "xml", "turtle", "ttl", "n3", "turtle2"]:
        return PlainTextResponse(app.cprmvsettings["CPRMVMETHODS_KG"].serialize(format=format))


@app.get("/rules/{rule_id_path}")
def rules(
    rule_id_path: str = RULE_ID_PATH,
    path_delimiter: str = PATH_DELIMITER,
    format: str = FORMAT,
    _language: Union[str, None] = LANGUAGE,
    unformat: str = UNFORMAT,
):
    """
    Returns the Rule(Set) including all Rules that are part of it and that can be found as indicated in the given Rule Id Path.

    This endpoint retrieves a specific rule or rule set from various official publication repositories
    and transforms it into CPRMV format. The ReSpec documentation of the CPRMV can be found under the /respec endpoint. 
    It supports BWB, CVDR, EU CELLAR and the operaton.open-regels.nl repositories.

    The API downloads the source publication on-the-fly, transforms it using XSLT, and serves the resulting
    CPRMV-formatted rules. You can request individual rules within a rule set by specifying their path.
    """
    return PlainTextResponse(get_rules(rule_id_path, path_delimiter, format, unformat))


@app.get("/ref")
def ref(reference : str = ""):
    """
    Supported reference methods
    
    - ELI to Formex4 to be found on EU CELLAR. (Work in progress)
    
      Currently the resonse will be from the EU CELLAR SPARQL endpoint giving a list fro multiple files that form a collection. 
      See endpoint /cellar-by-eli what to do with this. This endpoint will make the language and format to default to 'NLD' and 'fmx4'
      Use for example: http://data.europa.eu/eli/reg/2018/1805/oj
    
    - ELI to BWB and CVDR. (Experimental, Work in progress)
    
      Note it just accepts a cprmv api path delimited with forward slashes after the base URI. Note that it also accepts CFMX4... references due to this
      
      Example: https://wetten.overheid.nl/BWBR0015703/Artikel%2020/onderdeel%20a.
    
    - Juriconnect:
    
        Supports both jci version 1.3 as 1.31. The usage of sighting date is not (yet) supported (it can be included in the URL but it won't have any effect as the cprmv api does not yet support it as part of the rule id path). The sighting date therefor always implicitly defaults to today (which is the default in the Juriconnect standard too).
    
        Also, only references to single consolidations are supported. Note that what the juriconnect standard supports within the CPRMV API might not yet be supported in the BWB support implementation within the CPRMV API. For instance some types of items can not yet be referenced. Currently supported of the juriconnect standard therefor is: "artikel", "hoofdstuk", "paragraaf", "onderdeel", "lid".
    
        Example: jci1.31:c:BWBR0015703&artikel=20&o=a.'
    
    - CPRMV API:
    
      you can just use the /rules endpoint but you can also use the URL to such endpoint call here to make this call on this CPRMV API instance.
        
      Example: https://cprmv.open-regels.nl/rules/BWBR0015703/Artikel%2020/onderdeel%20a.         
    
    """
    
    redirect_url = detect_cprmv_serve_reference_method_and_transform(reference)
    if redirect_url is not None:
        response = RedirectResponse(
            url=redirect_url
        )
        return response
    return {"error": "not a valid or supported reference..."}


@app.get("/cellar-by-eli/{elipath:path}/{language}/{format}")
def eli(elipath: str = "http://data.europa.eu/eli/reg/2018/1805/oj", language: str = "NLD", format: str = "fmx4"):
    """
    Same as the /cellar-by-celex endpoint but using a ELI reference to EU CELLAR instead of a CELEX reference.
    
    Example ELI reference: http://data.europa.eu/eli/reg/2018/1805/oj/nld/fmx4
    
    Note that currently due to a CORS issue in swagger the redirect causes a TypeError: Load failed to show up as response. 
    Try opening the request url shown in swagger to see the actual response you get by using the CPRMV API directly. 
    """
    print("cellar by eli")
    language = language.upper()
    format = format.lower()
    cellarurl = f"https://publications.europa.eu/webapi/rdf/sparql?default-graph-uri=&query=prefix+cdm%3A+%3Chttp%3A%2F%2Fpublications.europa.eu%2Fontology%2Fcdm%23%3E+%0D%0Aprefix+purl%3A+%3Chttp%3A%2F%2Fpurl.org%2Fdc%2Felements%2F1.1%2F%3E+%0D%0Aselect+distinct+%3Fitem%0D%0Awhere+%7B%0D%0A%3Fwork+cdm%3Aresource_legal_eli+%22{elipath}%22%5E%5E%3Chttp%3A%2F%2Fwww.w3.org%2F2001%2FXMLSchema%23anyURI%3E+.%0D%0A%3Fexpr+cdm%3Aexpression_belongs_to_work+%3Fwork+%3B%0D%0Acdm%3Aexpression_uses_language+%3Flang+.%0D%0A%3Flang+purl%3Aidentifier+%3FlangCode+.%0D%0A%3Fmanif+cdm%3Amanifestation_manifests_expression+%3Fexpr%3B%0D%0Acdm%3Amanifestation_type+%3Fformat.%0D%0A%3Fitem+cdm%3Aitem_belongs_to_manifestation+%3Fmanif.%0D%0AFILTER%28str%28%3FlangCode%29%3D%22{language}%22+%26%26+str%28%3Fformat%29%3D%22{format}%22%29%0D%0A%7D+LIMIT+100&format=application%2Fjson&timeout=0&debug=on&run=+Run+Query+"
    print(cellarurl)
    response = RedirectResponse(url=cellarurl)
    return response

@app.get("/cellar-by-celex/{celexid}")
def celex(celexid: str = "32018R1805", language: str = "NLD", format: str = "fmx4"):
    """
    Gives a URL to the SPARQL endpoint of the European CELLAR repository
    running a specific query that finds publications ('work' in terms of
    the EU's Common Data Model) identified by the given CELEX id (for instance
    02016R0679-20160504 for the consolidated GDPR Act, or an example that
    is given on the EU website: 32018R1805) for a given language
    (defaults to Dutch ("NLD")) and finds the manifestation items with
    the given format (defaults to the EU's Formex 4 standard ("fmx4")).
    This can give you multiple entries (URI's) to the specific parts of
    the work. The result will show corresponding ruleset id's that can
    be used with this api (work in progress) for the given URI's
    (with which you can inspect the given documents).

    Note that currently only CELLAR URL's will be shown.. the corresponding
    ruleset id is the part after 'https://publications.europa.eu/resource/cellar/',
    which needs to be converted to the ruleset id this api can work with
    (for usage of it with the /rules endpoint) by prepending the prefix "CFMX4" and
    changing the '/' into a '_'. For example: the publication (you can open this
    in the browser)
    'http://publications.europa.eu/resource/cellar/83e4752e-f2e5-11e8-9982-01aa75ed71a1.0017.02/DOC_2'
    can be used to forge the rule set id:
    'CFMX483e4752e-f2e5-11e8-9982-01aa75ed71a1.0017.02_DOC_2'
    (Note this will be improved so you do not have to do this yourselves)
    
    Also note that currently due to a CORS issue in swagger the redirect causes a TypeError: Load failed to show up as response. 
    Try opening the request url shown in swagger to see the actual response you get by using the CPRMV API directly. 
    """
    cellarurl = f"https://publications.europa.eu/webapi/rdf/sparql?default-graph-uri=&query=prefix+cdm%3A+%3Chttp%3A%2F%2Fpublications.europa.eu%2Fontology%2Fcdm%23%3E+%0D%0Aprefix+purl%3A+%3Chttp%3A%2F%2Fpurl.org%2Fdc%2Felements%2F1.1%2F%3E+%0D%0Aselect+distinct+%3Fitem%0D%0Awhere+%7B%0D%0A%3Fwork+owl%3AsameAs+%3Chttp%3A%2F%2Fpublications.europa.eu%2Fresource%2Fcelex%2F{celexid}%3E+.%0D%0A%3Fexpr+cdm%3Aexpression_belongs_to_work+%3Fwork+%3B%0D%0Acdm%3Aexpression_uses_language+%3Flang+.%0D%0A%3Flang+purl%3Aidentifier+%3FlangCode+.%0D%0A%3Fmanif+cdm%3Amanifestation_manifests_expression+%3Fexpr%3B%0D%0Acdm%3Amanifestation_type+%3Fformat+.%0D%0A%3Fitem+cdm%3Aitem_belongs_to_manifestation+%3Fmanif.%0D%0AFILTER%28str%28%3FlangCode%29%3D%22{language}%22+%26%26+str%28%3Fformat%29%3D%22{format}%22%29%0D%0A%7D+LIMIT+100&format=application%2Fjson&timeout=0&debug=on&run=+Run+Query+"
    print(cellarurl)
    response = RedirectResponse(url=cellarurl)
    return response


# Tip: use https://publications.europa.eu/webapi/rdf/sparql to edit the SPARQL query in the URL above (you get the URI in a new browser window by executing the query):
"""
prefix cdm: <http://publications.europa.eu/ontology/cdm#> 
prefix purl: <http://purl.org/dc/elements/1.1/> 
select distinct ?item
where {
?work owl:sameAs <http://publications.europa.eu/resource/celex/32018R1805> .
?expr cdm:expression_belongs_to_work ?work ;
cdm:expression_uses_language ?lang .
?lang purl:identifier ?langCode .
?manif cdm:manifestation_manifests_expression ?expr;
cdm:manifestation_type ?format.
?item cdm:item_belongs_to_manifestation ?manif.
FILTER(str(?langCode)="NLD" && str(?format)="fmx4")
} LIMIT 100

or for the eli version:

prefix cdm: <http://publications.europa.eu/ontology/cdm#> 
prefix purl: <http://purl.org/dc/elements/1.1/> 
select distinct ?item
where {
?work cdm:resource_legal_eli "http://data.europa.eu/eli/reg/2018/1805/oj"^^<http://www.w3.org/2001/XMLSchema#anyURI> .
?expr cdm:expression_belongs_to_work ?work ;
cdm:expression_uses_language ?lang .
?lang purl:identifier ?langCode .
?manif cdm:manifestation_manifests_expression ?expr;
cdm:manifestation_type ?format.
?item cdm:item_belongs_to_manifestation ?manif.
FILTER(str(?langCode)="NLD" && str(?format)="fmx4")
} LIMIT 100
"""

# as_seen_on (zichtdatum) argument not implemented. Always defaults to default used in SRU service which is "today" .. only implemented for AnalysisMethods, not the non-FRBR methods
def find_publication_version_valid_on_date(date, method, as_seen_on=datetime.now().strftime('%Y-%m-%d')):
    date_ts = ciso8601.parse_datetime(date)
    frbr_sru_url_format = str(method[CPRMVSERVE["frbr-repository-sru-url"]])
    frbr_valid_from_term_ns = str(method[CPRMVSERVE["frbr-repository-sru-response-from-date-term-namespace"]])
    frbr_valid_from_term = str(method[CPRMVSERVE["frbr-repository-sru-response-from-date-term"]])
    fvft_prefix = 'fvft'
    frbr_valid_from_xpath = '//'+fvft_prefix+':'+frbr_valid_from_term
    frbr_sru_response_publoc_term_ns = str(method[CPRMVSERVE["frbr-repository-sru-response-publication-location-term-namespace"]])
    frbr_sru_response_publoc_term = str(method[CPRMVSERVE["frbr-repository-sru-response-publication-location-term"]])
    fsrpt_prefix = 'fsrpt'
    frbr_publoc_format = str(method[CPRMVSERVE["repository-publication-location-format"]])
    frbr_publoc_xpath = '//'+fsrpt_prefix+':'+frbr_sru_response_publoc_term 
    sru_url = frbr_sru_url_format.format_map(method[CPRMVSERVE["id_parts"]])
    methodLabel = method[CPRMV.label]
    try:
        print(f"retrieving versioning information through SRU service: {sru_url}")
        req = Request(sru_url)
        response = urlopen(req, context=SSL_CONTEXT)
        print("Saving response from SRU")
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            shutil.copyfileobj(response, tmp_file)
            tmp_file.close()
            print(f"opening publication versioning information from temp file {tmp_file.name}")
            try:
                xml = etree.parse(open(tmp_file.name))
            except Exception as e:
                print('Exception parsing sru response: '+str(e))
                raise Exception(f"error parsing retrieved publication versioning information.")
            print("succesfull parse of sru response")
            try:
                found_date = 'unknown'
                found_index = 'unknown'
                for expr in xml.xpath(frbr_valid_from_xpath, namespaces={fvft_prefix : frbr_valid_from_term_ns}):
                    found_date = expr.text
                    if not valid_date(found_date):
                        print("invalid publication valid-from date found: "+found_date)
                        raise Exception('SRU response contained invalid publication valid-from date.')
                    break
                print('publication valid-from date found: '+found_date)
                for expr in xml.xpath(frbr_publoc_xpath, namespaces={fsrpt_prefix : frbr_sru_response_publoc_term_ns}):
                    publoc = expr.text
                    print(f"Parsing (frbr) repository-publication-location-format ({frbr_publoc_format}) on value from SRU response: {publoc}")
                    result = parse(frbr_publoc_format, publoc)
                    if result is not None:
                        parts = result.named
                        if 'index' in parts:
                            found_index = parts['index']
                        else:
                            raise Exception('Error parsing frbr-repository-publication-location-format. No index value configured or found...')
                        print(f"found publication index: "+found_index)
                    else:
                        raise Exception('SRU response contained unexpected publication location url.')
                    break
                print('Processed SRU response. valid-from date and index found')
            except Exception as e:
                print("Exception processing SRU response: "+str(e))
                raise Exception(f'error processing retrieved publication versioning information..'+str(e))
            print(f"latest version found: {found_date}_{found_index}")
            os.remove(tmp_file.name)
            return {"date" : found_date, "index" : found_index}
    except URLError as e:
        if hasattr(e, "reason"):
            print("We failed to reach a server.")
            print("Reason: ", e.reason)
            raise e
        elif hasattr(e, "code"):
            print("The server couldn't fulfill the request.")
            print("Error code: ", e.code)
            raise e
    except Exception as e:
        print("Error finding publication versioning information: "+str(e))
        raise e
    raise Exception(f"unknown error finding publication versioning information...")


def valid_date(datestr):
    try:
        datetime.fromisoformat(datestr)
    except:
        return False
    return True

def get_mapping(referencemethod):
    cprmvMethods = app.cprmvsettings["CPRMVMETHODS_KG"]
    result = {}
    mapping = cprmvMethods.value(predicate=CPRMVSERVE["reference-mapping"], subject=referencemethod, any=False)
    while mapping is not None and mapping != RDF.nil:
        try:
            item = cprmvMethods.value(mapping, RDF.first)
            key = cprmvMethods.value(item, RDF.first)
            value = cprmvMethods.value(cprmvMethods.value(item, RDF.rest), RDF.first)
        except:
            print("unexpected structure in reference mapping knowledge for reference method id:"+str(cprmvMethods.value(referencemethod, CPRMVSERVE["id"])))
            return {}
        result[str(key)] = str(value)
        mapping = cprmvMethods.value(mapping, RDF.rest)
    return result

def transform_jci_reference(method_config, reference_parts):
    if 'subversion' not in reference_parts:
        print("Invalid call to transform_jci_reference. No subversion part in reference parts...")
        return None
    if reference_parts['subversion'] not in ('3','31'):
        print("No valid juriconnect version (must be 1.3 or 1.31)")
        return None
    path = '/rules/'
    cprmvMethods = app.cprmvsettings["CPRMVMETHODS_KG"]
    id_format = str(cprmvMethods.value(CPRMVMETHODS.bwb, CPRMVSERVE['normalized-id-format']))
    id_parts = {}
    mapping = get_mapping(method_config)
    if len(reference_parts['bwbid']) != 8:
        return None
    locstr = reference_parts['locatie-string']
    locstr_path = ''
    delim = ''
    for part in locstr.split('&'):
        kv = part.split('=')
        if len(kv) != 2:
            return None
        if kv[0] == mapping[str(CPRMVSERVE['reference-mapping-valid-on'])]:
            id_parts['date'] = kv[1]
        elif kv[0] == mapping[str(CPRMVSERVE['reference-mapping-seen-on'])]:
            id_parts['index'] = kv[1]
        elif kv[0] in mapping:
            locstr_path = locstr_path+delim+mapping[kv[0]]+'%20'+kv[1]
            delim = '%2C'
    id_parts['rulesetid'] = reference_parts['bwbid'].upper()
    if 'date' not in id_parts:
        id_parts['date'] = datetime.now().strftime('%Y-%m-%d')
    if 'index' not in id_parts:
        id_parts['index'] = 'latest'
    return path+id_format.format_map(id_parts)+'%2C'+locstr_path

def transform_cprmvapi_reference(method_config, reference_parts):
    path = reference_parts['path'].replace('/',', ')
    return '/rules/'+path
    
def transform_eli_reference(method_config, reference):
    result = None
    language='NLD'
    format='fmx4'
    cellarurl = f"https://publications.europa.eu/webapi/rdf/sparql?default-graph-uri=&query=prefix+cdm%3A+%3Chttp%3A%2F%2Fpublications.europa.eu%2Fontology%2Fcdm%23%3E+%0D%0Aprefix+purl%3A+%3Chttp%3A%2F%2Fpurl.org%2Fdc%2Felements%2F1.1%2F%3E+%0D%0Aselect+distinct+%3Fitem%0D%0Awhere+%7B%0D%0A%3Fwork+cdm%3Aresource_legal_eli+%22{reference}%22%5E%5E%3Chttp%3A%2F%2Fwww.w3.org%2F2001%2FXMLSchema%23anyURI%3E+.%0D%0A%3Fexpr+cdm%3Aexpression_belongs_to_work+%3Fwork+%3B%0D%0Acdm%3Aexpression_uses_language+%3Flang+.%0D%0A%3Flang+purl%3Aidentifier+%3FlangCode+.%0D%0A%3Fmanif+cdm%3Amanifestation_manifests_expression+%3Fexpr%3B%0D%0Acdm%3Amanifestation_type+%3Fformat.%0D%0A%3Fitem+cdm%3Aitem_belongs_to_manifestation+%3Fmanif.%0D%0AFILTER%28str%28%3FlangCode%29%3D%22{language}%22+%26%26+str%28%3Fformat%29%3D%22{format}%22%29%0D%0A%7D+LIMIT+100&format=application%2Fjson&timeout=0&debug=on&run=+Run+Query+"
    print(f"querying EU CELLAR: {cellarurl}")
    with urlopen(cellarurl, context=SSL_CONTEXT) as response:
        data = response.read().decode('utf-8')
        json_data = json.loads(data)
        print(json_data)
        if 'results' in json_data and 'bindings' in json_data['results'] and len(json_data['results']['bindings']) > 0 and 'item' in json_data['results']['bindings'][0] and 'value' in json_data['results']['bindings'][0]['item']:
            result = json_data['results']['bindings'][0]['item']['value']
    return result
    
def transform_elinl_reference(method_config, reference_parts):
    path = reference_parts['path'].replace('/',', ')
    return '/rules/'+path
    
def detect_cprmv_serve_reference_method_and_transform(reference):
    cprmvMethods = app.cprmvsettings["CPRMVMETHODS_KG"]
    result = None
    methods = cprmvMethods.value(CPRMVMETHODS.referencemethods, CPRMV.acknowledged)
    while methods != RDF.nil:
        method_config = cprmvMethods.value(methods, RDF.first)
        reference_method_id = str(cprmvMethods.value(method_config , CPRMV["id"]))
        referenceformat = str(cprmvMethods.value(method_config , CPRMVSERVE["reference-format"]))
        refresult = parse(referenceformat, reference)
        print(reference_method_id+' '+referenceformat+' '+reference)
        if refresult is not None:
            if reference_method_id == 'Juriconnect':
                result = transform_jci_reference(method_config , refresult)
            elif reference_method_id == 'ELIFMX4 on EU CELLAR':
                result = transform_eli_reference(method_config , reference)
            elif reference_method_id == 'ELI for BWB and CVDR':
                result = transform_elinl_reference(method_config , refresult)
            elif reference_method_id == 'CPRMV API - rule id path':
                result = transform_cprmvapi_reference(method_config , refresult)
            print(refresult)
            if result is not None:
                break
        methods = cprmvMethods.value(methods, RDF.rest)
    if result is None:
        print('Could not detect reference: invalid, unknown or unsupported reference type')
    return result

# finds the first acknowledged RuleMethod of given category (AnalysisMethod (default) / FormalisationMethod uri's) supported by CPRMV Serve for which the given cprmvid matches the id format defined in the cprmvmethods value lists
# returns all the information on the matching method as a Dictionary in which also the unformatted cprmvid (one or more key/values) is added under the CPRMV.id key
def detect_cprmv_serve_acknowledged_method(cprmvid, category = CPRMVMETHODS.analysismethods):
    cprmvMethods = app.cprmvsettings["CPRMVMETHODS_KG"]
    result = None
    methods = cprmvMethods.value(category, CPRMV.acknowledged)
    while methods != RDF.nil:
        method = cprmvMethods.value(methods, RDF.first)
        idformat = cprmvMethods.value(method, CPRMVSERVE["publication-id-format"])
        normalized_idformat = cprmvMethods.value(method, CPRMVSERVE["normalized-id-format"])
        if idformat is not None and normalized_idformat is not None:
            cprmvid_official = cprmvid
            print(f"detect for {cprmvid}")
            cprmvid_normalized = normalize_ruleset_id(cprmvid)
            print(f"Parsing {normalized_idformat} on value {cprmvid_normalized}")
            result = parse(normalized_idformat, cprmvid_normalized)
            if result is not None:
                methodTriples = {}
                for p, o in cprmvMethods.predicate_objects(method):
                    methodTriples[p] = o
                methodTriples[CPRMVSERVE['id_parts']] = result.named
                if 'index' in methodTriples[CPRMVSERVE['id_parts']] and methodTriples[CPRMVSERVE['id_parts']]['index'] == 'latest':
                    if 'date' in methodTriples[CPRMVSERVE['id_parts']] and valid_date(methodTriples[CPRMVSERVE['id_parts']]['date']):
                        methodTriples[CPRMVSERVE['id_parts']]['valid-on'] = methodTriples[CPRMVSERVE['id_parts']]['date']
                    else:
                        methodTriples[CPRMVSERVE['id_parts']]['valid-on'] = datetime.now().strftime('%Y-%m-%d')
                    print(f"searching latest version valid on date: {methodTriples[CPRMVSERVE['id_parts']]['valid-on']}")
                    version = find_publication_version_valid_on_date(methodTriples[CPRMVSERVE['id_parts']]['valid-on'], methodTriples)
                    methodTriples[CPRMVSERVE['id_parts']]['date'] = version['date']
                    methodTriples[CPRMVSERVE['id_parts']]['index'] = version['index']
                    cprmvid_official = idformat.format_map(methodTriples[CPRMVSERVE['id_parts']])
                methodTriples[CPRMVSERVE['id_parts']]['cprmvid'] = cprmvid_official
                result = methodTriples
                break
        methods = cprmvMethods.value(methods, RDF.rest)
    return result

def get_cprmv_rule_set_from_publication(g, method):
    cprmvid = method[CPRMVSERVE["id_parts"]]['cprmvid']
    puburlformat = str(method[CPRMVSERVE["repository-publication-location-format"]])
    puburl = puburlformat.format_map(method[CPRMVSERVE["id_parts"]])
    methodLabel = method[CPRMV.label]
    try:
        print(f"downloading publication: {puburl}")
        req = Request(puburl)
        response = urlopen(req, context=SSL_CONTEXT)
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            shutil.copyfileobj(response, tmp_file)
            tmp_file.close()
            print(f"opening publication from temp file {tmp_file.name}")
            xml = etree.parse(open(tmp_file.name))
            print(f"transforming {methodLabel} resource into CPRMV RuleSet ...")
            ac = etree.XSLTAccessControl(read_network=False, read_file=False)
            transform = etree.XSLT(
                etree.parse(method[CPRMVSERVE.xslt]), access_control=ac
            )
            result = str(transform(xml, cprmvid=etree.XSLT.strparam(cprmvid), puburl=etree.XSLT.strparam(puburl)))
            os.remove(tmp_file.name)
            # print(result)
            g.parse(data=result, format="turtle")
            return
    except URLError as e:
        if hasattr(e, "reason"):
            print("We failed to reach a server.")
            print("Reason: ", e.reason)
            raise e
        elif hasattr(e, "code"):
            print("The server couldn't fulfill the request.")
            print("Error code: ", e.code)
            raise e
    else:
        raise Exception(f"unknown error loading {methodLabel} publication ...")


# load the requested publication from the official repository and transform it to CPRMV and load it
def load_rule_set(method):
    g = Graph()
    try:
        get_cprmv_rule_set_from_publication(g, method)
    except Exception as e:
        if (
            "unbound prefix" in str(e).lower()
        ):  # TODO maybe this should not be ignonred always
            print(f"Warning: ignoring unbound prefix encountered: {e}")
        else:
            raise e
    return g


@with_pattern(r".+")
def param_value(pvalue):
    return pvalue

def normalize_ruleset_id(rulesetid):
    print("normalizing id: "+rulesetid)
    if rulesetid.find('_') < 0:
        rulesetid = rulesetid+'_now_latest'
    splitted = rulesetid.split('_')
    if len(splitted) == 2:
        rulesetid = splitted[0]+'_na_'+splitted[1]
    print("normalizedid: "+rulesetid)
    return rulesetid

# detect any supported type of method (either Analysis and or Formalisation methods)
def detect_cprmv_serve_method(cprmvid):
    method = detect_cprmv_serve_acknowledged_method(cprmvid, CPRMVMETHODS.analysismethods)
    print('A method detected')
    if method is None:
        # currently this implies dmn13 method which needs to split up the rulesetid in a deployment and resource id. TODO This should be supported in a better way than the quick hack below
        originalId = cprmvid
        deploymentid = ''
        resourceid = ''
        cprmvid = cprmvid.split('_')
        if len(cprmvid) == 4:
            operatonids = cprmvid[1].split('R')
            if len(operatonids) == 2:
                deploymentid = operatonids[0]
                resourceid = operatonids[1]
        method = detect_cprmv_serve_acknowledged_method(originalId, CPRMVMETHODS.formalisationmethods)
        if method is not None:
            method[CPRMVSERVE["id_parts"]]['deploymentid'] = deploymentid
            method[CPRMVSERVE["id_parts"]]['resourceid'] = resourceid
    return method

def get_rules(
    rule_id_path="",
    path_delimiter: str = ",",
    formatarg: str = "cprmv-json",
    unformat: str = "",
):
    if formatarg not in ['cprmv-json', 'json-ld', 'turtle', 'n3', 'xml', 'ttl', 'turtle2']:
        print('Info: using default format cprmv-json...')
        formatarg = "cprmv-json"
    try:
        delimindex = rule_id_path.find(path_delimiter)
        print(delimindex)
        if delimindex > 0:
            rulesetid = rule_id_path[:delimindex].strip()
        else:
            rulesetid = rule_id_path.strip()
        print(f"Info: retrieving info for cprmv:RuleSet : {rulesetid}")
        method = detect_cprmv_serve_method(rulesetid)
        if method is not None:
            g = load_rule_set(method)
            print(f"replacing {rulesetid} with {method[CPRMVSERVE['id_parts']]['cprmvid']} in {rule_id_path}")
            rule_id_path = rule_id_path.replace(rulesetid, method[CPRMVSERVE["id_parts"]]['cprmvid']) # the actual latest rulesetid might have been searched and found
        else:
            raise Exception(
                "No supported publication repository use identifiers with the format of the given Ruleset Id."
            )
    except Exception as e:
        return json.dumps({"error": str(e)})
    print(f"processing starts at first rule in path {rule_id_path}")
    r = get_first_rule_by_id_path(g, rule_id_path, path_delimiter)
    if r is None:
        return "No rules found for given path..."
    r2 = g.value(r, CPRMV.hasPart)
    r2 = g.value(r2, RDF.first)
    r2id = g.value(r2, CPRMV.id)
    print(f"rule found {r2id}")
    
    if unformat != "":
        definition = g.value(r2, CPRMV.definition)
        if definition is not None:
            string_definition = str(
                " ".join(definition.split())
            )  # transform no break spaces in regular ones
            definition: Result | Match | None = search(
                unformat, string_definition, extra_types={"param_value": param_value}
            )
            if definition is not None:
                named_definition: Definition = definition.named
                named_definition["rulesetid"] = rulesetid
                named_definition["rule_id_path"] = rule_id_path
                prefix, namespace, local_name = g.namespace_manager.compute_qname(r)
                for key in named_definition:
                    g.add((r2, URIRef(namespace+key), Literal(named_definition[key])))
    
    if formatarg == "cprmv-json":
        result = get_rule(
            g, r
        )  # this custom format has a more human readable pretty print layout
    else:
        # The Concise Bounded Description of the RuleSet does not include the
        # triples of the named cprmv:RuleMethod it points to (those live in the
        # separate CPRMVMETHODS_KG graph). Without them the published Turtle would
        # fail SHACL: RuleSetShape requires cprmv:hasMethod to resolve to a typed
        # cprmv:RuleMethod, and RuleMethodShape requires that method to carry a
        # cprmv:id. So copy the method's cprmv-vocabulary triples (type/id/comment)
        # into the output graph and assert the cprmv:RuleMethod type explicitly
        # (the shapes carry no rdfs:subClassOf entailment, so the specific subtype
        # alone — e.g. cprmv:AnalysisMethod — is not sufficient). Only the type and
        # id are copied: cprmv:comment is optional and RuleMethodShape constrains it
        # to xsd:string, which the language-tagged method comments would violate.
        out = g.cbd(r)
        methods_kg = app.cprmvsettings["CPRMVMETHODS_KG"]
        for method in set(out.objects(None, CPRMV.hasMethod)):
            out.add((method, RDF.type, CPRMV.RuleMethod))
            for p, o in methods_kg.predicate_objects(method):
                if p in (RDF.type, CPRMV.id):
                    out.add((method, p, o))
        result = out.serialize(format=formatarg)
    if (type(result) != str):
        result = json.dumps(result, indent=4, ensure_ascii=False)
    return result


# depth first search in the given graph g for the first rule matching the given path (the path splitted as a list) from the given rootrule
# the found (sub)Rule will be nested as such within the root item which is always a RuleSet
def get_first_rule_by_id_path(g, path, path_delimiter: str = ","):
    pathsplit = path.split(path_delimiter)
    firstid = pathsplit.pop(0).strip()
    firstroot = None
    for rootrule in g.subjects(CPRMV.id, Literal(firstid, lang="nl")):
        if firstroot is None:
            firstroot = rootrule
        rule = get_first_rule_by_Id_path_split_from_rule_as_root(g, rootrule, pathsplit)
        if rule is not None:
            if rule != firstroot:
                subrules = g.value(firstroot, CPRMV.hasPart)
                g.remove((firstroot, CPRMV.hasPart, subrules))
                subrules = BNode()
                g.add((subrules, RDF.first, rule))
                g.add((subrules, RDF.rest, RDF.nil))
                g.add((firstroot, CPRMV.hasPart, subrules))
                return firstroot
            else:
                return rule
    return None


# recursive depth first search in the given graph g for the first rule matching the path (the path splitted as a list) from the given rootrule
def get_first_rule_by_Id_path_split_from_rule_as_root(g, rootrule, pathsplit):
    if len(pathsplit) == 0:
        return rootrule
    rulelist = g.value(rootrule, CPRMV.hasPart)
    if rulelist is None:
        return None
    while rulelist != RDF.nil:
        rule = g.value(rulelist, RDF.first)
        ruleid = g.value(rule, CPRMV.id)
        if ruleid is not None:
            ruleid = ruleid.toPython()
            ruleid = "".join(
                c for c in ruleid if c.isalnum()
            )  # look only at alphanumeric characters
        id = pathsplit.pop(0)
        id = "".join(
            c for c in id if c.isalnum()
        )  # look only at alphanumeric characters
        subrule = None
        if ruleid == id:
            subrule = get_first_rule_by_Id_path_split_from_rule_as_root(
                g, rule, pathsplit
            )
            pathsplit.insert(0, id)
        else:
            pathsplit.insert(0, id)
            subrule = get_first_rule_by_Id_path_split_from_rule_as_root(
                g, rule, pathsplit
            )
        if subrule is not None:
            return subrule
        rulelist = g.value(rulelist, RDF.rest)
    return None


# retrieves all info of the given rule (and all its subrules from the given graph by default. Use includeSubRules=False when no subrules need to be returned instead).
# Note that rule structures over CPRMV.hasPart relations should be trees, so no cyclic graphs, otherwise this method will not stop.
def get_rule(g, rule, includeSubRules=True):
    r = {}
    for p, o in g.predicate_objects(rule):
        if includeSubRules and p == CPRMV.hasPart:
            r[p] = {}
            item = o
            while item != RDF.nil:
                firstitem = g.value(item, RDF.first)
                subid = g.value(firstitem, CPRMV.id)
                r[p][subid] = get_rule(g, firstitem)
                item = g.value(item, RDF.rest)
        else:
            r[p] = o
    return r


mcp = FastApiMCP(app)
mcp.mount_http()
