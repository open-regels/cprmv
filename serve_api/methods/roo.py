from OrganisationRegister import OrganisationRegister
from core_api import core_api
from core_json import core_json
from rdflib import URIRef, BNode
from rdflib.namespace import RDF
from utils.constants import CPSV, COREAPI

class roo(OrganisationRegister, core_api, core_json):

    def get_organisation_by_ruleset(self, rulesetid):
        return AcknowledgedOrganisation()

    def determin_method(self, json_data, publication):
        return URIRef("https://cprmv.open-regels.nl/0.4.3/methods/roo")

    def get_cprmv_rule_set_from_raw_publication(self, g, raw, publication):
        super().get_cprmv_rule_set_from_raw_publication(g, raw, publication)

    def determin_output_of_object(self, g, json_data, publication):
        svc = BNode() # Note this service is not (yet) in any service register
        org = URIRef('https://identifier.overheid.nl/tooi/id/ministerie/mnre1034') # BZK
        g.add((org, RDF.type, CPSV.PublicOrganisation))
        channel = BNode() # An api forms the channel (type=Other) for this service
        g.add((channel, RDF.type, CPSV.Channel))
        g.add((channel, URIRef('http://purl.org/dc/terms/type'), URIRef('http://data.europa.eu/snb/com-channel/c_8106f76d'))) # "Other" channel
        g.add((channel, COREAPI["api-base-url"], URIRef('https://api-organisaties.overheid.nl/v1/')))
        g.add((channel, CPSV["ownedBy"], URIRef('https://identifier.overheid.nl/tooi/id/oorg/oorg10117'))) # Channel owned by KOOP (part of Logius)
        g.add((svc, RDF.type, CPSV.PublicService))
        g.add((svc, CPSV["hasCompetentAuthority"] ,org))
        g.add((svc, CPSV["hasChannel"],  channel))
        return svc

class roo_uri(roo):
    pass

class roo_catalogus(roo):
    pass
