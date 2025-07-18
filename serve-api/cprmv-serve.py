from rdflib import Graph, Namespace
from rdflib.term import Literal
from rdflib.plugins.sparql import prepareQuery
from rdflib.namespace import RDF
from typing import Union
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from parse import search
from parse import with_pattern
from urllib.request import Request, urlopen
from urllib.error import URLError
from lxml import etree
import shutil
import tempfile
import os

import locale

try:
    locale.setlocale(locale.LC_ALL, 'nl_NL.UTF-8') # todo, find out whether locale has effect on the parse module at all, and if so, make NL not the hard coded locale but dependent on language arguments
    print("Dutch locale (nl_NL.UTF-8) set successfully")
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'nl_NL')
        print("Dutch locale (nl_NL) set successfully")
    except locale.Error:
        print("Warning: Dutch locale not available, using system default")

app = FastAPI(
    title="CPRMV Rules Serve API",
    description="This experimental API allows fetching single CPRMV Rules from locally provided CPRMV RuleSets in a desired RDF format",
    version="0.1.0",
    contact={
        "name": "Bas Kaptijn",
        "url": "http://git.open-regels.nl/standards/cprmv",
        "email": "Bas.Kaptijn@ictu.nl",
    },
    license_info={
        "name": "EUPL",
        "url": "https://git.open-regels.nl/standards/cprmv/-/blob/main/LICENSE?ref_type=heads",
    }
)

CPRMV = Namespace("https://cprmv.open-regels.nl/0.3.0/")

@app.get("/")
def cprmvinfo():
    """
    returns basic app information (title and version)
    """
    return {app.title : app.version}

@app.get("/ruleset/{rulesetid}")
def ruleset(rulesetid: str, format: str = 'cprmv-json', language: Union[str, None] = None):
    """
    returns all rules of a ruleset with the given cprmv:id value (rulesetid) if it can be found as a cprmv resource.

    Note that the Rule Set cprmv resource has to have been installed with this API as a turtle file with the rulsetid name in order for it to be found (for instance "BWBR0015703_2025-07-01_0", being the concatenation of the BWB id, valid from date and index number on this date and which is provided as example with this API).
    
    The format argument allows all built in rdflib formats (see https://rdflib.readthedocs.io/en/stable/apidocs/rdflib.html#rdflib.graph.Graph.serialize)  and implies returning the Concise Bounded Description (CBD) of the indicated Rule (see https://rdflib.readthedocs.io/en/stable/apidocs/rdflib.html#rdflib.graph.Graph.cbd) as well as a default custom cprmv jsonld format which is more easy to use / anderstand and read (but leaves out extra metadata information however in this initial version as it does not use the CBD definition at the moment as it is not a custom rdflib seriallizer yet).
    
    The language parameter for now should always be "nl" (default). Multilingual support will be added in a later version.
    """
    return getRules(rulesetid, rulesetid, format)
    
@app.get("/rules/{rulesetid}/{ruleidpath}")
def rules(rulesetid: str, ruleidpath: str, path_delimiter: str = ',', format: str = 'cprmv-json', language: Union[str, None] = None, unformat: str='{situatie:paramvalue}: € {norm:paramvalue};'):
    """
    Returns the Rule including all Rules it contains and that can be found as indicated in the given Rule Id Path (ruleidpath) within the Rule Set that has the given Rule Set Id (rulesetid)
    
    Note that the path consists out of the values of the cprmv:id of the rules in the given ruleset delimited by a delimiter (default delimiter is ',') and for convenience the path may also leave out id's of rules in the path. The first matching rule (depth first) is the one returned.
    
    Note that the id's in the path are matched case sensitive (!) but surrounding whitespace will be ignored. Case sensitivity might get removed lateron.
    
    Note that the Rule Set cprmv resource has to have been installed with this API as a turtle file with the rulsetid name in order for it to be found (for instance "BWBR0015703_2025-07-01_0", being the concatenation of the BWB id, valid from date and index number on this date and which is provided as example with this API).
    
    So the path "Artikel 20,    onderdeel a. " leads to the same result as "Artikel 20   ,lid 1,onderdeel a.". To fetch only the "onderdeel a." contained in "Artikel 20, lid 2" you need to include the id of "lid 2" in the path, otherwise the one contained in "lid 1" will be retrieved (depth first). This does depend on the order in which the triples are loaded from the cprmv source however, so it is better to provide a path that is not ambigeous.
    
    The format argument allows all built in rdflib formats (see https://rdflib.readthedocs.io/en/stable/apidocs/rdflib.html#rdflib.graph.Graph.serialize)  and implies returning the Concise Bounded Description (CBD) of the indicated Rule (see https://rdflib.readthedocs.io/en/stable/apidocs/rdflib.html#rdflib.graph.Graph.cbd) as well as a default custom cprmv jsonld format which is more easy to use / anderstand and read (but leaves out extra metadata information however in this initial version as it does not use the CBD definition at the moment as it is not a custom rdflib seriallizer yet).
    
    The language parameter for now should always be "nl" (default). Multilingual support will be added in a later version.
    
    The unformat argument allows for simple string parsing for instance extracting the amount in the sentence of Artikel 20, lid 1, onderdeel a. of the ruleset BWBR0015703_2025-07-01_0 which can also assert parts of the sentence to be expected.
    It is not neccesary to specify the whole expected content and it works as a search string (using parse.search()) on the formatted output depending on the format argument. For more information on how to use this see https://pypi.org/project/parse/
    """
    return getRules(rulesetid, ruleidpath, path_delimiter, format, unformat)

