 # Changelog CPRMV / CPRMV API  
  
This changelog is going to be maintained starting from CPRMV / CPRMV API v0.4.0.   
Usage of earlier versions is deprecated and at own risk.   
Note that CPRMV / CPRMV API still is highly subjected to change.   

**v0.4.1 CPRMV API**
- ** extends the implementation of the /ref endpoint (partly) supports juriconnect, ELI (to EU CELLAR), CPRMV API /rules endpoint and experimental ELI style for NL references
- ** Bugfix of internal server error when invalid arguments were included in a juriconnect reference
- ** Adds a helper /cellar-by-eli endpoint, works analogous to /cellar-by-celex, but accepts ELI references (though it only matches ELI references that are explicitly linked to documents in the EU CELLAR knowledge graph, so for instance partial ELI references won't work)
- ** Fixes a quote escaping bug for certain BWB resources
   
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
  

