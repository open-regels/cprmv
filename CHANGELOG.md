 # Changelog CPRMV / CPRMV API  
  
This changelog is going to be maintained starting from CPRMV / CPRMV API v0.4.0.   
Usage of earlier versions is deprecated and at own risk.   
Note that CPRMV / CPRMV API still is highly subjected to change.   


**v0.4.2 CPRMV**  
- **updates URI's and documentation to mention 0.4.2 instead of 0.4.1**
- **adds improved compatibility : the SHACL shapes now do not include a recursive definition**
- **makes the output of the API validate against the cprmv SHACL shapes, which failed due to compatibility problems, but also the DMN and FMX4 methods are now made conformant (using dummy properties for the moment though)**
- **updates tests for the API output against SHACL shapes (tests in the rdf folder)** 
- **improves the npm run build script in the full-package.json to create folders if they do not exist**
- **removes old deprecated project folders: /example and /tools**

**v0.4.2 CPRMV API**
- **Updates URI's and documentation to mention 0.4.2 instead of 0.4.1**
- **removes some old deprecated project files** 

**v0.4.1 CPRMV**  
- **Updates URI's and documentation to mention 0.4.1 instead of 0.4.0**
- **The CPRMV now defines a RuleSet to be a subclass of FRBR Work (frbroo:F1_Work) instead of an eli:LegalResource as Formalisations like business rules are not to be seen as legal resources in the context of ELI up until further notice. Note that eli:LegalResources are defined as a subclass of FRBR Work too.**
- **The CPRMV now defines the isBasedOn relation as a subProperty of frbroo:R2_is_derivative_of instead of eli:based_on. It still is also defined to be a subProperty of prov:wasDerivedFrom**
- **Documentation on properties in the ReSpec documentation**  
- **Updates the class diagram in the respec documentation to only have rectangular edges as provided through the Elk layout engine in plantuml instead of what Graphviz provides**
- **Fixes publication paths in respec document**
- **Adds PDF version of the respec (as is using pandoc, manually build and committed in the repository)**
- **updates full-package.json that also generates the pdf and runs shaclgen on top of what the normal package.json does**
- **a npm run build now also updates the files in the respec folders of the CPRMV API**

**v0.4.1 CPRMV API**
- **Updates URI's and documentation to mention 0.4.1 instead of 0.4.0**
- **extends the implementation of the /ref endpoint (partly) supports juriconnect, ELI (to EU CELLAR), CPRMV API /rules endpoint and experimental ELI style for NL references** 
- **Bugfix of internal server error when invalid arguments were included in a juriconnect reference** 
- **/cellar-by-celex endpoint : redirects to the output of CELLAR instead of giving the user a URL to CELLAR**
- **Adds a helper /cellar-by-eli endpoint, works analogous to /cellar-by-celex, but accepts ELI references (though it only matches ELI references that are explicitly linked to documents in the EU CELLAR knowledge graph, so for instance partial ELI references won't work)** 
- **Fixes a quote escaping bug for certain BWB resources** 
- **The /rules endpoint always returns a RuleSet with at least a Rule that is part of it. So also when selecting a specific subrule. This makes that certain properties tied to the RuleSet entity are always bundled**
- **The ruleset instance the /rules endpoint returns is placed in the cprmv.open-regels.nl / operaton.open-regels.nl namespace instead of the opencatalogi.open-regels.nl namespace.**
- **The /rules endpoint automatically adds a cprmv:isBasedOn property to the BWB,CVDR,FMX4 and DMN RuleSet's that refers to the original source the CPRMV API retrieves. Note that RuleSets can have multiple isBasedOn relations. A DMN RuleSet retrieved from the CPRMV API in the future could refer to both the DMN in the Operaton as well as the RuleSet (for instance a BWB document) the DMN is based on. Best is when the formalised RuleSet would include this cprmv metadata itself.**
- **The /rules endpoint now applies the optional unformatting of the definition of the first selected Rule before serializing to a requested format. Before 0.4.1 the unformat feature was only usable when the cprmv-json format was requested. Now it is also possible to do this with rdflib's 'n3' as a format for instance.**
- **The /rules endpoint now transforms and dumps json in UTF-8 encoding**
- **The possibility to retrieve DMN files is now documented with the /rules endpoint swagger docs**
- **Adds (basic) support for using the CPRMV API as MCP server (/mcp endpoint)**
   
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
  

