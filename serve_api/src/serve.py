from contextlib import asynccontextmanager
from contextvars import ContextVar
from fastmcp import FastMCP
from fastapi import FastAPI, Depends, Request as FastAPIRequest
from fastapi.security import APIKeyHeader
from rdflib import Graph, BNode, URIRef
from rdflib.term import Literal
from rdflib.namespace import RDF, RDFS
from typing import Union
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.responses import PlainTextResponse
from fastapi.responses import FileResponse
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
import sys
import importlib
import inspect
import pkgutil
from starlette.datastructures import Headers

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

mcp_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    if mcp_app is not None:
        async with mcp_app.lifespan(app):
            yield
    else:
        yield

app = FastAPI(
    title="CPRMV Rules Serve API",
    description="This API allows fetching CPRMV RuleSets from acknowledged publication methods part of the CPRMV Instruments catalog configured for this CPRMV API instance. See the CPRMV project website for more information (The link below links to the ReSpec documentation for CPRMV)",
    version="0.4.4",
    lifespan=lifespan,
    contact={
        "name": "CPRMV project",
        "url": "https://cprmv.open-regels.nl/respec/",
        "email": "Bas.Kaptijn@ictu.nl",
    },
    license_info={
        "name": "EUPL",
        "url": "https://git.open-regels.nl/standards/cprmv/-/blob/main/LICENSE?ref_type=heads",
    },
)

# load knowledge about CPRMV and CPRMV Methods into memory
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

app.SSL_CONTEXT = SSL_CONTEXT

# Holds the headers for the currently executing request
app.current_request_headers = ContextVar(
    "current_request_headers", default=Headers()
)
# Define the custom header name (as a feature for the core_api module)
header_scheme = APIKeyHeader(name="x-api-key", auto_error=False)

@app.middleware("http")
async def store_request_headers(request: FastAPIRequest, call_next):
    token = app.current_request_headers.set(request.headers)
    try:
        return await call_next(request)
    finally:
        app.current_request_headers.reset(token)

@app.get("/")
def cprmv_info():
    """
    returns basic app information (title and version)
    """
    return {app.title: app.version}

# respec documentation on CPRMV and CPRMV Methods endpoint
app.mount("/respec", StaticFiles(directory="respec", html=True, follow_symlink=True), name="respec")

# endpoint for retrieving all information on CPRMV Methods and CPRMV itself
# which can be combined with information retrieved through the /rules endpoint
# also, a method name can be given (as defined in wither cprmvmethods or cprmv-serve namespaces) to get only the RDF knowledge for that given method
@app.get("/methods")
@app.get("/0.4.4/methods/{method_name}")
def methods(method_name: str | None = None, format: str = "json-ld"):
    if format in ["json-ld", "xml", "turtle", "ttl", "n3", "turtle2"]:
        g = Graph()
        if method_name is not None:
            if method_name.startswith('core'):
                m = app.cprmvsettings["CPRMVMETHODS_KG"].value(predicate=RDF.type, object=CPRMVSERVE[method_name])
            else:
                m = app.cprmvsettings["CPRMVMETHODS_KG"].value(predicate=RDF.type, object=CPRMVMETHODS[method_name])
            g = iterative_cbd(app.cprmvsettings["CPRMVMETHODS_KG"], m)
        else:
            g = app.cprmvsettings["CPRMVMETHODS_KG"]
        return PlainTextResponse(g.serialize(format=format))

@app.get("/rules/{rule_id_path}")
def rules(
    rule_id_path: str = RULE_ID_PATH,
    path_delimiter: str = PATH_DELIMITER,
    format: str = FORMAT,
    _language: Union[str, None] = LANGUAGE,
    unformat: str = UNFORMAT,
    api_key: None | str = Depends(header_scheme)
):
    """
    Returns the Rule(Set) including all Rules that are part of it and that can be found as indicated in the given Rule Id Path,
    which is the default reference method for the CPRMV API. Use the /ref endpoint for other supported references.

    With this endpoint, amongst other features, you can retrieve a selection of rules from any type of publication that can be seen as a rule set
    from various official publication repositories as upported by this CPRMV API instance (depending on its configuration).
    A ruleset from such repositories is transformed into a knowledge graph in which the retrieved publication is split into related
    and identifiable rule's at least in the tree structure that is formed by these rule's matching how the publication gets serialised.

    The ReSpec documentation of the CPRMV can be found under the /respec endpoint which contains information about all known (publication) methods
    that define what can be retrieved and how through this endpoint, also depending on the configuration of this API instance, which can be retrieved
    through the /methods endpoint.

    When supported, this API can be used to adopt the CPRMV standard for repositories that do not yet. It requires that publications at least can be linked
    to the organisation (the competent authority) that created the rules in the publication in some way such that a defined method module for this API can
    add CPRMV metadata.

    It is possible to have this API not transform the publication and select parts from it but instead just pass through the whole original publication referenced.
    In this case use the /raw endpoint.
    """
    if api_key is not None:
        headers = dict(app.current_request_headers.get())
        headers['x-api-key'] = api_key
        app.current_request_headers.set(headers)
    return PlainTextResponse(get_rules(rule_id_path, path_delimiter, format, unformat))

