from rdflib import Graph, Namespace
from rdflib.term import Literal
from rdflib.plugins.sparql import prepareQuery
from rdflib.namespace import RDF
from typing import Union
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from parse import parse, search
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
    version="0.3.0",
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
CPRMVSERVE = Namespace("https://cprmv.open-regels.nl/0.3.0/serve-api/")
CPRMVMETHODS = Namespace("https://cprmv.open-regels.nl/0.3.0/methods/")

def setCPRMVMETHODSKG(path):
    _cprmvMethods = Graph()
    _cprmvMethods.parse(path, format="turtle")
    app.cprmvsettings = { 'CPRMVMETHODS_KG' : _cprmvMethods }
    return app.cprmvsettings['CPRMVMETHODS_KG']
setCPRMVMETHODSKG('./data/cprmvmethods.ttl')

@app.get("/")
def cprmvinfo():
    """
    returns basic app information (title and version)
    """
    return {app.title : app.version}
    
@app.get("/methods")
def methods(format: str='json-ld'):
    if format in ['json-ld','xml','turtle','ttl','n3','turtle2']:
        return app.cprmvsettings['CPRMVMETHODS_KG'].serialize(format=format)
    
@app.get("/rules/{ruleidpath}")
def rules(ruleidpath: str='BWBR0015703_2025-07-01_0, Artikel 20, onderdeel a.', path_delimiter: str=',', format: str='cprmv-json', language: Union[str, None] = None, unformat: str=''):
    """
    Returns the Rule(Set) including all Rules it contains and that can be found as indicated in the given Rule Id Path (ruleidpath) within the Rule Set that has been published and is identifiable through the given Rule Set Id that should come as first element in the path.
    
    Note that this version of the API only supports the Dutch BWB directory (https://repository.officiele-overheidspublicaties.nl/bwb/...) the Dutch CVDR directory (https://repository.officiele-overheidspublicaties.nl/cvdr/...) and Formex 4 publications in the EU's CELLAR directory and no other sources. Given a valid cprmvid, it will fetch a source publication and transform it into a RuleSet on the fly and with a result as intended using the CPRMV. A valid cprmvid for the BWB directory is the concatenation of a BWB id, valid from date (yyyy-mm-dd) and an index number (starting at 0), concatenated with an underscore ('_'). The index number is to support the case when there are multiple versions published on the same date whih is rare. For instance the cprmvid "BWBR0015703_2025-07-01_0" will simply fetch and process https://repository.officiele-overheidspublicaties.nl/bwb/BWBR0015703/2025-07-01_0/xml/BWBR0015703_2025-07-01_0.xml.
    
    A publication in the CVDR directory is just identified with a concatenation of a CVDR id and an index number concatenated with an underscore ('_'). For instance the cprmvid "CVDR712517_1" will simply fetch and process https://repository.officiele-overheidspublicaties.nl/cvdr/CVDR712517/1/xml/CVDR712517_1.xml
    
    A Formex 4 publication in the CELLAR directory is just identified with a concatenation of a prefix ("CFMX4") and the CELLAR id and an item id concatenated with an underscore ('_'). For instance the cprmvid "CFMX483e4752e-f2e5-11e8-9982-01aa75ed71a1.0017.02_DOC_2" will simply fetch and process http://publications.europa.eu/resource/cellar/83e4752e-f2e5-11e8-9982-01aa75ed71a1.0017.02/DOC_2. See the helper endpoint /cellar-by-celex for how to find these identifiers when only having a CELEX identifier (and only having a ELI identifier is similar)
    
    All BWB/CVDR structure elements will become nested cprmv Rules. For the transformation the API uses a XSL transformation defined in 'data/bwb2cprmv.xsl' or 'data/cvdr2cprmv.xsl' or 'data/fmc4cellar2crprmv.xsl' which transforms the XML source fetched from the aforementioned directory, which is exepcted to follow the bwb-toestand scheme (https://repository.officiele-overheidspublicaties.nl/Schema/BWB-toestand/2016-1/xsd/toestand_2016-1.xsd) or cvdr scheme (http://standaarden.overheid.nl/cvdr/terms/ http://decentrale.regelgeving.overheid.nl/cvdr/xsd/cvdr.xsd) or Formex 4 scheme (see: https://op.europa.eu/en/web/eu-vocabularies/formex) , to the CPRMV RuleSet as a Turtle file. This content is what this API can serve, either by returning the whole RuleSet in the format requested or single Rules (with all the Rules that are nested in them if applicable). 
    
    This API also allows for simple string interpretation of the definition of a single rule (see /rules/...) or as in this method: single Rules (with all the Rules that are nested in them if applicable)
    
    Note that the path consists out of the values of the cprmv:id of the rules in the given ruleset delimited by a delimiter (default delimiter is ',') and for convenience the path may also leave out id's of rules in the path. The first matching rule (depth first) is the one returned.
    
    Note that the id's in the path are matched case sensitive (!) but surrounding whitespace will be ignored.
    
    So the path "Artikel 20,    onderdeel a. " leads to the same result as "Artikel 20   ,lid 1,Onderdeel a.". To fetch only the "onderdeel a." contained in "Artikel 20, lid 2" you need to include the id of "lid 2" in the path, otherwise the one contained in "lid 1" will be retrieved (depth first). This does depend on the order in which the triples are loaded from the cprmv source however, so it is better to provide a path that is not ambigeous.
    
    The format argument allows all built in rdflib formats (see https://rdflib.readthedocs.io/en/stable/apidocs/rdflib.html#rdflib.graph.Graph.serialize)  and implies returning the Concise Bounded Description (CBD) of the indicated Rule (see https://rdflib.readthedocs.io/en/stable/apidocs/rdflib.html#rdflib.graph.Graph.cbd) as well as a default custom cprmv jsonld format which is more easy to use / anderstand and read (but leaves out extra metadata information however in this initial version as it does not use the CBD definition at the moment as it is not a custom rdflib seriallizer yet).
    
    The language parameter for now will always be "nl" (implicit default regardless what is passed as argument). Multilingual support will be added in a later version.
    
    The unformat argument allows for simple string parsing for instance extracting the amount in the sentence of Artikel 20, lid 1, onderdeel a. of the ruleset BWBR0015703_2025-07-01_0 which can also assert parts of the sentence to be expected.
    
    It is not neccesary to specify the whole expected content and it works as a search string (using parse.search()) on the formatted output depending on the format argument. For more information on how to use this see https://pypi.org/project/parse/ ..
    
    An example would be using the unformat value : "{situatie:paramvalue}: € {norm:paramvalue}" when requesting with the ruleid path: "BWBR0015703_2025-07-01_0, Artikel 20, onderdeel a.". It also works for Artikel 21 and other Rules in this particular case.
    """
    return getRules(ruleidpath, path_delimiter, format, unformat)

