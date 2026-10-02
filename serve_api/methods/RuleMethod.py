
# abstract base class for all methods
class RuleMethod:
    # the constructor is given the reference to the method definition node within the CPRMV standard
    # knowledge graph the API loads and self.config can be used in inherited methods as how it gets passed to child class instances
    def __init__(self, app, method_config):
        self.app = app
        self.config = method_config
