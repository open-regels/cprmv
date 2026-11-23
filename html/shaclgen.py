# Custom script for generating normative ReSpec documentation (markdown and plantuml)
# from RDFS/OWL/SHACL definitions.
#
# Note that this script has been created only for CPRMV and only supports standards as far as
# is neccesary for CPRMV

from contextlib import redirect_stdout
from textwrap import wrap
from rdflib import Graph, Namespace, BNode
from rdflib.term import URIRef
from rdflib.namespace import RDF, RDFS, OWL, SH, XSD, split_uri

SKOS = Namespace('http://www.w3.org/2004/02/skos/core#')
CPRMV = Namespace('https://standaarden.open-regels.nl/standards/cprmv/0.4.3#')
CPRMVMETHODS = Namespace('https://cprmv.open-regels.nl/0.4.3/methods/')
CPRMVBASE = Namespace('https://standaarden.open-regels.nl/standards/cprmv/0.4.3/')
CPRMVSERVE = Namespace('https://cprmv.open-regels.nl/0.4.3/serve-api/')

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
RuleSet  -[dotted]-> service : "isOutputOf"
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
    vocabkg.parse('../rdf/0.4.3/cprmv.ttl', format="turtle")
    vocabkg.parse('../rdf/0.4.3/cprmv.shacl.ttl', format="turtle")
    vocabkg.parse('../rdf/0.4.3/cprmvmethods.ttl', format="turtle")

    modules = {}
    classes = {}

    for subject in vocabkg.subjects(RDF.type, OWL.Class):
        if subject not in CPRMV: # only classes not part of the CPRMV core vocabulary itself
            classes[subject] = { 'properties' : {}}
            for p, o in vocabkg.predicate_objects(subject):
                if p in [SKOS.prefLabel, SKOS.definition]: # properties that can only be defined once for a method
                    classes[subject][p] = o
                if p in [RDFS.subClassOf]: # properties that can be defined multiple times for a method
                    if p not in classes[subject].keys():
                        classes[subject][p] = []
                    classes[subject][p].append(o)
            if SKOS.prefLabel not in classes[subject].keys():
                print(f"Warning: class {subject} does not define a skos:prefLabel...")
            if SKOS.definition not in classes[subject].keys():
                print(f"Warning: class {subject} does not define a skos:definition...")
            print(f"added class {subject}")
    for subject in vocabkg.objects(CPRMVBASE.methods, OWL.imports): # method module folders in rdf specification
        print(f"Importing CPRMV Methods for module: {subject}")
        spfx, sns, subject_local_name = vocabkg.namespace_manager.compute_qname(subject)
        method_module_foldername = subject_local_name.replace('core-','core.')
        try:
            vocabkg.parse('../rdf/0.4.3/methods/'+method_module_foldername+'/method.ttl', format="turtle")
        except:
            print("Could not load: ../rdf/0.4.3/methods/"+method_module_foldername+"/method.ttl using RDFlib")
            continue
    for module in vocabkg.subjects(RDF.type, CPRMVMETHODS.module):
        print(f"Processing CPRMV Method module : {module}")
        modules[module] = []
        spfx, sns, subject_local_name = vocabkg.namespace_manager.compute_qname(module)
        method_module_foldername = subject_local_name.replace('core-','core.')
        for subject in asList(vocabkg, module, CPRMVMETHODS.hasMethods):
            print(f"Importing CPRMV Method : {subject}")
            spfx, sns, subject_local_name = vocabkg.namespace_manager.compute_qname(subject)
            modules[module].append(subject)
            classes[subject] = { 'properties' : {}}
            for p, o in vocabkg.predicate_objects(subject):
                if p in [SKOS.prefLabel, SKOS.definition]: # properties that can only be defined once for a method
                    classes[subject][p] = o
                if p in [RDFS.subClassOf]: # properties that can be defined multiple times for a method
                    if p not in classes[subject].keys():
                        classes[subject][p] = []
                    classes[subject][p].append(o)
            if SKOS.prefLabel not in classes[subject].keys():
                print(f"Warning: CPRMV Method class {subject} does not define a skos:prefLabel...")
                defaultvalue = vocabkg.value(subject, CPRMV.id)
                if defaultvalue is not None:
                    print(f"Warning: using default value for skos:prefLabel : cprmv:id = {vocabkg.value(subject, CPRMV.id)}") # Note this was CPRMV.label
                    classes[subject][SKOS.prefLabel] = defaultvalue
                else:
                    print(f"Warning: using default value for skos:prefLabel : {subject_local_name}")
                    classes[subject][SKOS.prefLabel] = subject_local_name
            defaultvalue = None
            #try:
            #    print(f"Attempting to use content of ../rdf/0.4.3/methods/{method_module_foldername}/README.md as SKOS.definition...")
            #    with open('../rdf/0.4.3/methods/'+method_module_foldername+'/README.md', 'r') as readmefile:
            #        defaultvalue = readmefile.read()
            #        defaultvalue = ''.join(defaultvalue.splitlines(keepends=True)[2:])
            #    print(f"Warning: using as default value for skos:definition : contents of the README.md file for this CPRMV Method")
            #    classes[subject][SKOS.definition] = defaultvalue
            #except:
            if SKOS.definition not in classes[subject].keys():
                print(f"Warning: CPRMV Method class {subject} does not define a skos:definition...")
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
                    print(f"FOUND RDF:Type {obj}")
                    if RDFS.subClassOf not in classes[subject].keys():
                        classes[subject][RDFS.subClassOf] = []
                    classes[subject][RDFS.subClassOf].append(obj)
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
    return modules, classes

