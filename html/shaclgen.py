# Custom script for generating normative ReSpec documentation (markdown and plantuml)
# from RDFS/OWL/SHACL definitions.
#
# Note that this script has been created only for CPRMV and only supports standards as far as
# is neccesary for CPRMV

from rdflib import Graph, Namespace, BNode
from rdflib.namespace import RDF, RDFS, OWL, SH

SKOS = Namespace('http://www.w3.org/2004/02/skos/core#')

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
    vocabkg.parse('../rdf/cprmv.ttl', format="turtle")
    vocabkg.parse('../rdf/cprmv.shacl.ttl', format="turtle")
    
    classes = {}
    
    # for all classes find all properties that have them in their rdfs domain
    # and/or are sh:properties of a nodeshape that target them
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
                        #for relatesWith in asList(vocabkg, prop, SH['class']):
                        #    if (RDFS.range in classes[target]['properties'][path]) and (relatesWith in classes[target]['properties'][path][RDFS.range]):
                        print(f"processing additional information from shapes for {target}.{path}")
                        for p, o in vocabkg.predicate_objects(prop):
                            if p in [SH.minCount, SH.maxCount, SH.datatype]:
                                classes[target]['properties'][path][p] = o
    return classes

def genmd(classes, out='ch3.md'):
    for c in classes.keys():
        print(f"##{classes[c][SKOS.prefLabel]}\n\n")
        print(f"definition: {classes[c][SKOS.definition]}\n\n")
        if RDFS.subClassOf in classes[c].keys():
            if classes[c][RDFS.subClassOf] in classes.keys():
                print(f"subclass: {classes[classes[c][RDFS.subClassOf]][SKOS.prefLabel]}\n\n")
            else:
                print(f"subclass: {classes[c][RDFS.subClassOf]}\n\n")
        print("properties:\n\n")
        print("| Property | Type/Range | Cardinality | Definition |")
        print("| --- | --- | --- | --- |")
        for p in classes[c]['properties'].keys():
            prop = classes[c]['properties'][p]
            range = ''
            if (RDFS.range not in prop.keys()) or (len(prop[RDFS.range]) == 0):
                range = ' '
                if SH.datatype in prop.keys():
                    range = prop[SH.datatype]
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
            print(f"| {prop[SKOS.prefLabel]} | {range} | {prop[SH.minCount]}..{prop[SH.maxCount]} | {prop[SKOS.prefLabel]} |")
        print('\n\n')

def genpuml(classes, out='puml/overview.gen.puml'):
    n = 0
    print('```puml')
    for c in classes.keys():
        n = n + 1
        print(f"object C{n} : '{classes[c][SKOS.prefLabel]}'")
    print('```')

def main():
    classes = load()
    genpuml(classes)
    genmd(classes)


main()
