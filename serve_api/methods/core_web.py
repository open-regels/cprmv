from PublicationMethod import PublicationMethod
from utils.constants import CPRMVSERVE
import shutil
from urllib.request import Request, urlopen
from urllib.error import URLError
import tempfile

# core publication method that downloads a publication from the web using a given URL in which parts of publication id's are contained
# in a standardized way to resolve to the publications. This is configured in the "repository-publication-location-format" property
# of the method definition.
class core_web(PublicationMethod):
    def get_raw_publication(self, publication):
        cprmvMethods = self.app.cprmvsettings["CPRMVMETHODS_KG"]
        puburlformat = str(cprmvMethods.value(self.config, CPRMVSERVE["repository-publication-location-format"]))
        puburl = puburlformat.format_map(publication[CPRMVSERVE["id_parts"]])
        publication['puburl'] = puburl
        try:
            print(f"downloading publication: {puburl}")
            req = Request(puburl)
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
