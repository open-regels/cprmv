from OrganisationRegister import AcknowledgedOrganisation
from utils.constants import CPRMVSERVE

class AcknowledgedService:

    def __init__(self, ref='', orgref=''):
        self.ref = ref
        self.org = AcknowledgedOrganisation(orgref)

    def get_organisation(self):
        return self.org

class ServiceRegister():

    def __init__(self, app, method_config):
        super().__init__(app, method_config)

    def get_service_by_ruleset(self, rulesetid):
        return AcknowledgedService()

    def get_organisation_by_service(self, acknowledged_service):
        return AcknowledgedOrganisation()

    def get_services_by_organisation(self, acknowledged_organisation):
        return []

    def get_rulesets_by_service(self, acknowledged_service):
        return []
