# Custom script for generating normative ReSpec documentation (markdown and plantuml)
# from RDFS/OWL/SHACL definitions.
#
# Note that this script has been created only for CPRMV and only supports standards as far as
# is neccesary for CPRMV

from contextlib import redirect_stdout
from rdflib import Graph, Namespace, BNode
from rdflib.term import URIRef
from rdflib.namespace import RDF, RDFS, OWL, SH, XSD

SKOS = Namespace('http://www.w3.org/2004/02/skos/core#')
CPRMV = Namespace('https://standaarden.open-regels.nl/standards/cprmv/0.4.2#')
CPRMVMETHODS = Namespace('https://cprmv.open-regels.nl/0.4.2/methods/')
CPRMVBASE = Namespace('https://standaarden.open-regels.nl/standards/cprmv/0.4.2/')
CPRMVSERVE = Namespace('https://cprmv.open-regels.nl/0.4.2/serve-api/')

CPSVAP3_2_0_PUML = """

package "cpsv-ap v3.2.0 (relevant part)" as cpsv-ap {
    object "cpsv-ap:Rule" as cpsvrule
    object "cpsv-ap:PublicService" as service
    service "0..*" -u-> cpsvrule : follows

    object "frbroo:F1_Work" as frbrooWork
    object "eli:LegalResource" as legalresource
    frbrooWork <|-- legalresource
    legalresource <-[dotted]- "0..*" cpsvrule : implements
    object "cv:output" as output
    service "0..*" -l-> output : produces
    object "dcat:dataset" as dcat
    output --> "0..*" dcat : isPartOf
    object "cv:Event" as event
    object "cv.LifeEvent" as lifeevent
    lifeevent -u-|> event
    service <-- event : hasRelatedService
    service --> event : isGroupedBy

    object "cv:PublicOrganisation" as organisation
    service --> "1..*" organisation : hasCompetentAuthority

    service "0..*" --> service : requires
    service "0..*" --> service : related
}

"""

CPRMV_CPSV_PUML = """

RuleSet --> "1..1" frbrooWork : isBasedOn
RuleSet  -[dotted]-> service : "output-of"
output <|--  RuleSet
frbrooWork <|--  RuleSet
"""

def asList(kg, obj, prop = None):
    #print(f"ASLIST CALL obj:{obj} prop:{prop}")
    if obj is None:
        return []
    if obj == RDF.nil:
        return []
    if isinstance(obj, BNode):
        list = asList(kg, kg.value(obj, RDF.rest))
        list.extend(asList(kg, kg.value(obj, RDF.first)))
        list.extend(asList(kg, kg.value(obj, OWL.unionOf)))
        if prop is not None:
            list.extend(asList(kg, kg.value(obj, prop)))
        if len(list) > 0:
            return list
    if prop is not None:
        return asList(kg, kg.value(obj, prop))
    return [obj]

