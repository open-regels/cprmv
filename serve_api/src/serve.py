from rdflib import Graph
from rdflib.term import Literal
from rdflib.namespace import RDF
from typing import Union
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from parse import parse, search, with_pattern, Result, Match
from urllib.request import Request, urlopen
from urllib.error import URLError
from lxml import etree
import shutil
import tempfile
import os
import ciso8601

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
    description="This experimental API allows fetching single CPRMV Rules from locally provided CPRMV RuleSets in a desired RDF format",
    version="0.3.1",
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


def set_CPRMVMETHODSKG(path):
    _cprmvMethods = Graph()
    _cprmvMethods.parse(path, format="turtle")
    app.cprmvsettings = {"CPRMVMETHODS_KG": _cprmvMethods}
    return app.cprmvsettings["CPRMVMETHODS_KG"]


set_CPRMVMETHODSKG("./data/cprmvmethods.ttl")


@app.get("/")
def cprmv_info():
    """
    returns basic app information (title and version)
    """
    return {app.title: app.version}


@app.get("/methods")
def methods(format: str = "json-ld"):
    if format in ["json-ld", "xml", "turtle", "ttl", "n3", "turtle2"]:
        return app.cprmvsettings["CPRMVMETHODS_KG"].serialize(format=format)


@app.get("/rules/{rule_id_path}")
def rules(
    rule_id_path: str = RULE_ID_PATH,
    path_delimiter: str = PATH_DELIMITER,
    format: str = FORMAT,
    _language: Union[str, None] = LANGUAGE,
    unformat: str = UNFORMAT,
):
    """
    Returns the Rule(Set) including all Rules it contains and that can be found as indicated in the given Rule Id Path.

    This endpoint retrieves a specific rule or rule set from various official publication repositories
    and transforms it into CPRMV format. It supports BWB, CVDR, and EU CELLAR repositories.

    The API downloads the source publication on-the-fly, transforms it using XSLT, and serves the resulting
    CPRMV-formatted rules. You can request individual rules within a rule set by specifying their path.
    """
    return get_rules(rule_id_path, path_delimiter, format, unformat)


@app.get("/jci13/{jciuri}")
def jci13(
    jciuri: str = "jci1.3:c:BWBR0015703&hoofdstuk=3&paragraaf=3.2&artikel=20&z=2025-07-01&g=2025-07-01",
):
    """
    Not yet implemented in full. Returns a fixed example URL given a corresponding fixed example Juriconnect URI: "jci1.3:c:BWBR0015703&hoofdstuk=3&paragraaf=3.2&artikel=20&z=2025-07-01&g=2025-07-01"
    """
    # todo : actually implement this properly
    if (
        jciuri
        == "jci1.3:c:BWBR0015703&hoofdstuk=3&paragraaf=3.2&artikel=20&z=2025-07-01&g=2025-07-01"
    ):
        response = RedirectResponse(
            url="/rules/BWBR0015703_2025-07-01_0%2C%20Artikel%2020"
        )
        return response
    return {"error": "not implemented"}


@app.get("/cellar-by-celex/{celexid}/{language}/{format}")
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
    """
    url = f"https://publications.europa.eu/webapi/rdf/sparql?default-graph-uri=&query=prefix+cdm%3A+%3Chttp%3A%2F%2Fpublications.europa.eu%2Fontology%2Fcdm%23%3E+%0D%0Aprefix+purl%3A+%3Chttp%3A%2F%2Fpurl.org%2Fdc%2Felements%2F1.1%2F%3E+%0D%0Aselect+distinct+%3Fitem%0D%0Awhere+%7B%0D%0A%3Fwork+owl%3AsameAs+%3Chttp%3A%2F%2Fpublications.europa.eu%2Fresource%2Fcelex%2F{celexid}%3E+.%0D%0A%3Fexpr+cdm%3Aexpression_belongs_to_work+%3Fwork+%3B%0D%0Acdm%3Aexpression_uses_language+%3Flang+.%0D%0A%3Flang+purl%3Aidentifier+%3FlangCode+.%0D%0A%3Fmanif+cdm%3Amanifestation_manifests_expression+%3Fexpr%3B%0D%0Acdm%3Amanifestation_type+%3Fformat+.%0D%0A%3Fitem+cdm%3Aitem_belongs_to_manifestation+%3Fmanif.%0D%0AFILTER%28str%28%3FlangCode%29%3D%22NLD%22+%26%26+str%28%3Fformat%29%3D%22fmx4%22%29%0D%0A%7D+LIMIT+1000&format=application%2Fjson&timeout=0&debug=on&run=+Run+Query+"
    return {"url": url}


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
"""

