# Roadmap CPRMV / CPRMV API  
  
Note: this roadmap can change at any moment without prior notice  
  
**v0.4.1 CPRMV**  
-  **Documentation on properties in the ReSpec documentation**  
-  **Improved class diagram layout in the ReSpec documentation**  
-  **Examples and link to RDF definitions in the ReSpec documentation**   
  
**v0.4.1 CPRMV API**  
-  **/cellar-by-celex endpoint : redirects to the output of CELLAR instead of giving the user a URL to CELLAR**  
-  **/cellar-by-eli endpoint : new variant of /cellar-by-celex which accepts a full ELI URI as argument. Also redirecting to output of CELLAR.**  
-  **/ref endpoint : new version which accepts supported types of references, currently being ELI and Juriconnect but also an experimental ELI for BWB/CVDR reference and CPRMV API /rules endpoint references.. For the CPRMV API style reference one can also just use the /rules endpoint of course**  
-  **Link to /respec section from within the /docs section**  
-  **The /rules endpoint allows for retrieving the raw unprocessed source (the whole ruleset, not transformed into a CPRMV ruleset if the source isn’t a CPRMV ruleset) **  
-  **The /rules endpoint adds isBasedOn property (relation) to RuleSet’s with an URI’s as value (This will be the link to [repository.overheid.nl](http://repository.overheid.nl) in case for BWB,CVDR, an ELI reference in case of Formex 4 (these are seen as root sources for now). In the case of DMN it is the URI to the Operaton server**
-  **Fix escaping of quotes and newlines in transformations to RDF, which up until 0.4.1 can cause some sources to fail to load**
-  **Improved and more complete support for BWB, CVDR, Formex 4 and DMN 1.3 standards through usage of the existing XML Schema’s independent from XSL stylesheets (CPRMV uses a generic single stylesheet for all XML based standards which are constrained through schema checking)**  
-  **Adds (basic) support for using the CPRMV API as MCP server**
  
**v0.4.2 CPRMV**  
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

**0.4.3 CPRMV API**
- **Adds a caching feaure to the CPRMV API. RuleSets requested for can be cached and fetched from this cache. One can request recaching a RuleSet**
- **Adds the possibility to determin a need for recaching so new versions are automatically fetched and chached when there are new versions of a RuleSet (if the request is not already specifically requesting a specific version in time).**
- **Adds some easy caching settings with which memory/disk usage can be controlled**
- **Adds the use of CPRMV API as publishing node from which RuleSets in a backoffice can be retrieved through the CPRMV API. The CPRMV API then automatically can be registered as a publication respository in relation toa organisation for which the API is hosted and gives access to RuleSets of (the organisation is held to be the competent authority of these RuleSets)**
