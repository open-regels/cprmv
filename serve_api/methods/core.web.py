
class core_web(PublicationMethod):
    # NOTE this implementation only supports methods that are core.xml method based (but does not check for that)
    def get_raw_publication():
        cprmvid = method[CPRMVSERVE["id_parts"]]['cprmvid']
        # the following depends on the core.web publication method.. core.xml implies core.web?
        puburlformat = str(method[CPRMVSERVE["repository-publication-location-format"]])
        puburl = puburlformat.format_map(method[CPRMVSERVE["id_parts"]])
        methodLabel = method[CPRMV.label]
        try:
            print(f"downloading publication: {puburl}")
            req = Request(puburl)
            response = urlopen(req, context=SSL_CONTEXT)
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                shutil.copyfileobj(response, tmp_file)
                tmp_file.close()
                return tmp_file.name)
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
