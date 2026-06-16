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
        return list
    if prop is not None:
        return asList(kg, kg.value(obj, prop))
    return [obj]

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
            
    for shape in vocabkg.subjects(RDF.type, SH.NodeShape):
        target = vocabkg.value(shape, SH.targetClass)
        if target in classes.keys():
            for prop in vocabkg.objects(shape, SH.property):
                path = vocabkg.value(prop, SH.path)
                if path is not None:
                    if path in classes[target]['properties'].keys():
                        print(f"processing additional information from shapes for {target}.{path}")
                        for p, o in vocabkg.predicate_objects(prop):
                            if p in [SH.minCount, SH.maxCount, SH.datatype]:
                                classes[target]['properties'][path][p] = o
    return classes

def genmd(classes, out='ch03.md'):
    with open(out, 'w') as f:
        with redirect_stdout(f):
            print(f"# CPRMV Specification\n\n")
            for c in classes.keys():
                print(f"## <dfn>{URIRef(c).fragment}</dfn>\n {classes[c][SKOS.definition]}\n\n")
                link = '-'.join(classes[c][SKOS.prefLabel].split())
                if RDFS.subClassOf in classes[c].keys():
                    if classes[c][RDFS.subClassOf] in classes.keys():
                        print(f"subclass of: <a>{URIRef(classes[c][RDFS.subClassOf]).fragment}</a>\n\n")
                    else:
                        print(f"subclass of: [{classes[c][RDFS.subClassOf]}]({classes[c][RDFS.subClassOf]})\n\n")
                print("properties (excluding inherited):\n\n")
                print("| Property | Type/Range | Cardinality | Definition |")
                print("| --- | --- | --- | --- |")
                for p in classes[c]['properties'].keys():
                    prop = classes[c]['properties'][p]
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
                            range = range + delim + ' ' + classes[rangeclass][SKOS.prefLabel]
                            delim = ','
                        if SH.maxCount not in prop.keys():
                            prop[SH.maxCount] = '*'
                    if SH.minCount not in prop.keys():
                        prop[SH.minCount] = 0
                    print(f"| {prop[SKOS.prefLabel]} | {range} | {prop[SH.minCount]}..{prop[SH.maxCount]} | {prop[SKOS.definition]} |")
                print('\n\n')

def genpuml(classes, out='puml/overview.puml'):
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
    genpuml(classes)
    genmd(classes)

main()
