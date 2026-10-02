# CPRMV Methods


## <dfn>rulemethods</dfn>
 Value list of acknowledged rule methods.


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |
| acknowledged |   | 0..1 | a list with RuleMethod's that are acknowledged as part of the rule methods value list. |
| | | | <a>OpenFisca</a> |
| | | | <a>Catala</a> |
| | | | <a>juriconnect</a> |
| | | | <a>cprmvapi</a> |
| | | | <a>corpus of RegelRecht Git Repository</a> |
| | | | <a>repository of the Normenbrief showcase</a> |
| | | | <a>DSO</a> |
| | | | <a>Operaton</a> |
| | | | <a>STTR</a> |
| | | | <a>DMN 1.3 on operaton.open-regels.nl (experimental)</a> |
| | | | <a>Formex v4 (EU)</a> |
| | | | <a>CVDR (NL)</a> |
| | | | <a>BWB (NL)</a> |
| | | | <a>flint</a> |
| | | | <a>jas</a> |
| | | | <a>alef-regelspraak</a> |



## <dfn>analysismethods</dfn>
 Value list of acknowledged analysis methods.


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |
| acknowledged |   | 0..1 | a list with RuleMethod's that are acknowledged as part of the rule methods value list. |
| | | | <a>Formex v4 (EU)</a> |
| | | | <a>CVDR (NL)</a> |
| | | | <a>BWB (NL)</a> |
| | | | <a>flint</a> |
| | | | <a>jas</a> |



## <dfn>formalisationmethods</dfn>
 Value list of acknowledged formalisation methods.


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |
| acknowledged |   | 0..1 | a list with RuleMethod's that are acknowledged as part of the rule methods value list. |
| | | | <a>OpenFisca</a> |
| | | | <a>Catala</a> |
| | | | <a>alef-regelspraak</a> |
| | | | <a>corpus of RegelRecht Git Repository</a> |
| | | | <a>repository of the Normenbrief showcase</a> |
| | | | <a>STTR</a> |
| | | | <a>DMN 1.3 on operaton.open-regels.nl (experimental)</a> |



## <dfn>serialisationmethods</dfn>
 Value list of acknowledged serialisation methods.


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |
| acknowledged |   | 0..1 | a list with RuleMethod's that are acknowledged as part of the rule methods value list. |
| | | | <a>corpus of RegelRecht Git Repository</a> |
| | | | <a>repository of the Normenbrief showcase</a> |
| | | | <a>STTR</a> |
| | | | <a>DMN 1.3 on operaton.open-regels.nl (experimental)</a> |
| | | | <a>Formex v4 (EU)</a> |
| | | | <a>CVDR (NL)</a> |
| | | | <a>BWB (NL)</a> |



## <dfn>codificationmethods</dfn>
 Value list of acknowledged codification methods.


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |
| acknowledged |   | 0..1 | a list with RuleMethod's that are acknowledged as part of the rule methods value list. |



## <dfn>testmethods</dfn>
 Value list of acknowledged test methods.


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |
| acknowledged |   | 0..1 | a list with RuleMethod's that are acknowledged as part of the rule methods value list. |



## <dfn>executionmethods</dfn>
 Value list of acknowledged execution methods.


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |
| acknowledged |   | 0..1 | a list with RuleMethod's that are acknowledged as part of the rule methods value list. |
| | | | <a>corpus of RegelRecht Git Repository</a> |
| | | | <a>Operaton</a> |



## <dfn>publicationmethods</dfn>
 Value list of acknowledged publication methods.


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |
| acknowledged |   | 0..1 | a list with RuleMethod's that are acknowledged as part of the rule methods value list. |
| | | | <a>corpus of RegelRecht Git Repository</a> |
| | | | <a>repository of the Normenbrief showcase</a> |
| | | | <a>DSO</a> |



## <dfn>referencemethods</dfn>
 Value list of acknowledged reference methods.


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |
| acknowledged |   | 0..1 | a list with RuleMethod's that are acknowledged as part of the rule methods value list. |
| | | | <a>juriconnect</a> |
| | | | <a>cprmvapi</a> |



## <dfn>alef-regelspraak</dfn>
 The alef-regelspraak method is a formalisation method that can be used within the ALEF IDE by the Dutch national tax authority.
It is to some extend analogous to RuleSpeak and defines a controlled Dutch natural language.



properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>BWB (NL)</dfn>
 The bwb method is the official analysis and serialisation method for legal rulesets defined by Dutch national government organisations focused on the structure and presentation thereof. It also specifies how to refer to rulesets using a BWB id which is to be used within the Juriconnect reference method. BWB is based on Akoma Ntoso and XML serialisation.



subclass of: <a>CPRMV API - Generic XML Serialisation Method</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>Catala</dfn>
 The catala method is a well known formalisation method originating in France. It typically uses Markdown to serialise formal rules expressed in the catala language along with explanatory content.



subclass of: <a>FormalisationMethod</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>cprmvapi</dfn>
 The cprmvidpath method is the CPRMV API's default reference method

This reference method is defined for support within API's that serve CPRMV metadated publications of which the CPRMV API is a reference implementation and therefor it is definied in the cprmv-serve namespace.



subclass of: <a>ReferenceMethod</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>CVDR (NL)</dfn>
 The cvdrmethod is the official analysis and serialisation method for legal rulesets defined by Dutch local governments focused on the structure and presentation thereof. It also specifies how to refer to rulesets using a CVDR id which is to be used within the Juriconnect reference method. CVDR is based on Akoma Ntoso and XML serialisation.