def loadmethods():
    vocabkg = Graph()
    vocabkg.parse('../rdf/0.4.2/cprmv.ttl', format="turtle")
    vocabkg.parse('../rdf/0.4.2/cprmv.shacl.ttl', format="turtle")
    vocabkg.parse('../rdf/0.4.2/cprmvmethods.ttl', format="turtle")

    classes = {}

    for subject in vocabkg.subjects(RDF.type, OWL.Class):
        if subject not in CPRMV: # only classes not part of the CPRMV core vocabulary itself
            classes[subject] = { 'properties' : {}}
            for p, o in vocabkg.predicate_objects(subject):
                if p in [SKOS.prefLabel, SKOS.definition, RDFS.subClassOf ]:
                    classes[subject][p] = o
            if SKOS.prefLabel not in classes[subject].keys():
                print(f"Warning: class {subject} does not define a skos:prefLabel...")
            if SKOS.definition not in classes[subject].keys():
                print(f"Warning: class {subject} does not define a skos:definition...")
            print(f"added class {subject}")
    for subject in vocabkg.objects(CPRMVBASE.methods, OWL.imports):
        print(f"Importing CPRMV Method class: {subject}")
        spfx, sns, subject_local_name = vocabkg.namespace_manager.compute_qname(subject)
        method_foldername = subject_local_name.replace('core-','core.')
        try:
            vocabkg.parse('../rdf/0.4.2/methods/'+method_foldername+'/method.ttl', format="turtle")
        except:
            print("Could not load: ../rdf/0.4.2/methods/"+method_foldername+"/method.ttl using RDFlib")
            continue
        classes[subject] = { 'properties' : {}}
        for p, o in vocabkg.predicate_objects(subject):
            if p in [SKOS.prefLabel, SKOS.definition, RDFS.subClassOf ]:
                classes[subject][p] = o
        if SKOS.prefLabel not in classes[subject].keys():
            print(f"Warning: CPRMV Method class {subject} does not define a skos:prefLabel...")
            defaultvalue = vocabkg.value(subject, CPRMV.label)
            if defaultvalue is not None:
                print(f"Warning: using default value for skos:prefLabel : cprmv:label = {vocabkg.value(subject, CPRMV.label)}")
                classes[subject][SKOS.prefLabel] = defaultvalue
            else:
                print(f"Warning: using default value for skos:prefLabel : {subject_local_name}")
                classes[subject][SKOS.prefLabel] = subject_local_name
        if SKOS.definition not in classes[subject].keys():
            print(f"Warning: CPRMV Method class {subject} does not define a skos:definition...")
            defaultvalue = None
            try:
                print(f"Attempting to use content of ../rdf/0.4.2/methods/{method_foldername}/README.md as SKOS.definition...")
                with open('../rdf/0.4.2/methods/'+method_foldername+'/README.md', 'r') as readmefile:
                    defaultvalue = readmefile.read()
                    defaultvalue = ''.join(defaultvalue.splitlines(keepends=True)[2:])
                print(f"Warning: using default value for skos:definition : contents of the README.md file for this CPRMV Method")
                classes[subject][SKOS.definition] = defaultvalue
            except:
                defaultvalue = vocabkg.value(subject, CPRMV.comment)
                if defaultvalue is not None:
                    print(f"Warning: using default value for skos:definition : cprmv:comment = {vocabkg.value(subject, CPRMV.comment)}")
                    classes[subject][SKOS.definition] = defaultvalue
                else:
                    print(f"Warning: using default value for skos:definition : local name = {subject_local_name}")
                    classes[subject][SKOS.definition] = subject_local_name
        if RDFS.subClassOf not in classes[subject].keys():
            print(f"Warning: CPRMV Method class {subject} does not define a RDFS.subClassOf... using default: last RDF:type declaration found (if any)")
            lastSubClassOf = None
            for obj in vocabkg.objects(subject, RDF.type):
                lastSubClassOf = obj
                print(f"FOUND RDF:Type {obj}")
            if lastSubClassOf is not None:
                classes[subject][RDFS.subClassOf] = lastSubClassOf
        print(f"added class {subject}")
    for prop in vocabkg.subjects(RDF.type, OWL.ObjectProperty):
        if prop in CPRMV: # we already processes these as part of the CPRMV specification
            continue
        print(f"Processing property {prop}")
        for domain in asList(vocabkg, prop, RDFS.domain):
            print(f"property {prop} has a rdfs.domain class: {domain}")
            if domain in classes.keys():
                print(f"found information for {domain}.{prop}")
                classes[domain]['properties'][prop] = {}
                for p, o in vocabkg.predicate_objects(prop):
                    if p in [SKOS.prefLabel, SKOS.definition, RDFS.subPropertyOf]:
                        classes[domain]['properties'][prop][p] = o
                if SKOS.prefLabel not in classes[domain]['properties'][prop].keys():
                    print(f"Warning: property {prop} does not define a skos:prefLabel...")
                if SKOS.definition not in classes[domain]['properties'][prop].keys():
                    print(f"Warning: property {prop} does not define a skos:definition...")
                for range in asList(vocabkg, prop, RDFS.range):
                    if range in classes.keys():
                        if RDFS.range not in classes[domain]['properties'][prop]:
                            classes[domain]['properties'][prop][RDFS.range] = []
                        classes[domain]['properties'][prop][RDFS.range].append(range)
                        print(f"range class : {range}")
                classes[domain]['properties'][prop]['value list'] = asList(vocabkg, vocabkg.value(domain, prop))

    for shape in vocabkg.subjects(RDF.type, SH.NodeShape):
        target = vocabkg.value(shape, SH.targetClass)
        if target in classes.keys():
            for prop in vocabkg.objects(shape, SH.property):
                path = vocabkg.value(prop, SH.path)
                if path is not None:
                    if path in classes[target]['properties'].keys():
                        print(f"processing additional information from shapes for {target}.{path}")
                        for p, o in vocabkg.predicate_objects(prop):
                            if p in [SH.minCount, SH.maxCount, SH.datatype, SH['class']]:
                                classes[target]['properties'][path][p] = o
                            if p in [SH['class']]:
                                classes[target]['properties'][path][p] = o
                                for c in asList(vocabkg, prop, p):
                                    if c in classes.keys():
                                        if RDFS.range not in classes[target]['properties'][path]:
                                            classes[target]['properties'][path][RDFS.range] = []
                                        classes[target]['properties'][path][RDFS.range].append(c)
                                        print(f"range class : {c}")
    return classes

