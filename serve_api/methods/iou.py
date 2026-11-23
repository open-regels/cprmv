from operaton import operaton
from core_web import core_web
from core_json import core_json
from rdflib import BNode, Literal, URIRef
from rdflib.namespace import RDF
from utils.constants import CPRMV, anyVersionOf

class iou_operaton(operaton):
    pass

class iou_norms(core_web, core_json):

    def transform_rules(self, g, json_data, publication, rules):
        for item in json_data['data']['rules']:
            rule = BNode()
            definition = {}
            for key, value in item.items():
                if anyVersionOf(key) == anyVersionOf(RDF.type):
                    g.add((rule, RDF.type, URIRef(value)))
                elif anyVersionOf(key) == anyVersionOf(CPRMV.id):
                    g.add((rule, CPRMV.id, Literal(value, lang="nl")))
                else:
                    definition[key] = value
            g.add((rule, CPRMV.definition, Literal(definition)))
            rules.append(rule)
        return