def find_publication_version_valid_on_date(date, method):
    date_ts = ciso8601.parse_datetime(date)
    frbr = str(method[CPRMVSERVE["frbr-repository-versioning-information-url"]])
    puburl = frbr.format_map(method[CPRMVSERVE["id_parts"]])
    methodLabel = method[CPRMV.label]
    try:
        print(f"retrieving versioning information on publication: {puburl}")
        req = Request(puburl)
        response = urlopen(req)
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            shutil.copyfileobj(response, tmp_file)
            print(f"opening publication versioning information from temp file {tmp_file.name}")
            xml = etree.parse(open(tmp_file.name))
            last_date = None
            last_date_ts = None
            last_index = None
            for expr in xml.xpath('/work/expression'):
                found_date, found_index = expr.get('label').split('_')
                found_date_ts = ciso8601.parse_datetime(found_date)
                if(last_date_ts is None or (found_date_ts <= date_ts and found_date_ts > last_date_ts)):
                    last_date = found_date
                    last_date_ts = found_date_ts
                    last_index = found_index
            print(f"latest version found: {last_date}_{last_index}")
            os.remove(tmp_file.name)
            return {"date" : last_date, "index" : last_index}
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
        raise Exception(f"unknown error loading {methodLabel} publication versioning information...")


# finds the first acknowledged AnalysisMethod supported by CPRMV Serve for which the given cprmvid matches the id format defined in the cprmvmethods value lists
# returns all the information on the matching method as a Dictionary in which also the unformatted cprmvid (one or more key/values) is added under the CPRMV.id key
def detect_cprmv_serve_analysis_method(cprmvid):
    cprmvMethods = app.cprmvsettings["CPRMVMETHODS_KG"]
    result = None
    methods = cprmvMethods.value(CPRMVMETHODS.analysismethods, CPRMV.acknowledged)
    while methods != RDF.nil:
        method = cprmvMethods.value(methods, RDF.first)
        idformat = cprmvMethods.value(method, CPRMVSERVE["publication-id-format"])
        if idformat is not None:
            print(f"Parsing {idformat} on value {cprmvid}")
            result = parse(idformat, cprmvid)
            if result is not None:
                methodTriples = {}
                for p, o in cprmvMethods.predicate_objects(method):
                    methodTriples[p] = o
                methodTriples[CPRMVSERVE["id_parts"]] = result.named
                if 'index' in methodTriples[CPRMVSERVE["id_parts"]] and methodTriples[CPRMVSERVE["id_parts"]]['index'] == 'latest':
                    methodTriples[CPRMVSERVE["id_parts"]]['valid-on'] = methodTriples[CPRMVSERVE['id_parts']]['date']
                    print(f"searching latest version valid on date: {methodTriples[CPRMVSERVE['id_parts']]['date']}")
                    version = find_publication_version_valid_on_date(methodTriples[CPRMVSERVE["id_parts"]]['date'], methodTriples)
                    methodTriples[CPRMVSERVE["id_parts"]]['date'] = version['date']
                    cprmvid = cprmvid.replace(methodTriples[CPRMVSERVE["id_parts"]]['valid-on'], version['date'])
                    methodTriples[CPRMVSERVE["id_parts"]]['index'] = version['index']
                    cprmvid = cprmvid.replace('latest', version['index'])
                methodTriples[CPRMVSERVE["id_parts"]]['cprmvid'] = cprmvid
                result = methodTriples
                break
        methods = cprmvMethods.value(methods, RDF.rest)
    return result


