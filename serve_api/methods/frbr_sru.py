from datetime import datetime
from core_web import core_web

class frbr_sru(core_web):

    def valid_date(self, datestr):
        try:
            datetime.fromisoformat(datestr)
        except:
            return False
        return True

    # as_seen_on (zichtdatum) argument not implemented. Always defaults to default used in SRU service which is "today" ..
    # only implemented for AnalysisMethods, not the non-FRBR methods
    def find_publication_version_valid_on_date(date, as_seen_on=datetime.now().strftime('%Y-%m-%d')):
        date_ts = ciso8601.parse_datetime(date)
        frbr_sru_url_format = str(method[CPRMVSERVE["frbr-repository-sru-url"]])
        frbr_valid_from_term_ns = str(method[CPRMVSERVE["frbr-repository-sru-response-from-date-term-namespace"]])
        frbr_valid_from_term = str(method[CPRMVSERVE["frbr-repository-sru-response-from-date-term"]])
        fvft_prefix = 'fvft'
        frbr_valid_from_xpath = '//'+fvft_prefix+':'+frbr_valid_from_term
        frbr_sru_response_publoc_term_ns = str(method[CPRMVSERVE["frbr-repository-sru-response-publication-location-term-namespace"]])
        frbr_sru_response_publoc_term = str(method[CPRMVSERVE["frbr-repository-sru-response-publication-location-term"]])
        fsrpt_prefix = 'fsrpt'
        frbr_publoc_format = str(method[CPRMVSERVE["repository-publication-location-format"]])
        frbr_publoc_xpath = '//'+fsrpt_prefix+':'+frbr_sru_response_publoc_term
        sru_url = frbr_sru_url_format.format_map(method[CPRMVSERVE["id_parts"]])
        methodLabel = method[CPRMV.label]
        try:
            print(f"retrieving versioning information through SRU service: {sru_url}")
            req = Request(sru_url)
            response = urlopen(req, context=SSL_CONTEXT)
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
                                raise Exception('Error parsing frbr-repository-publication-location-format. No index value configured or found...')
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
