# Roadmap CPRMV / CPRMV API  

Note: this roadmap can change at any moment without prior notice  

Expected by end of September 2026:
  
**v0.4.2 CPRMV**  
-  **Adds acknowledgement of STTR as a formalisationmethod (relating to DSO)**
-  **Adds acknowledgement of Normenbrief as a formalisation- and publicationmethod**
  
**v0.4.2 CPRMV API**  
-  **respec documentation also includes information on methods (the cprmvmethods namespace)**
-  **Adds that the API properly and always references to a service (which can be an unknown however) but with always the right competent authority.**
-  **Support for using the /rules endpoint to find multiple published ruleset’s, which is a modus separate from referencing a single published ruleset. In the case of multiple ruleset’s the CPRMV API returns a list with references RuleSets which can be used with the CPRMV API to retrieve them.**
-  **Support for utilizing organisation and product and services catalog information within references in the /rules endpoint.** 

Expected by 15 November 2026:

**0.4.3 CPRMV**
-  **Improvement on relation with FRBR ans ELI: a RuleSet can both be seen as a frbr Work as well as an frbr Expression. Currently it is defined as a frbr:F1_Work (similar as eli:legalResource), but also Expressions thereof can form RuleSets with similar properties as that of RuleSet's as Work.
-  **Support for Dutch parliamentary documents that are officially published and the linkage of rulesets that relate to them using the :isBasedOn relation**
-  **Adds example of a fully traceable piece of law, from parliament  to execution of formalised rules (Article 7a of the Dutch Old Age Pension law)**
-  **Adds example of a fully traceable piece of law, from parliament to execution of formalised rules (Home Battery Subsidy Flevoland)**
-  **Adds example of a fully traceable piece of law, from parliament to execution of formalised rules (Normenbrief)**
-  **Adds example of a fully traceable piece of law, from parliament to execution of formalised rules (a selected service basd on a single STTR published in the DSO)**
-  **Examples and link to RDF definitions in the ReSpec documentation**  
-  **Adds acknowledgement of PNA Group's iKnow as a AnalysisMethod (mainly as tooling) from which DMN's can be exported**
-  **Improvement of DMN13 method to interpret DMN knowledgesource information as cprmv:isBasedOn references**
-  **Improvement of Operaton method to reference rulesets more easily on name then using references that contain two long reference id's that can not easily be found**

**0.4.3 CPRMV API**
-  **Adds basic support for DSO as source for STTR rulesets**
-  **Adds basic support for MC/DC as test method**
-  **Adds basic support for RegelSpraak sources (depending on where these will get published)**
-  **Adds basic support for retrieving testsets for MC/DC as testmethod (irt DMN)**
-  **Adds basic support for Legifrance as publicationmethod**
-  **Adds basic support for Catala sources (depending on where these will get published)**
-  **Adds basic support for OpenFisca sources (depending on where these will get published)**
-  **Support for automatically determin :isBasedOn relations using ref2link**
-  **Support for utilizing :isBasedOn relations within references in the /rules endpoint. It should be possible to refer to all rulesets based on a given ruleset and vice versa.**

Expected by 21 December 2026:

**0.4.4 CPRMV**
-  **Improvements in the specification of desciptions and naming of concepts after feedback from several expert communities (SEMIC, NORA, Opschalingstickets 2026, ...)**

**0.4.4 CPRMV API**
- **Adds a caching feaure to the CPRMV API. RuleSets requested for can be cached and fetched from this cache. One can request recaching a RuleSet**
- **Adds the possibility to determin a need for recaching so new versions are automatically fetched and chached when there are new versions of a RuleSet (if the request is not already specifically requesting a specific version in time).**
- **Adds some easy caching settings with which memory/disk usage can be controlled**
- **Adds the use of CPRMV API as publishing node from which RuleSets in a backoffice can be retrieved through the CPRMV API. The CPRMV API then automatically can be registered as a publication respository in relation to a single organisation for which the API is hosted and gives access to RuleSets of (the organisation is held to be the competent authority of these RuleSets)**
- **Adds supports of signing the Rulesets using a key tied to the competent authority so it's authenticity can be validated when the CPRMV API is used as publishing node**
- **Improves security**