@app.get("/jci13/{jciuri}")
def jci13(jciuri: str = 'jci1.3:c:BWBR0015703&hoofdstuk=3&paragraaf=3.2&artikel=20&z=2025-07-01&g=2025-07-01'):
    """
    Not yet implemented in full. Returns a fixed example URL given a corresponding fixed example Juriconnect URI: "jci1.3:c:BWBR0015703&hoofdstuk=3&paragraaf=3.2&artikel=20&z=2025-07-01&g=2025-07-01"
    """
    # todo : actually implement this properly
    if(jciuri == "jci1.3:c:BWBR0015703&hoofdstuk=3&paragraaf=3.2&artikel=20&z=2025-07-01&g=2025-07-01"):
        response = RedirectResponse(url='/rules/BWBR0015703_2025-07-01_0/Artikel%2020')
        return response
    return { "error" : "not implemented"}

def getBWBPublicationAsCPRMVRuleSet(cprmvid):
    bwbid, pubdate, index = cprmvid.split('_')
    req = Request(f"https://repository.officiele-overheidspublicaties.nl/bwb/{bwbid}/{pubdate}_{index}/xml/{cprmvid}.xml")
    try:
        print("downloading publication...")
        response = urlopen(req)
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            shutil.copyfileobj(response, tmp_file)
            print(f"opening publication from temp file {tmp_file.name}")
            xml = etree.parse(open(tmp_file.name))
            print("transforming BWB resource into CPRMV RuleSet ...")
            ac = etree.XSLTAccessControl(read_network=False, read_file=False)
            transform = etree.XSLT(etree.parse('data/bwb2cprmv.xsl'), access_control=ac)
            result = str(transform(xml))
            os.remove(tmp_file.name)
            return result
    except URLError as e:
        if hasattr(e, 'reason'):
            print('We failed to reach a server.')
            print('Reason: ', e.reason)
            raise e
        elif hasattr(e, 'code'):
            print('The server couldn\'t fulfill the request.')
            print('Error code: ', e.code)
            raise e
    else:
        raise Exception('unknown error loading BWB publication ...')

# load the requested publication from the official repository and transform it to CPRMV and load it
def loadRuleSet(cprmvid):
    g = Graph()
    try:
        if not (None, CPRMV.id, Literal(cprmvid)) in g:
            ttl = getBWBPublicationAsCPRMVRuleSet(cprmvid)
            g.parse(data=ttl, format="turtle")
    except Exception as e:
        if "unbound prefix" in str(e).lower(): #TODO maybe this should not be ignonred always
            print(f"Warning: ignoring unbound prefix encountered: {e}")
        else:
            print(f"Warning: Exception raised: {e}")
            raise e
    return g
    
@with_pattern(r'.+')
def paramvalue(pvalue):
    return pvalue

def getRules(rulesetid, ruleidpath='', path_delimiter: str = ',', formatarg: str = 'cprmv-json', unformat: str=''):
    print(f"Info: retrieving info for cprmv:RuleSet : {rulesetid}")
    try:
        g = loadRuleSet(rulesetid)
    except Exception as e:
        return { "error" : str(e) }
    r = getFirstRuleByIdPath(g, ruleidpath, path_delimiter)
    if(r == None):
        return "None"
    if(formatarg == 'cprmv-json'):
        result = getRule(g, r)
    else:
        result = g.cbd(r).serialize(format=formatarg)
    if(unformat != ''):
        definition = str(' '.join(result[CPRMV.definition].split()))
        definition = search(unformat, definition, extra_types={'paramvalue':paramvalue})
        if(definition != None):
            definition = definition.named
            definition['rulesetid'] = rulesetid
            definition['ruleidpath'] = ruleidpath
            result.update(definition)
    return result

def getFirstRuleByIdPath(g, path, path_delimiter: str = ','):
    reversed_pathsplit = path.split(path_delimiter)
    reversed_pathsplit.reverse()
    firstid = reversed_pathsplit.pop().strip();
    for rootrule in g.subjects(CPRMV.id, Literal(firstid, lang="nl")):
        rule = getFirstRuleByReversedIdPathSplitFromRuleAsRoot(g, rootrule, reversed_pathsplit)
        if(rule != None):
            return rule
    return None

def getFirstRuleByReversedIdPathSplitFromRuleAsRoot(g, rootrule, reversed_pathsplit):
    if(len(reversed_pathsplit) == 0):
        return rootrule
    rulelist = g.value(rootrule, CPRMV.contains)
    if(rulelist == None):
        return None
    while(rulelist != RDF.nil):
        rule = g.value(rulelist, RDF.first)
        ruleid = g.value(rule, CPRMV.id)
        id = reversed_pathsplit.pop().strip()
        subrule = None
        if(Literal(id, lang="nl") == ruleid):
            subrule = getFirstRuleByReversedIdPathSplitFromRuleAsRoot(g, rule, reversed_pathsplit)
            reversed_pathsplit.append(id)
        else:
            reversed_pathsplit.append(id)
            subrule = getFirstRuleByReversedIdPathSplitFromRuleAsRoot(g, rule, reversed_pathsplit)
        if(subrule != None):
            return subrule
        rulelist = g.value(rulelist, RDF.rest)
    return None
            
def getRule(g, rule):
    r = {}
    for p, o in g.predicate_objects(rule):
        if(p == CPRMV.contains):
            r[p] = {}
            item = o
            while (item != RDF.nil):
                firstitem = g.value(item, RDF.first)
                subid = g.value(firstitem, CPRMV.id)
                r[p][subid] = getRule(g, firstitem)
                item = g.value(item, RDF.rest)
        else:
            r[p] = o
    return r
