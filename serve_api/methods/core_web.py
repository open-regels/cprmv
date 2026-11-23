from PublicationMethod import PublicationMethod
from utils.constants import CPRMVSERVE
import shutil
from urllib.request import Request, urlopen
from urllib.error import URLError
from urllib.parse import urlsplit, parse_qs, urlencode, unquote
import tempfile
import json

# core publication method that downloads a publication from the web using a given URL in which parts of publication id's are contained
# in a standardized way to resolve to the publications. This is configured in the "repository-publication-location-format" property
# of the method definition.
class core_web(PublicationMethod):

    # this method can be overridden to add headers to the request for the publication to download
    def add_headers(self, req):
        return

    # this method can be overridden to change the HTTP method, for instance into POST instead of GET
    def get_http_method(self):
        return "GET"

    def get_raw_publication(self, publication):
        cprmvMethods = self.app.cprmvsettings["CPRMVMETHODS_KG"]
        puburlformat = str(cprmvMethods.value(self.config, CPRMVSERVE["repository-publication-location-format"]))
        puburl = puburlformat.format_map(publication[CPRMVSERVE["id_parts"]])
        publication['puburl'] = puburl
        try:
            print(f"downloading publication: {puburl}")
            httpmethod = self.get_http_method()
            body=''
            if httpmethod == "POST":
                # for now we convert the query parameters as a dictionary into a body to post
                body = str(json.dumps({k: v[0] for k, v in parse_qs(urlsplit(puburl).query).items()})).encode('utf-8')
                print(f"POST BODY : {body}")
                req = Request(puburl, method="POST")
            else:
                req = Request(puburl)
            self.add_headers(req)
            if httpmethod == "POST":
                response = urlopen(req, context=self.app.SSL_CONTEXT, data=body)
            else:
                response = urlopen(req, context=self.app.SSL_CONTEXT)
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                shutil.copyfileobj(response, tmp_file)
                tmp_file.close()
                return tmp_file.name
        except URLError as e:
            if hasattr(e, "reason"):
                print("We failed to reach a server.")
                print("Reason: ", e.reason)
                raise e
            elif hasattr(e, "code"):
                print("The server couldn't fulfill the request.")
                print("Error code: ", e.code)
                raise e
        else:
            raise Exception(f"Unknown error loading publication from the web (core.web) ...")
