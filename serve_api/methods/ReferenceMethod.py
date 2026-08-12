from RuleMethod import RuleMethod

# reference method implementations must define the abstract methods in this class
class ReferenceMethod(RuleMethod):
    def parse_reference(reference):
        cprmvMethods = app.cprmvsettings["CPRMVMETHODS_KG"]
        referenceformat = str(cprmvMethods.value(self.config , CPRMVSERVE["reference-format"]))
        print('Parsing '+reference+' on format '+referenceformat)
        return parse(referenceformat, reference)

    # transforms a reference string that can be unformatted into reference parts into
    # a reference that can be used with the CPRMV API
    # (this default implementation is used in the cprmvapi reference method)
    def transform_reference(reference):
        reference_parts = parse_reference(reference)
        path = reference_parts['path'].replace('/',', ')
        return '/rules/'+path
