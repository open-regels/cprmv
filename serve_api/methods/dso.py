from core_api import core_api
from sttr import sttr
from ServiceRegister import AcknowledgedService, ServiceRegister
from OrganisationRegister import AcknowledgedOrganisation
from core_json import core_json
from rdflib import Graph, URIRef, Literal, BNode
from rdflib.namespace import RDF
from utils.constants import CPSV, CPRMV

class dso(core_api, sttr):

    def get_cprmv_rule_set_from_raw_publication(self, g, raw, publication):
        super().get_cprmv_rule_set_from_raw_publication(g, raw, publication)
        self.determin_output_of_object(g, publication)

    def determin_output_of_object(self, g, publication):
        # return the related knowledge for the cprmv:isOuputOf relation to g which is the service and organisation
        # as competent_authority attached to it following CPSV-AP
        cprmvMethods = self.app.cprmvsettings["CPRMVMETHODS_KG"]
        serviceregister_method_module = None
        serviceregister_method_id = str(cprmvMethods.value(subject=self.service_register , predicate=CPRMV.id)).replace('-','_').replace('.','_')
        print(f"Accessing ServiceRegister Method: {serviceregister_method_id}")
        if serviceregister_method_id in self.app.cprmvmethods:
            serviceregister_method_module = self.app.cprmvmethods[serviceregister_method_id]
            print("ServiceRegister Method module found")
        svc = serviceregister_method_module.get_service_by_ruleset(publication)
        org = serviceregister_method_module.get_acknowledged_organisation_by_service(svc)
        svcnode = BNode()
        orgnode = BNode()
        g.add((svcnode, RDF.type, CPSV.PublicService))
        g.add((svcnode, CPSV.identifier, Literal(svc.ref)))
        g.add((orgnode, RDF.type, CPSV.PublicOrganisation))
        g.add((orgnode, CPSV.preferredLabel, Literal(org.ref)))
        g.add((svcnode, CPSV.has_competent_authority, orgnode))
        g.add((g.value(predicate=RDF.type, object=CPRMV.DecisionModel), CPRMV.isOutputOf, svcnode))

class dso_service_register(ServiceRegister, core_api, core_json):

    def get_service_by_ruleset(self, publication):
        g = Graph()
        self.get_cprmv_rule_set_from_publication(g, publication)
        subj = g.value(predicate=CPRMV.id, object=Literal("functioneleStructuurRef", lang="nl"))
        print(f"determined subj node: {subj}")
        service = str(g.value(subject=subj, predicate=CPRMV.definition))
        print(f"determined CPSV-AP service: {service}")
        organisation = str(g.value(subject=g.value(predicate=CPRMV.id, object=Literal('oin', lang="nl")), predicate=CPRMV.definition))
        print(f"determined CPSV-AP organisation: {organisation}")
        return AcknowledgedService(service, organisation)

    def get_acknowledged_organisation_by_service(self, acknowledged_service):
        # DSO uses OIN numbers to indicate organisations while the configuration may indicate a different type of identifier that needs to be looked up
        # in the utilised organisation register using the provided OIN number. The OrganisationRegister method utilised must accept OIN numbers as the ruleset id
        # (the part of the first id in the cprmvid path exluding the method prefix and valid date and index parts)
        key = 'uri' # we always want the uri type of identifier given the oin number as this is the main type used when accessing the ROO api
        oin = acknowledged_service.get_organisation().ref
        cprmvMethods = self.app.cprmvsettings["CPRMVMETHODS_KG"]
        organisationregister_method_module = None
        organisationregister_method_id = str(cprmvMethods.value(subject=self.organisation_register , predicate=CPRMV.id)).replace('-','_').replace('.','_')
        print(f"Accessing OrganisationRegister Method: {organisationregister_method_id}")
        if organisationregister_method_id in self.app.cprmvmethods:
            organisationregister_method_module = self.app.cprmvmethods[organisationregister_method_id]
            print("OrganisationRegister Method module found")
        publication = organisationregister_method_module.interpret_publication_id('ROO.oin='+oin)
        g = Graph()
        organisationregister_method_module.get_cprmv_rule_set_from_publication(g, publication)
        print("loaded OrganisationRegister query result")
        subj = g.value(predicate=CPRMV.id, object=Literal(key, lang="nl"))
        print(f"found subject node: "+subj)
        orgkey = str(g.value(subject=subj, predicate=CPRMV.definition))
        print(f"oin: {oin} => uri: {orgkey}")
        return AcknowledgedOrganisation(orgkey)

    def get_services_by_organisation(self, acknowledged_organisation):
        return []

    def get_rulesets_by_service(self, acknowledged_service):
        return []

    def determin_method(self, json_data, publication):
        return URIRef("https://cprmv.open-regels.nl/0.4.4/methods/dso-service-register")