def load():
    vocabkg = Graph()
    vocabkg.parse('../rdf/0.4.2/cprmv.ttl', format="turtle")
    vocabkg.parse('../rdf/0.4.2/cprmv.shacl.ttl', format="turtle")

    classes = {}

    for subject in vocabkg.subjects(RDF.type, OWL.Class):
        classes[subject] = { 'properties' : {}}
        for p, o in vocabkg.predicate_objects(subject):
            if p in [SKOS.prefLabel, SKOS.definition, RDFS.subClassOf ]:
                classes[subject][p] = o
        if SKOS.prefLabel not in classes[subject].keys():
            print(f"Warning: class {subject} does not define a skos:prefLabel...")
        if SKOS.definition not in classes[subject].keys():
            print(f"Warning: class {subject} does not define a skos:definition...")
        print(f"added class {subject}")
    for prop in vocabkg.subjects(RDF.type, OWL.ObjectProperty):
        print(f"Processing property {prop}")
        for domain in asList(vocabkg, prop, RDFS.domain):
            #print(f"property {prop} has a rdfs.domain class: {domain}")
            if domain in classes.keys():
                print(f"found information for {domain}.{prop}")
                classes[domain]['properties'][prop] = {}
                for p, o in vocabkg.predicate_objects(prop):
                    if p in [SKOS.prefLabel, SKOS.definition, RDFS.subPropertyOf]:
                        classes[domain]['properties'][prop][p] = o
                if SKOS.prefLabel not in classes[domain]['properties'][prop].keys():
                        print(f"Warning: property {prop} does not define a skos:prefLabel...")
                if SKOS.definition not in classes[domain]['properties'][prop].keys():
                        print(f"Warning: property {prop} does not define a skos:definition...")
                for range in asList(vocabkg, prop, RDFS.range):
                    if range not in classes.keys() and range not in OWL:
                        if RDFS.range not in classes[domain]['properties'][prop]:
                            classes[domain]['properties'][prop][RDFS.range] = []
                        if range not in classes[domain]['properties'][prop][RDFS.range]:
                            classes[domain]['properties'][prop][RDFS.range].append(range)
                            print(f"range class : {range}")

    for shape in vocabkg.subjects(RDF.type, SH.NodeShape):
        target = vocabkg.value(shape, SH.targetClass)
        if target in classes.keys():
            for prop in vocabkg.objects(shape, SH.property):
                path = vocabkg.value(prop, SH.path)
                if path is not None and not isinstance(path, BNode): # we do not support complex path definitions
                    print(f"processing additional information from shapes for {target}.{path}")
                    if path not in classes[target]['properties'].keys():
                        classes[target]['properties'][path] = {}
                        for p, o in vocabkg.predicate_objects(path):
                            if p in [SKOS.prefLabel, SKOS.definition, RDFS.subPropertyOf]:
                                classes[target]['properties'][path][p] = o
                    for p, o in vocabkg.predicate_objects(prop):
                        if p in [SH.minCount, SH.maxCount, SH.datatype]:
                            classes[target]['properties'][path][p] = o
                        if p == SH['class']:
                            for c in asList(vocabkg, o):
                                if RDFS.range not in classes[target]['properties'][path]:
                                    classes[target]['properties'][path][RDFS.range] = []
                                if c not in classes[target]['properties'][path][RDFS.range]:
                                    classes[target]['properties'][path][RDFS.range].append(c)
                                    print(f"range class : {c}")
                        if p == SH['or']:
                            for c in asList(vocabkg, o):
                                for p2, c2 in vocabkg.predicate_objects(c):
                                    if p2 == SH['class']:
                                        if RDFS.range not in classes[target]['properties'][path]:
                                            classes[target]['properties'][path][RDFS.range] = []
                                        if c2 not in classes[target]['properties'][path][RDFS.range]:
                                            classes[target]['properties'][path][RDFS.range].append(c2)
                                            print(f"range class : {c2}")

    return classes