@app.get("/jci13/{jciuri}")
def jci13(jciuri: str = 'jci1.3:c:BWBR0015703&hoofdstuk=3&paragraaf=3.2&artikel=20&z=2025-07-01&g=2025-07-01'):
    """
    Not yet implemented in full. Returns a fixed example URL given a corresponding fixed example Juriconnect URI: "jci1.3:c:BWBR0015703&hoofdstuk=3&paragraaf=3.2&artikel=20&z=2025-07-01&g=2025-07-01"
    """
    # todo : actually implement this properly
    if(jciuri == "jci1.3:c:BWBR0015703&hoofdstuk=3&paragraaf=3.2&artikel=20&z=2025-07-01&g=2025-07-01"):
        response = RedirectResponse(url='/rules/BWBR0015703_2025-07-01_0%2C%20Artikel%2020')
        return response
    return { "error" : "not implemented"}

@app.get("/cellar-by-celex/{celexid}/{language}/{format}")
def celex(celexid: str = '32018R1805', language: str = 'NLD', format:str = 'fmx4'):
    """
    Gives a URL to the SPARQL endpoint of the European CELLAR repository running a specific query that finds publications ('work' in terms of the EU's Common Data Model) identified by the given CELEX id (for instance 02016R0679-20160504 for the consolidated GDPR Act, or an example that is given on the EU website: 32018R1805) for a given language (defaults to Dutch ("NLD")) and finds the manifestation items with the given format (defaults to the EU's Formex 4 standard ("fmx4")). This can give you multiple entries (URI's) to the specific parts of the work. The result will show corresponding ruleset id's that can be used with this api (work in progress) for the given URI's (with which you can inspect the given documents). Note that currently only CELLAR URL's will be shown.. the corresponding ruleset id is the part afer 'https://publications.europa.eu/resource/cellar/', which needs to be converted to the ruleset id this api can work with (for usage of it with the /rules endpoint) by prepending the prefix "CFMX4" and changing the '/' into a '_'. For example: the publication (you can open this in the browser) 'http://publications.europa.eu/resource/cellar/83e4752e-f2e5-11e8-9982-01aa75ed71a1.0017.02/DOC_2' can be used to forge the rule set id: 'CFMX483e4752e-f2e5-11e8-9982-01aa75ed71a1.0017.02_DOC_2' (Note this will be improved so you do not have to do this yourselves)
    """
    url = f"https://publications.europa.eu/webapi/rdf/sparql?default-graph-uri=&query=prefix+cdm%3A+%3Chttp%3A%2F%2Fpublications.europa.eu%2Fontology%2Fcdm%23%3E+%0D%0Aprefix+purl%3A+%3Chttp%3A%2F%2Fpurl.org%2Fdc%2Felements%2F1.1%2F%3E+%0D%0Aselect+distinct+%3Fitem%0D%0Awhere+%7B%0D%0A%3Fwork+owl%3AsameAs+%3Chttp%3A%2F%2Fpublications.europa.eu%2Fresource%2Fcelex%2F{celexid}%3E+.%0D%0A%3Fexpr+cdm%3Aexpression_belongs_to_work+%3Fwork+%3B%0D%0Acdm%3Aexpression_uses_language+%3Flang+.%0D%0A%3Flang+purl%3Aidentifier+%3FlangCode+.%0D%0A%3Fmanif+cdm%3Amanifestation_manifests_expression+%3Fexpr%3B%0D%0Acdm%3Amanifestation_type+%3Fformat+.%0D%0A%3Fitem+cdm%3Aitem_belongs_to_manifestation+%3Fmanif.%0D%0AFILTER%28str%28%3FlangCode%29%3D%22NLD%22+%26%26+str%28%3Fformat%29%3D%22fmx4%22%29%0D%0A%7D+LIMIT+1000&format=application%2Fjson&timeout=0&debug=on&run=+Run+Query+"
    return {"url" : url}

