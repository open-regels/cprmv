from RuleMethod import RuleMethod
from utils.constants import CPRMVSERVE
from parse import parse

# reference method implementations must define the abstract methods in this class
class ReferenceMethod(RuleMethod):
    def parse_reference(self, reference):
        cprmvMethods = self.app.cprmvsettings["CPRMVMETHODS_KG"]
        referenceformat = str(cprmvMethods.value(self.config , CPRMVSERVE["reference-format"]))
        print('Parsing '+reference+' on format '+referenceformat)
        return parse(referenceformat, reference)

    # transforms a reference string that can be unformatted into reference parts into
    # a reference that can be used with the CPRMV API
    # (this default implementation is also inherited in the cprmvapi reference method)
    def transform_reference(self, reference):
        reference_parts = self.parse_reference(reference)
        if reference_parts is not None:
            path = reference_parts['path'].replace('/',', ')
            return '/rules/'+path
        return None
