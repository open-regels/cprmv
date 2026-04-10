 # Changelog CPRMV / CPRMV API  
  
This changelog is going to be maintained starting from CPRMV / CPRMV API v0.4.0.   
Usage of earlier versions is deprecated and at own risk.   
Note that CPRMV / CPRMV API still is highly subjected to change.   

**v0.4.1 CPRMV API**
- **extends the implementation of the /ref endpoint (partly) supports juriconnect, ELI (to EU CELLAR), CPRMV API /rules endpoint and experimental ELI style for NL references** 
- **Bugfix of internal server error when invalid arguments were included in a juriconnect reference** 
- **Adds a helper /cellar-by-eli endpoint, works analogous to /cellar-by-celex, but accepts ELI references (though it only matches ELI references that are explicitly linked to documents in the EU CELLAR knowledge graph, so for instance partial ELI references won't work)** 
- **Fixes a quote escaping bug for certain BWB resources** 
- **Updates the class diagram in the respec documentation to only have rectangular edges as provided through the Elk layout engine in plantuml instead of what Graphviz provides**
- **The /rules endpoint always returns a RuleSet with at least a Rule that is part of it. So also when selecting a specific subrule. This makes that certain properties tied to the RuleSet entity are always bundled**
- **The ruleset instance the /rules endpoint returns is placed in the cprmv.open-regels.nl / operaton.open-regels.nl namespace instead of the opencatalogi.open-regels.nl namespace.**
- **The /rules endpoint automatically adds a cprmv:isBasedOn property to the BWB,CVDR,FMX4 and DMN RuleSet's that refers to the original source the CPRMV API retrieves. Note that RuleSets can have multiple isBasedOn relations. A DMN RuleSet retrieved from the CPRMV API in the future could refer to both the DMN in the Operaton as well as the RuleSet (for instance a BWB document) the DMN is based on. Best is when the formalised RuleSet would include this cprmv metadata itself.**
- **The /rules endpoint now applies the optional unformatting of the definition of the first selected Rule before serializing to a requested format. Before 0.4.1 the unformat feature was only usable when the cprmv-json format was requested. Now it is also possible to do this with rdflib's 'n3' as a format for instance.**
- **The /rules endpoint now transforms and dumps json in UTF-8 encoding**
- **The possibility to retrieve DMN files is now documented with the /rules endpoint swagger docs**
   
**v0.4.0 CPRMV**  
-  **More elaborated and updated RDFS/OWL/SHACL specification of CPRMV. Adds several new classes like types of methods. Adds start for alignment with ELI.**  
-  **Changes the official cprmv URI to one that resolves to the respective documentation**  
-  **Normative section generated from RDFS/OWL/SHACL in the ReSpec documentation**  
-  **Generated class diagram in  ReSpec documentation**  
  
**v0.4.0 CPRMV API**  
-  **bugfixes around support for BWB schema (now supports circulaire’s)**  
-  **Adds /respec section hosting the respec documentation (besides the official URI) **  
-  **Adds /ref endpoint which is going to support all reference methods (but currently only implements juriconnect at a basic level)**  
-  **Allows for retrieving DMN 1.3 rulesets published in acknowledged (in value list in cprmvmethods.ttl) Operaton servers (currently only [operaton.open-regels.nl](http://operaton.open-regels.nl))**  
  