# Tip: use https://publications.europa.eu/webapi/rdf/sparql to edit the SPARQL query in the URL above (you get the URI in a new browser window by executing the query):
'''
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
'''

# finds the first acknowledges AnalysisMethod supported by CPRMV Serve for which the given cprmvid matches the id format defined in the cprmvmethods value lists
# returns all the information on the matching method as a Dictionary in which also the unformatted cprmvid (one or more key/values) is added under the CPRMV.id key
def detectCPRMVServeAnalysisMethod(cprmvid):
    cprmvMethods = app.cprmvsettings['CPRMVMETHODS_KG']
    result = None
    methods = cprmvMethods.value(CPRMVMETHODS.analysismethods, CPRMV.acknowledged)
    while (methods != RDF.nil):
        method = cprmvMethods.value(methods, RDF.first)
        idformat = cprmvMethods.value(method, CPRMVSERVE['publication-id-format'])
        if idformat != None:
            print(f"Parsing {idformat} on value {cprmvid}")
            result = parse(idformat, cprmvid)
            if result != None:
                methodTriples = {}
                for p, o in cprmvMethods.predicate_objects(method):
                    methodTriples[p] = o
                methodTriples[CPRMVSERVE['id_parts']] = result.named
                result = methodTriples
                break
        methods = cprmvMethods.value(methods, RDF.rest)
    return result
    
