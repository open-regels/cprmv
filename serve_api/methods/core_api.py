from core_web import core_web
from utils.constants import CPRMVSERVE, COREAPI
from rdflib.namespace import RDF

# core publication method that downloads a publication from an api using a given URL in which parts of publication id's are contained
# in a standardized way to resolve to the publications. This is configured in the "repository-publication-location-format" property of the configuration for the core_web base class.
# core_api adds the special property "api-base-url" that can be used to define or refine the service definition following CPSV-AP with the API as a Channel (Type=Other)
# core_api also adds properties for adding headers to the request to the api, especially for using a "access_token" when api's require one
class core_api(core_web):

    def __init__(self, app, method_config):
        super().__init__(app, method_config)
        self.headers = self.get_header_list()

    def get_http_method(self):
        cprmvMethods = self.app.cprmvsettings["CPRMVMETHODS_KG"]
        method = cprmvMethods.value(predicate=COREAPI["http-method"], subject=self.config, any=False)
        if method is not None and str(method) == "POST":
            return "POST"
        return "GET"

    # helper method
    def get_header_list(self):
        thismethod = self.config
        cprmvMethods = self.app.cprmvsettings["CPRMVMETHODS_KG"]
        result = {}
        header = cprmvMethods.value(predicate=COREAPI["api-headers"], subject=thismethod, any=False)
        while header is not None and header != RDF.nil:
            try:
                item = cprmvMethods.value(header, RDF.first)
                key = cprmvMethods.value(item, RDF.first)
                value = cprmvMethods.value(cprmvMethods.value(item, RDF.rest), RDF.first)
            except:
                print("unexpected structure in api-headers knowledge for method id:"+str(cprmvMethods.value(thismethod, CPRMVSERVE["id"])))
                return {}
            result[str(key)] = str(value)
            header = cprmvMethods.value(header, RDF.rest)
        return result

    def add_headers(self, req):
        incoming = self.app.current_request_headers.get()

        for header in self.headers.keys():
            if header == 'x-api-key' and self.headers[header] == 'pass_on_from_request':
                req.add_header(header, incoming[header])
            else:
                req.add_header(header, self.headers[header])
