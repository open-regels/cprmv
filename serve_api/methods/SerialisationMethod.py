from RuleMethod import RuleMethod

# serialisation method implementations must define the abstract methods in this class
class SerialisationMethod(RuleMethod):
    # adds the publication as cprmv information to the given RDFlib graph
    def get_cprmv_rule_set_from_raw_publication(self, g):
        return g