@app.get("/raw/{rule_id_path}")
def rules(
    rule_id_path: str = RULE_ID_PATH,
    path_delimiter: str = PATH_DELIMITER,
    api_key: None | str = Depends(header_scheme)
):
    """
    Retrieves the raw publication that forms a Ruleset referenced in the given Rule Id Path,
    which is the default reference method for the CPRMV API. Use the /ref endpoint for other supported references.

    The ReSpec documentation of the CPRMV can be found under the /respec endpoint which contains information about all known (publication) methods
    that define what can be retrieved and how through this endpoint, also depending on the configuration of this API instance, which can be retrieved
    through the /methods endpoint.

    When supported, this API can also be used to adopt the CPRMV standard for repositories that do not yet. It requires that publications at least can be linked
    to the organisation (the competent authority) that created the rules in the publication in some way such that a defined method module for this API can
    add CPRMV metadata.

    It is possible to have this API transform the publication into a CPRMV compliant knowledge graph and amongst other features select parts from it instead of
    just pass through the whole original publication referenced.
    In this case use the /rules endpoint.

    """
    if api_key is not None:
        headers = dict(app.current_request_headers.get())
        headers['x-api-key'] = api_key
        app.current_request_headers.set(headers)
    pubfile, friendlyname = get_raw_publication(rule_id_path, path_delimiter)
    if os.path.isfile(pubfile):
        return FileResponse(
            path=pubfile,
            filename=friendlyname,
        )
    else:
        return PlainTextResponse(pubfile)

@app.get("/ref")
def ref(
    reference : str = "",
    api_key: None | str = Depends(header_scheme)
):
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
    headers = {}
    if api_key is not None:
        headers = dict(app.current_request_headers.get())
        headers['x-api-key'] = api_key
        app.current_request_headers.set(headers)
    redirect_url = detect_cprmv_serve_reference_method_and_transform(reference)
    if redirect_url is not None:
        response = RedirectResponse(
            url=redirect_url,
            headers = app.current_request_headers.get()
        )
        return response
    return {"error": "not a valid or supported reference..."}

# old deprecated helper endpoints for which the /ref endpoint came in place
# helper endpoint
# @app.get("/cellar-by-eli/{elipath:path}/{language}/{format}")
# def eli(elipath: str = "http://data.europa.eu/eli/reg/2018/1805/oj", language: str = "NLD", format: str = "fmx4"):
#    """
#    Same as the /cellar-by-celex endpoint but using a ELI reference to EU CELLAR instead of a CELEX reference.
#
#    Example ELI reference: http://data.europa.eu/eli/reg/2018/1805/oj/nld/fmx4
#
#    Note that currently due to a CORS issue in swagger the redirect causes a TypeError: Load failed to show up as response.
#    Try opening the request url shown in swagger to see the actual response you get by using the CPRMV API directly.
#    """
#    print("cellar by eli")
#    language = language.upper()
#    format = format.lower()
#    cellarurl = f"https://publications.europa.eu/webapi/rdf/sparql?default-graph-uri=&query=prefix+cdm%3A+%3Chttp%3A%2F%2Fpublications.europa.eu%2Fontology%2Fcdm%23%3E+%0D%0Aprefix+purl%3A+%3Chttp%3A%2F%2Fpurl.org%2Fdc%2Felements%2F1.1%2F%3E+%0D%0Aselect+distinct+%3Fitem%0D%0Awhere+%7B%0D%0A%3Fwork+cdm%3Aresource_legal_eli+%22{elipath}%22%5E%5E%3Chttp%3A%2F%2Fwww.w3.org%2F2001%2FXMLSchema%23anyURI%3E+.%0D%0A%3Fexpr+cdm%3Aexpression_belongs_to_work+%3Fwork+%3B%0D%0Acdm%3Aexpression_uses_language+%3Flang+.%0D%0A%3Flang+purl%3Aidentifier+%3FlangCode+.%0D%0A%3Fmanif+cdm%3Amanifestation_manifests_expression+%3Fexpr%3B%0D%0Acdm%3Amanifestation_type+%3Fformat.%0D%0A%3Fitem+cdm%3Aitem_belongs_to_manifestation+%3Fmanif.%0D%0AFILTER%28str%28%3FlangCode%29%3D%22{language}%22+%26%26+str%28%3Fformat%29%3D%22{format}%22%29%0D%0A%7D+LIMIT+100&format=application%2Fjson&timeout=0&debug=on&run=+Run+Query+"
#    print(cellarurl)
#    response = RedirectResponse(url=cellarurl)
#    return response

