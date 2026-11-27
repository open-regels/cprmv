from datetime import datetime
from core_web import core_web
import ciso8601
import shutil
from urllib.request import Request, urlopen
from urllib.error import URLError
import tempfile
from lxml import etree
from parse import parse
from utils.constants import CPRMV, CPRMVSERVE
from rdflib import Namespace
import os

FRBR_SRU = Namespace("https://cprmv.open-regels.nl/0.4.3/methods/frbr-sru/")

class frbr_sru(core_web):

    def valid_date(self, datestr):
        try:
            datetime.fromisoformat(datestr)
        except:
            return False
        return True

    # as_seen_on (zichtdatum) argument not implemented. Always defaults to default used in SRU service which is "today" ..
    # only implemented for AnalysisMethods, not the non-FRBR methods
    def find_publication_version_valid_on_date(self, publication, as_seen_on=datetime.now().strftime('%Y-%m-%d')):
        date = str(publication[CPRMVSERVE['id_parts']]['valid-on'])
        print(f"OK date {date}")
        cprmvMethods = self.app.cprmvsettings["CPRMVMETHODS_KG"]
        for p, o in cprmvMethods.predicate_objects(self.config):
            print(f"frbr-sru config: {p},{o}")
        date_ts = ciso8601.parse_datetime(date)
        frbr_sru_url_format = str(cprmvMethods.value(self.config, FRBR_SRU["url"]))
        frbr_valid_from_term_ns = str(cprmvMethods.value(self.config, FRBR_SRU["response-from-date-term-namespace"]))
        frbr_valid_from_term = str(cprmvMethods.value(self.config, FRBR_SRU["response-from-date-term"]))
        fvft_prefix = 'fvft'
        #print("OK")
        frbr_valid_from_xpath = '//'+fvft_prefix+':'+frbr_valid_from_term
        frbr_sru_response_publoc_term_ns = str(cprmvMethods.value(self.config, FRBR_SRU["response-publication-location-term-namespace"]))
        frbr_sru_response_publoc_term = str(cprmvMethods.value(self.config, FRBR_SRU["response-publication-location-term"]))
        fsrpt_prefix = 'fsrpt'
        #print("OKOK")
        frbr_publoc_format = str(cprmvMethods.value(self.config, CPRMVSERVE["repository-publication-location-format"]))
        #print(f"test: {frbr_sru_response_publoc_term}")
        frbr_publoc_xpath = '//'+fsrpt_prefix+':'+frbr_sru_response_publoc_term
        sru_url = frbr_sru_url_format.format_map(publication[CPRMVSERVE['id_parts']])
        #print("OKOK3")
        methodLabel = cprmvMethods.value(self.config, CPRMV.label)
        #print("OKOKOK")
        try:
            print(f"retrieving versioning information through SRU service: {sru_url}")
            req = Request(sru_url)
            # sru_url comes from frbr-sru:url in data/cprmvmethods.ttl, which ships in the
            # image: a literal https://zoekservice.overheid.nl/ prefix whose query
            # placeholders the request fills, so it cannot change the scheme or the host.
            # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            response = urlopen(req, context=self.app.SSL_CONTEXT)
            print("Saving response from SRU")
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                shutil.copyfileobj(response, tmp_file)
                tmp_file.close()
                print(f"opening publication versioning information from temp file {tmp_file.name}")
                try:
                    xml = etree.parse(open(tmp_file.name))
                except Exception as e:
                    print('Exception parsing sru response: '+str(e))
                    raise Exception(f"error parsing retrieved publication versioning information.")
                print("succesfull parse of sru response")
                try:
                    found_date = 'unknown'
                    found_index = 'unknown'
                    for expr in xml.xpath(frbr_valid_from_xpath, namespaces={fvft_prefix : frbr_valid_from_term_ns}):
                        found_date = expr.text
                        if not self.valid_date(found_date):
                            print("invalid publication valid-from date found: "+found_date)
                            raise Exception('SRU response contained invalid publication valid-from date.')
                        break
                    print('publication valid-from date found: '+found_date)
                    for expr in xml.xpath(frbr_publoc_xpath, namespaces={fsrpt_prefix : frbr_sru_response_publoc_term_ns}):
                        publoc = expr.text
                        print(f"Parsing (frbr) repository-publication-location-format ({frbr_publoc_format}) on value from SRU response: {publoc}")
                        result = parse(frbr_publoc_format, publoc)
                        if result is not None:
                            parts = result.named
                            if 'index' in parts:
                                found_index = parts['index']
                            else:
                                raise Exception('Error parsing (frbr) repository-publication-location-format. No index value configured or found...')
                            print(f"found publication index: "+found_index)
                        else:
                            raise Exception('SRU response contained unexpected publication location url.')
                        break
                    print('Processed SRU response. valid-from date and index found')
                except Exception as e:
                    print("Exception processing SRU response: "+str(e))
                    raise Exception(f'error processing retrieved publication versioning information..'+str(e))
                print(f"latest version found: {found_date}_{found_index}")
                os.remove(tmp_file.name)
                return {"date" : found_date, "index" : found_index}
        except URLError as e:
            if hasattr(e, "reason"):
                print("We failed to reach a server.")
                print("Reason: ", e.reason)
                raise e
            elif hasattr(e, "code"):
                print("The server couldn't fulfill the request.")
                print("Error code: ", e.code)
                raise e
        except Exception as e:
            print("Error finding publication versioning information: "+str(e))
            raise e
        raise Exception(f"unknown error finding publication versioning information...")