def getCprmvRuleSetFromPublication(g, cprmvid, method):
    frbr = str(method[CPRMVSERVE['frbr-repository']])
    puburl = frbr.format_map(method[CPRMVSERVE['id_parts']])
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
            transform = etree.XSLT(etree.parse(method[CPRMVSERVE.xslt]), access_control=ac)
            result = str(transform(xml, cprmvid = etree.XSLT.strparam(cprmvid)))
            #os.remove(tmp_file.name)
            print(result)
            g.parse(data=result, format="turtle")
            return
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
        raise Exception(f"unknown error loading {methodLabel} publication ...")
    
# load the requested publication from the official repository and transform it to CPRMV and load it
def loadRuleSet(cprmvid):
    g = Graph()
    try:
        method = detectCPRMVServeAnalysisMethod(cprmvid)
        if method != None:
            getCprmvRuleSetFromPublication(g, cprmvid, method)
        else:
            raise Exception("No supported publication repository use identifiers with the format of the given Ruleset Id.")
    except Exception as e:
        if "unbound prefix" in str(e).lower(): #TODO maybe this should not be ignonred always
            print(f"Warning: ignoring unbound prefix encountered: {e}")
        else:
            raise e
    return g
    
@with_pattern(r'.+')
def paramvalue(pvalue):
    return pvalue

def getRules(ruleidpath='', path_delimiter: str = ',', formatarg: str = 'cprmv-json', unformat: str=''):
    try:
        delimindex = ruleidpath.find(path_delimiter)
        print(delimindex)
        if delimindex > 0:
            rulesetid = ruleidpath[:delimindex].strip()
        else:
            rulesetid = ruleidpath.strip()
        print(f"Info: retrieving info for cprmv:RuleSet : {rulesetid}")
        g = loadRuleSet(rulesetid)
    except Exception as e:
        return { "error" : str(e) }
    print(f"processing starts at first rule in path {ruleidpath}")
    r = getFirstRuleByIdPath(g, ruleidpath, path_delimiter)
    if(r == None):
        return "No rules found for given path..."
    print(f"rule found {r}")
    if(formatarg == 'cprmv-json'):
        result = getRule(g, r) # this custom format has a more human readable pretty print layout
    else:
        result = g.cbd(r).serialize(format=formatarg)
    if(unformat != '' and CPRMV.definition in result):
        definition = str(' '.join(result[CPRMV.definition].split())) # transform no break spaces in regular ones
        definition = search(unformat, definition, extra_types={'paramvalue':paramvalue})
        if(definition != None):
            definition = definition.named
            definition['rulesetid'] = rulesetid
            definition['ruleidpath'] = ruleidpath
            result.update(definition)
    return result

# depth first search in the given graph g for the first rule matching the given path (the path splitted as a list) from the given rootrule
def getFirstRuleByIdPath(g, path, path_delimiter: str = ','):
    pathsplit = path.split(path_delimiter)
    firstid = pathsplit.pop(0).strip();
    for rootrule in g.subjects(CPRMV.id, Literal(firstid, lang="nl")):
        rule = getFirstRuleByIdPathSplitFromRuleAsRoot(g, rootrule, pathsplit)
        if(rule != None):
            return rule
    return None

# recursive depth first search in the given graph g for the first rule matching the path (the path splitted as a list) from the given rootrule
def getFirstRuleByIdPathSplitFromRuleAsRoot(g, rootrule, pathsplit):
    if(len(pathsplit) == 0):
        return rootrule
    rulelist = g.value(rootrule, CPRMV.contains)
    if(rulelist == None):
        return None
    while(rulelist != RDF.nil):
        rule = g.value(rulelist, RDF.first)
        ruleid = g.value(rule, CPRMV.id)
        id = pathsplit.pop(0).strip()
        subrule = None
        if(Literal(id, lang="nl") == ruleid):
            subrule = getFirstRuleByIdPathSplitFromRuleAsRoot(g, rule, pathsplit)
            pathsplit.insert(0,id)
        else:
            pathsplit.insert(0,id)
            subrule = getFirstRuleByIdPathSplitFromRuleAsRoot(g, rule, pathsplit)
        if(subrule != None):
            return subrule
        rulelist = g.value(rulelist, RDF.rest)
    return None

# retrieves all info of the given rule (and all its subrules from the given graph).
# Note that rule structures over CPRMV.contains relations should be trees, so no cyclic graphs, otherwise this method will not stop.
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
