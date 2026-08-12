from ReferenceMethod import ReferenceMethod

class elifmx4(ReferenceMethod):
    # Also note this method seems specific to ELI in CELLAR context
    def transform_reference(reference):
        result = None
        language='NLD'
        format='fmx4'
        cellarurl = f"https://publications.europa.eu/webapi/rdf/sparql?default-graph-uri=&query=prefix+cdm%3A+%3Chttp%3A%2F%2Fpublications.europa.eu%2Fontology%2Fcdm%23%3E+%0D%0Aprefix+purl%3A+%3Chttp%3A%2F%2Fpurl.org%2Fdc%2Felements%2F1.1%2F%3E+%0D%0Aselect+distinct+%3Fitem%0D%0Awhere+%7B%0D%0A%3Fwork+cdm%3Aresource_legal_eli+%22{reference}%22%5E%5E%3Chttp%3A%2F%2Fwww.w3.org%2F2001%2FXMLSchema%23anyURI%3E+.%0D%0A%3Fexpr+cdm%3Aexpression_belongs_to_work+%3Fwork+%3B%0D%0Acdm%3Aexpression_uses_language+%3Flang+.%0D%0A%3Flang+purl%3Aidentifier+%3FlangCode+.%0D%0A%3Fmanif+cdm%3Amanifestation_manifests_expression+%3Fexpr%3B%0D%0Acdm%3Amanifestation_type+%3Fformat.%0D%0A%3Fitem+cdm%3Aitem_belongs_to_manifestation+%3Fmanif.%0D%0AFILTER%28str%28%3FlangCode%29%3D%22{language}%22+%26%26+str%28%3Fformat%29%3D%22{format}%22%29%0D%0A%7D+LIMIT+100&format=application%2Fjson&timeout=0&debug=on&run=+Run+Query+"
        print(f"querying EU CELLAR: {cellarurl}")
        with urlopen(cellarurl, context=SSL_CONTEXT) as response:
            data = response.read().decode('utf-8')
            json_data = json.loads(data)
            print(json_data)
            if 'results' in json_data and 'bindings' in json_data['results'] and len(json_data['results']['bindings']) > 0 and 'item' in json_data['results']['bindings'][0] and 'value' in json_data['results']['bindings'][0]['item']:
                result = json_data['results']['bindings'][0]['item']['value']
        return result

class elinl(ReferenceMethod):
    pass
