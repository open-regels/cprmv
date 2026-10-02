from datetime import datetime
from ReferenceMethod import ReferenceMethod
from utils.constants import CPRMVSERVE, CPRMVMETHODS
from rdflib.namespace import RDF

class juriconnect(ReferenceMethod):
    # helper method
    def get_mapping(self):
        referencemethod = self.config
        cprmvMethods = self.app.cprmvsettings["CPRMVMETHODS_KG"]
        result = {}
        mapping = cprmvMethods.value(predicate=CPRMVSERVE["reference-mapping"], subject=referencemethod, any=False)
        while mapping is not None and mapping != RDF.nil:
            try:
                item = cprmvMethods.value(mapping, RDF.first)
                key = cprmvMethods.value(item, RDF.first)
                value = cprmvMethods.value(cprmvMethods.value(item, RDF.rest), RDF.first)
            except:
                print("unexpected structure in reference mapping knowledge for reference method id:"+str(cprmvMethods.value(referencemethod, CPRMVSERVE["id"])))
                return {}
            result[str(key)] = str(value)
            mapping = cprmvMethods.value(mapping, RDF.rest)
        return result

    # note that JuriConnect implies BWB
    def transform_reference(self, reference):
        reference_parts = self.parse_reference(reference)
        if reference_parts is None:
            return None
        if 'subversion' not in reference_parts:
            print("Invalid call to transform_jci_reference. No subversion part in reference parts...")
            return None
        if reference_parts['subversion'] not in ('3','31'):
            print("No valid juriconnect version (must be 1.3 or 1.31)")
            return None
        path = '/rules/'
        cprmvMethods = self.app.cprmvsettings["CPRMVMETHODS_KG"]
        id_format = str(cprmvMethods.value(CPRMVMETHODS['repository-overheid-nl-bwb'], CPRMVSERVE['normalized-id-format']))
        id_parts = {}
        mapping = self.get_mapping()
        if len(reference_parts['bwbid']) != 8:
            return None
        locstr = reference_parts['locatie-string']
        locstr_path = ''
        delim = ''
        for part in locstr.split('&'):
            kv = part.split('=')
            if len(kv) != 2:
                return None
            if kv[0] == mapping[str(CPRMVSERVE['reference-mapping-valid-on'])]:
                id_parts['date'] = kv[1]
            elif kv[0] == mapping[str(CPRMVSERVE['reference-mapping-seen-on'])]:
                id_parts['index'] = kv[1]
            elif kv[0] in mapping:
                locstr_path = locstr_path+delim+mapping[kv[0]]+'%20'+kv[1]
                delim = '%2C'
        id_parts['rulesetid'] = reference_parts['bwbid'].upper()
        if 'date' not in id_parts:
            id_parts['date'] = datetime.now().strftime('%Y-%m-%d')
        if 'index' not in id_parts:
            id_parts['index'] = 'latest'
        return path+id_format.format_map(id_parts)+'%2C'+locstr_path