# helper endpoint
#@app.get("/cellar-by-celex/{celexid}")
#def celex(celexid: str = "32018R1805", language: str = "NLD", format: str = "fmx4"):
#    """
#    Gives a URL to the SPARQL endpoint of the European CELLAR repository
#    running a specific query that finds publications ('work' in terms of
#    the EU's Common Data Model) identified by the given CELEX id (for instance
#    02016R0679-20160504 for the consolidated GDPR Act, or an example that
#    is given on the EU website: 32018R1805) for a given language
#    (defaults to Dutch ("NLD")) and finds the manifestation items with
#    the given format (defaults to the EU's Formex 4 standard ("fmx4")).
#    This can give you multiple entries (URI's) to the specific parts of
#    the work. The result will show corresponding ruleset id's that can
#    be used with this api (work in progress) for the given URI's
#    (with which you can inspect the given documents).

#    Note that currently only CELLAR URL's will be shown.. the corresponding
#    ruleset id is the part after 'https://publications.europa.eu/resource/cellar/',
#    which needs to be converted to the ruleset id this api can work with
#    (for usage of it with the /rules endpoint) by prepending the prefix "CFMX4" and
#    changing the '/' into a '_'. For example: the publication (you can open this
#    in the browser)
#    'http://publications.europa.eu/resource/cellar/83e4752e-f2e5-11e8-9982-01aa75ed71a1.0017.02/DOC_2'
#    can be used to forge the rule set id:
#    'CFMX483e4752e-f2e5-11e8-9982-01aa75ed71a1.0017.02_DOC_2'
#    (Note this will be improved so you do not have to do this yourselves)

 #   Also note that currently due to a CORS issue in swagger the redirect causes a TypeError: Load failed to show up as response.
 #   Try opening the request url shown in swagger to see the actual response you get by using the CPRMV API directly.
 #   """
 #   cellarurl = f"https://publications.europa.eu/webapi/rdf/sparql?default-graph-uri=&query=prefix+cdm%3A+%3Chttp%3A%2F%2Fpublications.europa.eu%2Fontology%2Fcdm%23%3E+%0D%0Aprefix+purl%3A+%3Chttp%3A%2F%2Fpurl.org%2Fdc%2Felements%2F1.1%2F%3E+%0D%0Aselect+distinct+%3Fitem%0D%0Awhere+%7B%0D%0A%3Fwork+owl%3AsameAs+%3Chttp%3A%2F%2Fpublications.europa.eu%2Fresource%2Fcelex%2F{celexid}%3E+.%0D%0A%3Fexpr+cdm%3Aexpression_belongs_to_work+%3Fwork+%3B%0D%0Acdm%3Aexpression_uses_language+%3Flang+.%0D%0A%3Flang+purl%3Aidentifier+%3FlangCode+.%0D%0A%3Fmanif+cdm%3Amanifestation_manifests_expression+%3Fexpr%3B%0D%0Acdm%3Amanifestation_type+%3Fformat+.%0D%0A%3Fitem+cdm%3Aitem_belongs_to_manifestation+%3Fmanif.%0D%0AFILTER%28str%28%3FlangCode%29%3D%22{language}%22+%26%26+str%28%3Fformat%29%3D%22{format}%22%29%0D%0A%7D+LIMIT+100&format=application%2Fjson&timeout=0&debug=on&run=+Run+Query+"
 #   print(cellarurl)
 #   response = RedirectResponse(url=cellarurl)
 #   return response

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

