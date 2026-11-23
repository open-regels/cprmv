# Roadmap CPRMV / CPRMV API  

Note: this roadmap can change at any moment without prior notice  

Expected by 21 December 2026:

**0.4.4 CPRMV**
- **To simplify the vocabulary and make it more flexible, the Echelons and RuleMethods will become soft typed using a type property.**
- **Add support for governance layering of CPRMV method configuration, allowing for method configuration at a local, national, eu and worldwide level**
- **Add acknowledgement of methods not yet in the CPRMV standard but contained in the inventory: https://legal-technology-09ea24.gitlab.io/typologie.html, translated to english**
- **Adds acknowledgement of PNA Group's iKnow as a AnalysisMethod (mainly as tooling) from which DMN's can be exported**
- **Improvement of DMN13 method to interpret DMN knowledgesource information as cprmv:isBasedOn references**
- **Improvement of Operaton method to reference rulesets more easily on name then using references that contain two long reference id's that can not easily be found**
- **Add acknowledgement of more methods**

**0.4.4 CPRMVAPI**
- **Adds that the API properly and always references to a service (which can be an unknown however) but with always the right competent authority (for all supported methods).**
- **Support for utilizing organisation and product and services catalog information within references in the /rules endpoint.**
- **While the CPRMV-API will soft type RuleMethods, in the CPRMV API different types of RuleMethods will keep their own class implementation**
- **Add support of more methods like Catala, RegelSpraak, OpemFisca, LegiFrance, MC/DC**
- **Support for automatically determin :isBasedOn relations using ref2link**
- **Support for utilizing :isBasedOn relations within references in the /rules endpoint. It should be possible to refer to all rulesets based on a given ruleset and vice versa.**
- **Support for utilizing organisation and product and services catalog information within references in the /rules endpoint.** 

Expected Q1 2027:

**0.4.5 CPRMV**
-  **Support for Dutch parliamentary documents that are officially published and the linkage of rulesets that relate to them using the :isBasedOn relation**
-  **Adds example of a fully traceable piece of law, from parliament  to execution of formalised rules (Article 7a of the Dutch Old Age Pension law)**
-  **Adds example of a fully traceable piece of law, from parliament to execution of formalised rules (Home Battery Subsidy Flevoland)**
-  **Adds example of a fully traceable piece of law, from parliament to execution of formalised rules (Normenbrief)**
-  **Adds example of a fully traceable piece of law, from parliament to execution of formalised rules (a selected service basd on a single STTR published in the DSO)**

**0.4.5 CPRMV API**
- **Support for Dutch parliamentary documents that are officially published and the linkage of rulesets that relate to them using the :isBasedOn relation**
- **Adds a caching feaure to the CPRMV API. RuleSets requested for can be cached and fetched from this cache. One can request recaching a RuleSet**
- **Adds the possibility to determin a need for recaching so new versions are automatically fetched and chached when there are new versions of a RuleSet (if the request is not already specifically requesting a specific version in time).**
- **Adds some easy caching settings with which memory/disk usage can be controlled**
- **Adds the use of CPRMV API as publishing node from which RuleSets in a backoffice can be retrieved through the CPRMV API. The CPRMV API then automatically can be registered as a publication respository in relation to a single organisation for which the API is hosted and gives access to RuleSets of (the organisation is held to be the competent authority of these RuleSets)**
- **Adds supports of signing the Rulesets using a key tied to the competent authority so it's authenticity can be validated when the CPRMV API is used as publishing node**
- **Improves security**