def get_cprmv_rule_set_from_publication(g, method):
    cprmvid = method[CPRMVSERVE["id_parts"]]['cprmvid']
    frbr = str(method[CPRMVSERVE["frbr-repository"]])
    puburl = frbr.format_map(method[CPRMVSERVE["id_parts"]])
    methodLabel = method[CPRMV.label]
    try:
        print(f"downloading publication: {puburl}")
        req = Request(puburl)
        response = urlopen(req)
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            shutil.copyfileobj(response, tmp_file)
            print(f"opening publication from temp file {tmp_file.name}")
            xml = etree.parse(open(tmp_file.name))
            print(f"transforming {methodLabel} resource into CPRMV RuleSet ...")
            ac = etree.XSLTAccessControl(read_network=False, read_file=False)
            transform = etree.XSLT(
                etree.parse(method[CPRMVSERVE.xslt]), access_control=ac
            )
            result = str(transform(xml, cprmvid=etree.XSLT.strparam(cprmvid)))
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


def get_rules(
    rule_id_path="",
    path_delimiter: str = ",",
    formatarg: str = "cprmv-json",
    unformat: str = "",
):
    try:
        delimindex = rule_id_path.find(path_delimiter)
        print(delimindex)
        if delimindex > 0:
            rulesetid = rule_id_path[:delimindex].strip()
        else:
            rulesetid = rule_id_path.strip()
        print(f"Info: retrieving info for cprmv:RuleSet : {rulesetid}")
        method = detect_cprmv_serve_analysis_method(rulesetid)
        if method is not None:
            g = load_rule_set(method)
            rule_id_path = rule_id_path.replace(rulesetid, method[CPRMVSERVE["id_parts"]]['cprmvid']) # the actual latest rulesetid might have been searched and found
        else:
            raise Exception(
                "No supported publication repository use identifiers with the format of the given Ruleset Id."
            )
    except Exception as e:
        return {"error": str(e)}
    print(f"processing starts at first rule in path {rule_id_path}")
    r = get_first_rule_by_id_path(g, rule_id_path, path_delimiter)
    if r is None:
        return "No rules found for given path..."
    print(f"rule found {r}")
    if formatarg == "cprmv-json":
        result = get_rule(
            g, r
        )  # this custom format has a more human readable pretty print layout
    else:
        result = g.cbd(r).serialize(format=formatarg)
    if unformat != "" and CPRMV.definition in result:
        string_definition = str(
            " ".join(result[CPRMV.definition].split())
        )  # transform no break spaces in regular ones
        definition: Result | Match | None = search(
            unformat, string_definition, extra_types={"param_value": param_value}
        )
        if definition is not None:
            named_definition: Definition = definition.named
            named_definition["rulesetid"] = rulesetid
            named_definition["rule_id_path"] = rule_id_path
            result.update(named_definition)
    return result


# depth first search in the given graph g for the first rule matching the given path (the path splitted as a list) from the given rootrule
def get_first_rule_by_id_path(g, path, path_delimiter: str = ","):
    pathsplit = path.split(path_delimiter)
    firstid = pathsplit.pop(0).strip()
    for rootrule in g.subjects(CPRMV.id, Literal(firstid, lang="nl")):
        rule = get_first_rule_by_Id_path_split_from_rule_as_root(g, rootrule, pathsplit)
        if rule is not None:
            return rule
    return None


# recursive depth first search in the given graph g for the first rule matching the path (the path splitted as a list) from the given rootrule
def get_first_rule_by_Id_path_split_from_rule_as_root(g, rootrule, pathsplit):
    if len(pathsplit) == 0:
        return rootrule
    rulelist = g.value(rootrule, CPRMV.contains)
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


# retrieves all info of the given rule (and all its subrules from the given graph).
# Note that rule structures over CPRMV.contains relations should be trees, so no cyclic graphs, otherwise this method will not stop.
def get_rule(g, rule):
    r = {}
    for p, o in g.predicate_objects(rule):
        if p == CPRMV.contains:
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