def load():
    vocabkg = Graph()
    vocabkg.parse('../rdf/0.4.3/cprmv.ttl', format="turtle")
    vocabkg.parse('../rdf/0.4.3/cprmv.shacl.ttl', format="turtle")

    classes = {}

    for subject in vocabkg.subjects(RDF.type, OWL.Class):
        classes[subject] = { 'properties' : {}}
        for p, o in vocabkg.predicate_objects(subject):
            if p in [SKOS.prefLabel, SKOS.definition]: # properties that can only be defined once for a method
                classes[subject][p] = o
            if p in [RDFS.subClassOf]: # properties that can be defined multiple times for a method
                if p not in classes[subject].keys():
                    classes[subject][p] = []
                classes[subject][p].append(o)
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
                classes[domain]['properties'][prop]['value list'] = asList(vocabkg, vocabkg.value(domain, prop))

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
                    print(f"### <dfn>{URIRef(c).fragment}</dfn>\n {classes[c][SKOS.definition]}\n\n")
                else:
                    print(f"### <dfn>{classes[c][SKOS.prefLabel]}</dfn>\n {classes[c][SKOS.definition]}\n\n")
                if RDFS.subClassOf in classes[c].keys():
                    for pc in classes[c][RDFS.subClassOf]:
                        if pc in classes.keys():
                            print(f"subclass of: <a>{classes[pc][SKOS.prefLabel]}</a>\n\n")
                        elif URIRef(pc) in CPRMV:
                            print(f"subclass of: <a>{URIRef(pc).fragment}</a>\n\n")
                        else:
                            print(f"subclass of: [{pc}]({pc})\n\n")
                print(f"<figure id='concepts'><img src='./media/class.{classes[c][SKOS.prefLabel].replace('.','-').replace('_','-')}.png' alt='class diagram {classes[c][SKOS.prefLabel]}' /><figcaption>class diagram {classes[c][SKOS.prefLabel]}</figcaption></figure>")
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
                            else:
                                print(f"| | | | <a>{value}</a> |")
                print('\n\n')

def genmethodsmd(classes, out='ch03.md', title='CPRMV Specification', filter=CPRMV, modules=[]):
    for m in modules.keys():
        mns, mname = split_uri(m)
        for c in modules[m]:
            if c not in filter:
                continue
            if c not in classes:
                continue
            print(f"generating documentation for method module: {mname} ")
            print(f"generating documentation for method class: {c} ")
            print(f"with SKOS:prefLabel: {classes[c][SKOS.prefLabel]}")
    with open(out, 'w') as f:
        with redirect_stdout(f):
            print(f"# {title}\n\n")
            for m in modules.keys():
                mns, mname = split_uri(m)
                defaultvalue = ''
                try:
                    with open('../rdf/0.4.3/methods/'+mname.replace('-','.')+'/README.md', 'r') as readmefile:
                        defaultvalue = readmefile.read()
                        defaultvalue = ''.join(defaultvalue.splitlines(keepends=True)[2:])
                except:
                    defaultvalue = ''
                modulesectionwritten = False
                for c in modules[m]:
                    if c not in filter:
                        continue
                    if c not in classes:
                        continue
                    if modulesectionwritten == False:
                        print(f"## {mname} (method module)\n\n{defaultvalue}\n\n")
                        modulesectionwritten = True
                    if URIRef(c) in CPRMV:
                        print(f"### <dfn>{URIRef(c).fragment}</dfn>\n {classes[c][SKOS.definition]}\n\n")
                    else:
                        print(f"### <dfn>{classes[c][SKOS.prefLabel]}</dfn>\n {classes[c][SKOS.definition]}\n\n")
                    if RDFS.subClassOf in classes[c].keys():
                        for pc in classes[c][RDFS.subClassOf]:
                            if pc in classes.keys():
                                print(f"subclass of: <a>{classes[pc][SKOS.prefLabel]}</a>\n\n")
                            elif URIRef(pc) in CPRMV:
                                print(f"subclass of: <a>{URIRef(pc).fragment}</a>\n\n")
                            else:
                                print(f"subclass of: [{pc}]({pc})\n\n")
                    print(f"<figure id='concepts'><img src='./media/class.{classes[c][SKOS.prefLabel].replace('.','-').replace('_','-')}.png' alt='class diagram {classes[c][SKOS.prefLabel]}' /><figcaption>class diagram {classes[c][SKOS.prefLabel]}</figcaption></figure>")
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

