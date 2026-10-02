from core_web import core_web
from dmn13 import dmn13
from utils.constants import CPRMVSERVE

class operaton(core_web, dmn13):
    def interpret_rulesetid(self, rulesetid):
        print(f"Hello from module Operaton: {rulesetid}")
        deploymentid = ''
        resourceid = ''
        operatonids = rulesetid.split('R')
        print(len(operatonids))
        if len(operatonids) == 2:
            deploymentid = operatonids[0]
            resourceid = operatonids[1]
        return deploymentid, resourceid

    def interpret_publication(self, publication):
        deploymentid, resourceid = self.interpret_rulesetid(publication[CPRMVSERVE['id_parts']]['rulesetid'])
        publication[CPRMVSERVE['id_parts']]['deploymentid'] = deploymentid
        publication[CPRMVSERVE['id_parts']]['resourceid'] = resourceid
        return publication
