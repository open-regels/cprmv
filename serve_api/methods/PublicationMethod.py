from datetime import datetime
from parse import parse
from RuleMethod import RuleMethod
from utils.constants import CPRMV, CPRMVSERVE
from rdflib.namespace import RDF
import os

# publication method implementations must override / define the (abstract) methods in this class
class PublicationMethod(RuleMethod):

    def __init__(self, app, method_config):
        super().__init__(app, method_config)
        self.service_register = None
        self.organisation_register = None
        cprmvMethods = self.app.cprmvsettings["CPRMVMETHODS_KG"]
        reg = cprmvMethods.value(self.config, CPRMVSERVE["utilizes"])
        if (reg, RDF.type, CPRMV.ServiceRegister) in cprmvMethods:
            print(f"{self.config} utilizes service register method: {reg}")
            self.service_register = reg
        elif (reg, RDF.type, CPRMV.OrganisationRegister) in cprmvMethods:
            print(f"{self.config} utilizes organisation register method: {reg}")
            self.organisation_register = reg

    def valid_date(self, datestr):
        try:
            datetime.fromisoformat(datestr)
        except:
            return False
        return True

    # method to support different ruleset id formats by transforming them to a "normalized" one
    #
    # PUBLICATIONID_DATE_INDEX normalizes to PUBLICATIONID_PUBLICATIONDATE_INDEX (specific nth version that was published on the given date where n=INDEX)
    # PUBLICATIONID normalizes to PUBLICATIONID_now_latest (the version in effect today)
    # PUBLICATIONID_INDEX normalizes to PUBLICATIONID_na_INDEX (the specific nth version that was published where n=INDEX) ... this format is used with CVDR .. the 'na' as date means not applicable
    # PUBLICATIONID_DATE_ASSEENONDATE normalizes to PUBLICATIONID_DATE_ASSEENONDATE (the version in effect on the given DATE as was the case on date ASSEENONDATE)
    #
    def normalize_ruleset_id(self, rulesetid):
        print("normalizing id: "+rulesetid)
        if rulesetid.find('_') < 0:
            rulesetid = rulesetid+'_now_latest'
        splitted = rulesetid.split('_')
        if len(splitted) == 2:
            rulesetid = splitted[0]+'_na_'+splitted[1]
        print("normalizedid: "+rulesetid)
        return rulesetid

    def interpret_publication(self, publication):
        return publication

    def interpret_publication_id(self, publication_id):
        cprmvMethods = self.app.cprmvsettings["CPRMVMETHODS_KG"]
        idformat = cprmvMethods.value(self.config, CPRMVSERVE["publication-id-format"])
        normalized_idformat = cprmvMethods.value(self.config, CPRMVSERVE["normalized-id-format"])
        if idformat is not None and normalized_idformat is not None:
            cprmvid_official = publication_id
            print(f"interpreting publication id: {publication_id}")
            cprmvid_normalized = self.normalize_ruleset_id(publication_id)
            print(f"Parsing {normalized_idformat} on value {cprmvid_normalized}")
            result = parse(normalized_idformat, cprmvid_normalized)
            if result is not None:
                publication = {}
                publication[CPRMVSERVE['id_parts']] = result.named
                if 'index' in publication[CPRMVSERVE['id_parts']] and publication[CPRMVSERVE['id_parts']]['index'] == 'latest':
                    if 'date' in publication[CPRMVSERVE['id_parts']] and self.valid_date(publication[CPRMVSERVE['id_parts']]['date']):
                        publication[CPRMVSERVE['id_parts']]['valid-on'] = publication[CPRMVSERVE['id_parts']]['date']
                    else:
                        publication[CPRMVSERVE['id_parts']]['valid-on'] = datetime.now().strftime('%Y-%m-%d')
                    print(f"searching latest version valid on date: {publication[CPRMVSERVE['id_parts']]['valid-on']}")
                    # note the following call is publication method dependent
                    version = self.find_publication_version_valid_on_date(publication)
                    publication[CPRMVSERVE['id_parts']]['date'] = version['date']
                    publication[CPRMVSERVE['id_parts']]['index'] = version['index']
                    cprmvid_official = idformat.format_map(publication[CPRMVSERVE['id_parts']])
                publication[CPRMVSERVE['id_parts']]['cprmvid'] = cprmvid_official
                return self.interpret_publication(publication)
        return None

    # Finds the publication date and index of the publication on that date and which was in effect on a given date
    # as could have been seen on a given second date which defaults to today, ignoring publications that possibly
    # were published lateron to become in effect in the past.
    # NOTE This functionality might not make sense for all publication methods in the end, but for the currently
    # supported ones it does.
    def find_publication_version_valid_on_date(self, publication, as_seen_on=datetime.now().strftime('%Y-%m-%d')):
        # method = self.config
        found_date = publication[CPRMVSERVE['id_parts']]['valid-on']
        found_index = 1
        return {"date" : found_date, "index" : found_index}

    # retrieve the path to a single raw publication file (the publication exactly as published)
    def get_raw_publication(self, publication):
        return ""

    # load the given raw publication (path to a file) into the given graph as cprmv knowledge
    # def get_cprmv_rule_set_from_raw_publication(self, g, raw, publication):
    #    return

    # load the publication into the given graph as cprmv knowledge (and clean up resources)
    def get_cprmv_rule_set_from_publication(self, g, publication):
        raw = self.get_raw_publication(publication)
        self.get_cprmv_rule_set_from_raw_publication(g, raw, publication)
        # todo improve resource management
        os.remove(raw)