def genpuml(
    classes,
    out='puml/overview.puml',
    classhierarchy=[],
    filter={ CPRMV.refinesFrom : CPRMV.RuleMethod, CPRMV.refinesTowards : CPRMV.RuleMethod, CPRMV.isOutputOf : URIRef("http://purl.org/vocab/cpsv#PublicService")},
    includeCPSV=True,
    wrapInPackage=True
    ):
    with open(out, 'w') as f:
        with redirect_stdout(f):
            n = 0
            print('```puml')
            print('@startuml')
            print('!pragma layout elk')
            print('left to right direction')
            print('')
            if wrapInPackage:
                print('package cprmv {')
            rels = ''
            infocus = []
            require_objects = []
            included_objects = []
            for h in classhierarchy:
                for c in classes.keys():
                    if str(h).startswith("*"):
                        if str(c).endswith(str(h)[1:]):
                            infocus.append(c)
                    elif c == h:
                        infocus.append(c)
            for c in classes.keys():
                if len(infocus) > 0 and c not in infocus:
                    continue
                cns, cname = split_uri(URIRef(c))
                cnameobj = cname.replace('.','_').replace('-','_')
                if RDFS.subClassOf in classes[c].keys():
                    for pc in classes[c][RDFS.subClassOf]:
                        if pc in classes.keys():
                            parentns, parentname = split_uri(URIRef(pc))
                            parentnameobj = parentname.replace('.','_').replace('-','_')
                            if parentname not in require_objects:
                                require_objects.append(parentname)
                            rels = rels + f"    {cnameobj} --|> {parentnameobj}\n"
                included_objects.append(cname)
                print(f"    object \"{cname}\" as {cnameobj} {{")
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
                            rns, rname = split_uri(URIRef(rangeclass))
                            rnameobj = rname.replace('.','_').replace('-','_')
                            if p in filter and c != filter[p]:
                               continue
                            if SH.minCount not in prop.keys():
                                prop[SH.minCount] = 0
                            if SH.maxCount not in prop.keys():
                                prop[SH.maxCount] = '*'
                            cardinality = f" \"{prop[SH.minCount]}..{prop[SH.maxCount]}\""
                            rels = rels + f"    {cnameobj} -->{cardinality} {rnameobj} : {URIRef(p).fragment}\n"
                            if rname not in require_objects:
                                require_objects.append(rname)
                print("    }")
            for obj in require_objects:
                if obj not in included_objects:
                    objname = obj.replace('.','_').replace('-','_')
                    print(f"    object \"{obj}\" as {objname}")
            print(rels)
            if wrapInPackage:
                print('}')
            if includeCPSV:
                print(CPSVAP3_2_0_PUML)
                print(CPRMV_CPSV_PUML)
            print('@enduml')
            print('```')

def genpumlforallclasses(classes):
    for c in classes.keys():
        ns, name = split_uri(c)
        name = name.replace('.','-').replace('_','-')
        print(f"Generating class diagram for {ns} {name}...")
        if ns in [CPRMV, CPRMVMETHODS, CPRMVSERVE]:
            genpuml(classes, out=f"puml/class.{name}.puml", classhierarchy=[c], includeCPSV=False, wrapInPackage=False)
        else:
            print(f"skipping , because it is not defined in the CPRMV namespace: {str(CPRMV)} as its namespace is: {ns}...")

def main():
    classes = load() # CPRMV namespace, chapter 3
    genpuml(classes, classhierarchy=[CPRMV.RuleSet, CPRMV.Rule, CPRMV.Instrument, CPRMV.Method, CPRMV.RuleMethod])
    genpuml(classes, out='puml/echelons-and-methods.puml', classhierarchy=["*Echelon", "*Method"], includeCPSV=False)
    genpumlforallclasses(classes)
    genmd(classes)
    modules, mclasses = loadmethods() # CPRMV Methods / Serve API namespaces, chapter 4 and 5
    genpumlforallclasses(mclasses | classes)
    moduleclasses = {} # classes referenced in cprmvmethod:module's
    methodnsclasses = {} # classes not referenced in cprmvmethod:module's
    for c in mclasses.keys():
        for m in modules.keys():
            if c in modules[m]:
                moduleclasses[c] = mclasses[c]
    for c in mclasses.keys():
        if c not in moduleclasses:
            methodnsclasses[c] = mclasses[c]
    genmd(methodnsclasses | classes, 'methods.md', "CPRMV Methods", CPRMVMETHODS)
    genmethodsmd(moduleclasses, 'modules.md', "CPRMV Method Modules", CPRMVMETHODS, modules)
    genmethodsmd(moduleclasses, 'api.md', "CPRMV API", CPRMVSERVE, modules)
main()
