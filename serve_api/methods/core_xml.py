from utils.constants import CPRMV, CPRMVSERVE
from SerialisationMethod import SerialisationMethod
from lxml import etree

# core serialisation method that can transform a publication that is serialised as XML into cprmv:RuleSet knowledge using a given XSL transformation
# definition stored in a file of which the name is set in the method definition knowledge (xslt property). This XSL tranformation file is contained
# within the method definition folder besides the method.ttl file.
class core_xml(SerialisationMethod):
    def get_cprmv_rule_set_from_raw_publication(self, g, raw, publication):
        cprmvMethods = self.app.cprmvsettings["CPRMVMETHODS_KG"]
        cprmvid = publication[CPRMVSERVE["id_parts"]]['cprmvid']
        puburl = publication['puburl']
        methodLabel = cprmvMethods.value(self.config, CPRMV.label)
        print(f"opening raw publication from temp file {raw}")
        xml = etree.parse(open(raw))
        print(f"transforming {methodLabel} resource into CPRMV RuleSet ...")
        ac = etree.XSLTAccessControl(read_network=False, read_file=False)
        xsl = cprmvMethods.value(self.config, CPRMVSERVE["xslt"])
        transform = etree.XSLT(
            etree.parse("./data/"+xsl), access_control=ac
        )
        result = str(transform(xml, cprmvid=etree.XSLT.strparam(cprmvid), puburl=etree.XSLT.strparam(puburl)))
        g.parse(data=result, format="turtle")
        return
