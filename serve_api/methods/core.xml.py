
class core_xml(SerialisationMethod):
    # NOTE this implementation only supports methods that are core.xml method based (but does not check for that)
    def get_cprmv_rule_set_from_raw_publication(g, raw, publication_metadata = {}):
        cprmvid = method[CPRMVSERVE["id_parts"]]['cprmvid']
        # the following depends on the core.web publication method.. core.xml implies core.web? .. move out
        puburlformat = str(method[CPRMVSERVE["repository-publication-location-format"]])
        puburl = puburlformat.format_map(method[CPRMVSERVE["id_parts"]])
        methodLabel = method[CPRMV.label]
        try:
            print(f"opening raw publication from temp file {tmp_file.name}")
            xml = etree.parse(open(raw))
            print(f"transforming {methodLabel} resource into CPRMV RuleSet ...")
            ac = etree.XSLTAccessControl(read_network=False, read_file=False)
            transform = etree.XSLT(
                etree.parse(method[CPRMVSERVE.xslt]), access_control=ac
            )
            result = str(transform(xml, cprmvid=etree.XSLT.strparam(cprmvid), puburl=etree.XSLT.strparam(puburl)))
            os.remove(tmp_file.name)
            # print(result)
            g.parse(data=result, format="turtle")
            return
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
            raise Exception(f"unknown error loading {methodLabel} publication ...")
