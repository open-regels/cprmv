
class cprmvapi:
    # NOTE this is cprmvapi as referencemethod specific and will have to move to corresponding method module
    def transform_cprmvapi_reference(method_config, reference_parts):
        path = reference_parts['path'].replace('/',', ')
        return '/rules/'+path