# abstract base class for all methods
class RuleMethod:
    # the constructor is given the reference to the method definition node within the CPRMV standard
    # knowledge graph the API loads and self.config can be used in inherited methods as how it gets passed to child class instances
    def __init__(self, app, method_config):
        self.app = app
        self.config = method_config

app.acknowledged_methods = {}

def get_acknowledged_methods(category):
    cprmvMethods = app.cprmvsettings["CPRMVMETHODS_KG"]
    result = []
    if category in app.acknowledged_methods:
        return app.acknowledged_methods[category]
    methods = cprmvMethods.value(category, CPRMVMETHODS.acknowledged)
    while methods != RDF.nil:
        method = cprmvMethods.value(methods, RDF.first)
        result.append(method)
        methods = cprmvMethods.value(methods, RDF.rest)
    app.acknowledged_methods[category] = result
    return result

def get_method_config(methodid):
    cprmvMethods = app.cprmvsettings["CPRMVMETHODS_KG"]
    for method in get_acknowledged_methods(CPRMVMETHODS.rulemethods):
        # note that python class names can not contain the characters '.' and '-' for which the underscore must be used instead
        id = str(cprmvMethods.value(method, CPRMV.id)).replace('.','_').replace('-','_')
        # print(f"{id} == {methodid}?")
        if id == methodid:
            # copy config for easy access in base classes (which they rely on)
            stack = [method]
            while len(stack) > 0 and len(stack) < 10:
                for parent in cprmvMethods.objects(stack[0], RDF.type):
                    stack.append(parent)
                    for p, o in cprmvMethods.predicate_objects(parent):
                        if p != RDF.type and not p.startswith(CPRMV):
                            #print(f"adding {method} {p} {o}")
                            cprmvMethods.add((method, p, o))
                stack.pop(0)
            return method
    #print(f"Warning: no configuration found for method with id: {methodid}")
    return None

# scans the methods directory for method implementation modules related to ackknowledged cprmv:RuleMethod's
def load_methods():
    loaded_methods = {}
    current_dir = Path(__file__).resolve().parent
    parent_dir = current_dir.parent
    target_dir = parent_dir / "methods"
    if str(current_dir) not in sys.path:
        sys.path.append(str(current_dir))
    if str(target_dir) not in sys.path:
        sys.path.append(str(target_dir))
    for file_path in target_dir.glob("*.py"):
        if file_path.name == "__init__.py":
            continue
        module_name = file_path.stem
        # Dynamically import the module
        print(f"Loading method: {module_name}")
        module = importlib.import_module(module_name)
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # print(f"checking {name} member")
            # Check if the class inherits from the RuleMethod class
            if name.startswith(module_name) or name.endswith(module_name): # and issubclass(obj, RuleMethod) and obj is not RuleMethod:
                print(f"loading RDF config for {name}")
                config = get_method_config(name)
                if config is not None:
                    loaded_methods[name] = obj(app, config)
                    print(f"Loaded method: {module_name}.{name}")
                    #else:
                    #print(f"Could not load method: {module_name} as no configuration as an acknowledged rule method could be found.")
    return loaded_methods

# Load all methods that have specific python implementations for the functionality of the CPRMV API
# Note that other methods may have configuration within the knowledge graph loaded (app.cprmvsettings) but no
# python implementation and these will not be contained in app.cprmvmethods.
# app.cprmvmethods is a dictionary with method id's as key and instances of their python classes that
# have RuleMethod as base class (indirectly) as value
app.cprmvmethods = load_methods()

# NOTE this depends on supported reference methods which are modular so this python method needs to traverse those
def detect_cprmv_serve_reference_method_and_transform(reference):
    cprmvMethods = app.cprmvsettings["CPRMVMETHODS_KG"]
    result = None
    for method in get_acknowledged_methods(CPRMVMETHODS.referencemethods):
        reference_method_id = str(cprmvMethods.value(method , CPRMV["id"]))
        method_module = app.cprmvmethods[reference_method_id]
        result = method_module.transform_reference(reference)
        if result is not None:
            break
    if result is None:
        print('Could not detect reference: invalid, unknown or unsupported reference type')
    return result