def genmd(classes, out='ch03.md', title='CPRMV Specification', filter=CPRMV):
    for c in classes.keys():
        if c not in filter:
            continue
        print(f"generating documentation for class: {c} ")
        print(f"with SKOS:prefLabel: {classes[c][SKOS.prefLabel]}")
    with open(out, 'w') as f:
        with redirect_stdout(f):
            print(f"# {title}\n\n")
            for c in classes.keys():
                if c not in filter:
                    continue
                if URIRef(c) in CPRMV:
                    print(f"## <dfn>{URIRef(c).fragment}</dfn>\n {classes[c][SKOS.definition]}\n\n")
                else:
                    print(f"## <dfn>{classes[c][SKOS.prefLabel]}</dfn>\n {classes[c][SKOS.definition]}\n\n")
                if RDFS.subClassOf in classes[c].keys():
                    if classes[c][RDFS.subClassOf] in classes.keys():
                        print(f"subclass of: <a>{classes[classes[c][RDFS.subClassOf]][SKOS.prefLabel]}</a>\n\n")
                    elif URIRef(classes[c][RDFS.subClassOf]) in CPRMV:
                        print(f"subclass of: <a>{URIRef(classes[c][RDFS.subClassOf]).fragment}</a>\n\n")
                    else:
                        print(f"subclass of: [{classes[c][RDFS.subClassOf]}]({classes[c][RDFS.subClassOf]})\n\n")
                print("properties:\n\n")
                print("| Property | Type/Range | Cardinality | Definition |")
                print("| --- | --- | --- | --- |")
                for p in classes[c]['properties'].keys():
                    prop = classes[c]['properties'][p]
                    if SKOS.prefLabel not in prop.keys():
                        prop[SKOS.prefLabel] = 'unknown, no SKOS.prefLabel for property '+p
                    if SKOS.definition not in prop.keys():
                        prop[SKOS.definition] = 'unknown, no SKOS.definition for property'+p
                    range = ''
                    if (RDFS.range not in prop.keys()) or (len(prop[RDFS.range]) == 0):
                        range = ' '
                        if SH.datatype in prop.keys():
                            range = prop[SH.datatype]
                            range = range.replace(str(XSD), "xsd:")
                        if SH.maxCount not in prop.keys():
                            prop[SH.maxCount] = 1
                    else:
                        delim = ''
                        for rangeclass in prop[RDFS.range]:
                            if rangeclass not in classes.keys():
                                range = range + delim + ' ' + rangeclass
                            else:
                                range = range + delim + ' ' + classes[rangeclass][SKOS.prefLabel]
                            delim = ','
                        if SH.maxCount not in prop.keys():
                            prop[SH.maxCount] = '*'
                    if SH.minCount not in prop.keys():
                        prop[SH.minCount] = 0
                    print(f"| {prop[SKOS.prefLabel]} | {range} | {prop[SH.minCount]}..{prop[SH.maxCount]} | {prop[SKOS.definition]} |")
                    if ('value list' in prop.keys()) and (prop['value list']) is not None:
                        for value in prop['value list']:
                            if value in classes.keys():
                                print(f"| | | | <a>{classes[value][SKOS.prefLabel]}</a> |")
                print('\n\n')

def genpuml(classes, out='puml/overview.puml', filter={ CPRMV.refinesFrom : CPRMV.RuleMethod, CPRMV.refinesTowards : CPRMV.RuleMethod}):
    with open(out, 'w') as f:
        with redirect_stdout(f):
            n = 0
            print('```puml')
            print('@startuml')
            print('!pragma layout elk')
            print('left to right direction')
            print('')
            print('package cprmv {')
            rels = ''
            for c in classes.keys():
                print(f"    object \"{URIRef(c).fragment}\" as {URIRef(c).fragment} {{")
                for p in classes[c]['properties'].keys():
                    prop = classes[c]['properties'][p]
                    if (RDFS.range not in prop.keys()) or (len(prop[RDFS.range]) == 0):
                        t = ''
                        if SH.datatype in prop.keys():
                            t = prop[SH.datatype]
                            t = t.replace(str(XSD), " : xsd:")
                        print(f"        {URIRef(p).fragment}{t}")
                    else:
                        for rangeclass in prop[RDFS.range]:
                            if p in filter and c != filter[p]:
                               continue
                            if SH.minCount not in prop.keys():
                                prop[SH.minCount] = 0
                            if SH.maxCount not in prop.keys():
                                prop[SH.maxCount] = '*'
                            cardinality = f" \"{prop[SH.minCount]}..{prop[SH.maxCount]}\""
                            rels = rels + f"    {URIRef(c).fragment} -->{cardinality} {URIRef(rangeclass).fragment} : {URIRef(p).fragment}\n"
                print("    }")
                if RDFS.subClassOf in classes[c].keys():
                    if classes[c][RDFS.subClassOf] in classes.keys():
                        rels = rels + f"    {URIRef(c).fragment} --|> {URIRef(classes[c][RDFS.subClassOf]).fragment}\n"
            print(rels)
            print('}')
            print(CPSVAP3_2_0_PUML)
            print(CPRMV_CPSV_PUML)
            print('@enduml')
            print('```')

def main():
    classes = load()
    print(classes[CPRMV.RuleSet]['properties'][CPRMV.hasMethod])
    genpuml(classes)
    genmd(classes)
    classes = loadmethods()
    genmd(classes, 'methods.md', "CPRMV Methods", CPRMVMETHODS)
    genmd(classes, 'api.md', "CPRMV API", CPRMVSERVE)
main()
