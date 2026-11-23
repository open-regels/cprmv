from rdflib import BNode, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF
from utils.constants import CPRMV, CPRMVSERVE
from SerialisationMethod import SerialisationMethod
import json

# core serialisation method that can transform a publication that is serialised as JSON (not JSON-LD) into cprmv:RuleSet
class core_json(SerialisationMethod):

    def get_json_data(self, raw):
        print(f"opening raw publication from temp file {raw}")
        json_data = None
        with open(raw) as f:
           json_data = json.load(f)
        return json_data

    def determin_output_of_object(self, g, json_data, publication):
        return Literal("unknown")

    def determin_method(self, json_data, publication):
        return Literal(self.get_method_label())

    def get_method_label(self):
        return self.app.cprmvsettings["CPRMVMETHODS_KG"].value(self.config, CPRMV.label)

    def get_cprmv_rule_set_from_raw_publication(self, g, raw, publication):
        methodLabel = self.get_method_label()
        print(f"transforming and loading {methodLabel} resource into CPRMV RuleSet ...")
        json_data = self.get_json_data(raw)
        return self.transform_json_into_ruleset(g, json_data, publication)

    def transform_json_into_ruleset(self, g, json_data, publication):
        cprmvid = publication[CPRMVSERVE["id_parts"]]['cprmvid']
        puburl = publication['puburl']
        ruleset = BNode()
        g.add((ruleset, RDF.type, CPRMV.RuleSet))
        g.add((ruleset, CPRMV.id, Literal(cprmvid, lang="nl")))
        g.add((ruleset, CPRMV.isBasedOn , URIRef(puburl)))
        g.add((ruleset, CPRMV.isOutputOf , self.determin_output_of_object(g, json_data, publication)))
        g.add((ruleset, CPRMV.method, self.determin_method(json_data, publication)))
        rules = Collection(g, BNode())
        self.transform_rules(g, json_data, publication, rules)
        g.add((ruleset, CPRMV.hasPart, rules.uri))
        return

    def transform_rules(self, g, json_data, publication, rules):
        ruleset = {}
        keyprefix=''
        if isinstance(json_data, list):
            ruleset = enumerate(json_data)
            keyprefix='item_'
        if isinstance(json_data, dict):
            ruleset = json_data.items()
        for key, value in ruleset:
            rule = BNode()
            g.add((rule, RDF.type, CPRMV.Rule))
            g.add((rule, CPRMV.id, Literal(keyprefix+str(key), lang="nl")))
            if isinstance(value, list) or isinstance(value, dict):
                hasparts = Collection(g, BNode())
                self.transform_rules(g, value, publication, hasparts)
                g.add((rule, CPRMV.hasPart, hasparts.uri))
            else:
                g.add((rule, CPRMV.definition, Literal(value)))
            rules.append(rule)
        return