# NOTE isn't this more related to all publication methods combined with analysis/formalisation (or serialisation)?
# finds the first acknowledged RuleMethod of given category (AnalysisMethod (default) / FormalisationMethod uri's) supported by CPRMV Serve
# for which the given cprmvid matches the id format defined in the cprmvmethods value lists
# returns all the information on the matching method as a Dictionary in which also the unformatted cprmvid (one or more key/values)
# is added under the CPRMV.id key
def detect_publication(cprmvid):
    cprmvMethods = app.cprmvsettings["CPRMVMETHODS_KG"]
    result = None
    for method in get_acknowledged_methods(CPRMVMETHODS.publicationmethods):

        publication_method_id = str(cprmvMethods.value(method , CPRMV["id"])).replace('-','_').replace('.','_')
        print(publication_method_id)
        if publication_method_id in app.cprmvmethods:
            method_module = app.cprmvmethods[publication_method_id]
        else:
            print(app.cprmvmethods.keys())
            continue

        print(method_module.interpret_publication_id)

        result = method_module.interpret_publication_id(cprmvid)

        print(f"RESULT: {result}")

        if result is not None:
            result['method_module'] = method_module
            break
    if result is None:
        print('Could not detect publication: invalid, unknown or unsupported publication method matching given publication id')
    return result


# only fetches the whole requested raw publication from the official repository
def fetch_rule_set(publication):
    pubfile = None
    cprmvMethods = app.cprmvsettings["CPRMVMETHODS_KG"]
    try:
        pubfile = publication['method_module'].get_raw_publication(publication)
    except Exception as e:
        raise e
    return pubfile

# load the requested publication from the official repository and transform it to CPRMV and load it
def load_rule_set(publication):
    cprmvMethods = app.cprmvsettings["CPRMVMETHODS_KG"]
    g = Graph()
    try:
        publication['method_module'].get_cprmv_rule_set_from_publication(g, publication)
    except Exception as e:
        if (
            "unbound prefix" in str(e).lower()
        ):  # TODO maybe this should not be ignonred always
            print(f"Warning: ignoring unbound prefix encountered: {e}")
        else:
            raise e
    return g


# defines function within a unformat setting which simply selects the substring matched with given regular expression
@with_pattern(r".+")
def param_value(pvalue):
    return pvalue

def get_raw_publication(
    rule_id_path="",
    path_delimiter: str = ","
):
    delimindex = rule_id_path.find(path_delimiter)
    if delimindex > 0:
        rulesetid = rule_id_path[:delimindex].strip()
    else:
        rulesetid = rule_id_path.strip()
    print(f"Info: retrieving info for cprmv:RuleSet : {rulesetid}")
    try:
        publication = detect_publication(rulesetid)
        if publication is not None:
            pubfile = fetch_rule_set(publication)
            if pubfile is not None:
                return pubfile, rulesetid
            raise Exception("An error occurred, either the publication does not exist or could not be retrieved...")
        raise Exception("The reference to the Rule Set publication is not a valid reference...")
    except Exception as e:
        return json.dumps({"error retrieving raw Rule Set publication": str(e)}), ""

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
        if delimindex > 0:
            rulesetid = rule_id_path[:delimindex].strip()
        else:
            rulesetid = rule_id_path.strip()
        print(f"Info: retrieving info for cprmv:RuleSet : {rulesetid}")
        publication = detect_publication(rulesetid)
        if publication is not None:
            g = load_rule_set(publication)
            print(f"replacing {rulesetid} with {publication[CPRMVSERVE['id_parts']]['cprmvid']} in {rule_id_path}")
            rule_id_path = rule_id_path.replace(rulesetid, publication[CPRMVSERVE["id_parts"]]['cprmvid']) # the actual latest rulesetid might have been searched and found
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
        out = iterative_cbd(g,r) #g.cbd(r)
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

def iterative_cbd(graph, target_node):
    cbd_graph = Graph()
    to_visit = {target_node}
    visited = set()

    while to_visit:
        node = to_visit.pop()
        if node in visited:
            continue
        visited.add(node)

        # Retrieve all direct properties
        for s, p, o in graph.triples((node, None, None)):
            cbd_graph.add((s, p, o))
            # Only recursively explore if the object is a blank node
            if isinstance(o, BNode):
                to_visit.add(o)

    return cbd_graph

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
            r[p] = cbd_cprmv_json(g, o)
    return r


def cbd_cprmv_json(graph, node, visited=set()):
    r = {}
    for s, p, o in graph.triples((node, None, None)):
        if o not in visited:
            visited.add(o)
            r[p] = cbd_cprmv_json(graph, o, visited)
        else:
            r[p] = o
    if not r:
        return node
    return r

# This block must stay at the end of the module
mcp = FastMCP.from_fastapi(app=app, name="CPRMV")
mcp_app = mcp.http_app(path="/")
app.mount("/mcp", mcp_app)