subclass of: <a>CPRMV API - Generic XML Serialisation Method</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>DMN 1.3 on operaton.open-regels.nl (experimental)</dfn>
 The DMN 1.3 method is a well known formalisation method by the OMG Group to express Decision Models. 
It typically uses XML as a serialisation format.



subclass of: <a>CPRMV API - Generic XML Serialisation Method</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>STTR</dfn>
 The STTR method is a formalisation method based on DMN used within the Dutch environment law domain (Digitaal Stelsel Omgevingswet (DSO)). See https://iplo.nl/digitaal-stelsel/aansluiten/standaarden/sttr-imtr/ for more information.



subclass of: <a>CPRMV API - Generic XML Serialisation Method</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>eli</dfn>
 The eli method is a well known reference method at EU level conforming to the ELI standard.



properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>eucellar</dfn>
 The eucellar method is a well known official publication method by the publication office of the EU for legal resources, for example represented in the form resulting from the Formex4 method.



properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>flint</dfn>
 The flint method is a analysis and formalisation method that focuses on norm engineering in which the expression of norms is developed in a methodical way such that legal rule expressions as well as formalized rule expressions are kept fully synchronised.



subclass of: <a>AnalysisMethod</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>Formex v4 (EU)</dfn>
 The fmx4 method is a well known analysis and serialisation method for, though mostly focused on the presentation of, legal ruleset's used by the EU's publication office. It typically serialises rules in a specific Akomo Ntoso compatible XML based format.



subclass of: <a>CPRMV API - Generic XML Serialisation Method</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>FRBR SRU</dfn>
 The frbr-sru method is a well known analysis and publication method focusing on the finding, identification, selection and retrieval of bibliographic information and its users through the FRBR vocabulary issued by IFLA (International Federation of Library Associations and Institutions) as well as the SRU (Search/Retrieve via URL) open web protocol created by the Library of Congress for systems for search an retrieval of bilbiographic information. 

Many existing publication methods are based on FRBR and/or SRU. The methods eucellar, ELI and repository.overheid.nl are examples of such.
Also note that the CPRMV itself currently defines a RuleSet in terms of FRBR (a RuleSet is a F1_Work).

In the context of CPRMV this publication method defines a set of properties which allows an API serving CPRMV metadated publications to extract key information from SRU responses. The CPRMV API is a reference implementation for this.



subclass of: <a>CPRMV API - Generic Web Publication Method</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |
| url |   | 0..1 | The URL the SRU REST service can be accessed. |
| response-publication-location-term-namespace |   | 0..1 | The namespace for the term in the SRU response that indicates the web location the publication can be retrieved from. |
| response-publication-location-term |   | 0..1 | The term name in the SRU response that indicates the web location the publication can be retrieved from. |
| response-from-date-term-namespace |   | 0..1 | The namespace for the term in the SRU response that indicates the date from which the publication to be retrieved is valid. |
| response-from-date-term |   | 0..1 | The term name in the SRU response that indicates the date from which the publication to be retrieved is valid. |



## <dfn>Git</dfn>
 The git method is a well known base publication method for the publication of rulesets in git repositories.



subclass of: <a>CPRMV API - Generic Web Publication Method</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>jas</dfn>
 The jas method is a analysis method that focuses on a methodical and standardized semantic analysis of legal rulesets in natural language using a judicial analysis scheme as laid out in the book: Wetsnalyse



subclass of: <a>AnalysisMethod</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>juriconnect</dfn>
 The juriconnect method is a well known Dutch reference method.



subclass of: <a>ReferenceMethod</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>open-regels.nl</dfn>
 open-regels.nl is the development environment for CPRMV, the CPRMV API, and the IOU software stack.



properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>OpenFisca</dfn>
 The openfisca method is a well known formalisation, testing and publication method.



subclass of: <a>FormalisationMethod</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>Operaton</dfn>
 The Operaton method is a well known execution as well as publication method for BPMN process and DMN decision models.
It can be combined with the dmn13 method as such.



subclass of: <a>ExecutionMethod</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>DSO</dfn>
 The Dutch environment law domain (Digitaal Stelsel Omgevingswet (DSO)) includes a publication method for decision models using the DSO specific STTR formalisation method (based on DMN).
It can be combined with the sttr method as such. See for more information: https://iplo.nl/digitaal-stelsel/



subclass of: <a>STTR</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>corpus of RegelRecht Git Repository</dfn>
 RegelRecht is an experimental Dutch project (https://regelrecht.rijks.app). It uses a specific github repository to publish rulesets, defined by experts in an AI augmented way. It defines a RegelRecht "Law format" formalisation method as such. This regelrecht method is a specialisation of the generic git publication method referring to this project specific github repository. It also forms formalisation method (which within RegelRecht is called "Law format": https://regelrecht.rijks.app/concepts/law-format).



subclass of: <a>ExecutionMethod</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>repository of the Normenbrief showcase</dfn>
 Normenbrief is a showcase in collaboration with Amsterdam and SZW for using the CPRMV API to build a formalised version of a publication in natural language (published as a PDF) that forms an announcement of changes in parameters in laws. The formalised version being published in a specific GIT Pages web repository for this showcase. See the GIT pages repository: https://standaarden.open-regels.nl/showcases/amsterdam/ and the GIT repository: https://git.open-regels.nl/showcases/amsterdam/-/tree/normenbrief-jul-2025?ref_type=heads



subclass of: <a>CPRMV API - Generic JSON Serialisation Method</a>


properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>repository.overheid.nl</dfn>
 The repository.overheid.nl method is an official Dutch publication method (a web repository for official publications) for legal rulesets that are the output of the BWB and CVDR methods.



properties:


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



