# Roadmap CPRMV / CPRMV API  
  
Note: this roadmap can change at any moment without prior notice  
  
**v0.4.2 CPRMV**  
-  **Examples and link to RDF definitions in the ReSpec documentation and makes URI's resove to RDF instead of the ReSpec documentation to be referred from the RDF information**  
-  **Improved and more complete cprmv methods knowledge / value lists**  
-  **Better defined relation with with official organisation registers (EU)**  
-  **Start of a CPRMV-NL variant, based on MIM and CPSV-NL and the ROO**  
-  **Adds acknowledgement of RegelSpraak as a FormalisationMethod and ALEF as tooling related to it**
-  **Adds acknowledgement of OpenFisca as a FormalisationMethod and tooling related to it**
  
**v0.4.2 CPRMV API**  
-  **Support for using the /rules endpoint to find multiple published ruleset’s, which is a modus separate from referencing a single published ruleset. In the case of multiple ruleset’s the CPRMV API returns a list with references RuleSets which can be used with the CPRMV API to retrieve them.**  
-  **Support for utilizing organisation and product and services catalog information within references in the /rules endpoint. **  
-  **Support for utilizing :isBasedOn relations within references in the /rules endpoint. It should be possible to refer to.**  
-  **Support for using ELI and where possible juriconnect references for other publication methods than typically supported by these reference types.**  
-  **Adds a /browser section offering a minimal viable web based GUI to browse organisations, services and rulesets. Offers a searchable tree control at the left and a resource viewer at the right from which should offer users to start processes related to the resources (as defined by services)  **  
-  **Adds user friendly access to method knowledge in the /browser section relating to defined services for governance on value lists**
-  **adds basic support for RegelSpraak sources (depending on where these will get published)**

**0.4.3 CPRMV**
-  **Support for Dutch parliamentary documents that are officially published**
-  **Adds example of a fully traceable piece of law, from parliament to execution of formalised rules (Article 7a of the Dutch Old Age Pension law)**

**0.4.3 CPRMV API**
- **Adds example of a fully traceable piece of law, from parliament to execution of formalised rules (Article 7a of the Dutch Old Age Pension law)**
- **Adds a caching feaure to the CPRMV API. RuleSets requested for can be cached and fetched from this cache. One can request recaching a RuleSet**
- **Adds the possibility to determin a need for recaching so new versions are automatically fetched and chached when there are new versions of a RuleSet (if the request is not already specifically requesting a specific version in time).**
- **Adds some easy caching settings with which memory/disk usage can be controlled**
- **Adds the use of CPRMV API as publishing node from which RuleSets in a backoffice can be retrieved through the CPRMV API. The CPRMV API then automatically can be registered as a publication respository in relation toa organisation for which the API is hosted and gives access to RuleSets of (the organisation is held to be the competent authority of these RuleSets)**
