# CPRMV API


## <dfn>CPRMV API - Generic JSON Serialisation Method</dfn>
 The core.json method is a serialisation method that serves as a basis for the support of JSON serialisations of RuleSet's for any RuleMethod that typically use JSON as a serialisation format.

The nrml method is an example of such

This serialisation method is defined for support within API's that serve CPRMV metadated publications of which the CPRMV API is a reference implementation and should not be used directly and therefor it is definied in the cprmv-serve namespace.



subclass of: <a>SerialisationMethod</a>


properties (excluding inherited):


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



## <dfn>CPRMV API - Generic Web Publication Method</dfn>
 The core.web method is a publication method that serves as a basis for the support retrieval of RuleSet's that have been published and are retrieveable through HTTP.

The operaton and frbr-sru methods are examples of such.

This serialisation method is defined for support within API's that serve CPRMV metadated publications of which the CPRMV API is a reference implementation and should not be used directly and therefor it is definied in the cprmv-serve namespace.



subclass of: <a>PublicationMethod</a>


properties (excluding inherited):


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |
| repository-publication-location-format |   | 0..1 | The format of the URL to retrieve a publication |



## <dfn>CPRMV API - Generic XML Serialisation Method</dfn>
 The core.xml method is a serialisation method that serves as a basis for the support of XML serialisations of RuleSet's for any RuleMethod that typically use XML as a serialisation format.

The fmx4 method is an example of such.

This serialisation method is defined for support within API's that serve CPRMV metadated publications of which the CPRMV API is a reference implementation and should not be used directly and therefor it is definied in the cprmv-serve namespace.



subclass of: <a>SerialisationMethod</a>


properties (excluding inherited):


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |
| xslt |   | 0..1 | The name of the XSLT file to apply to transform the raw XML publication into RDF for use within the CPRMV API |



## <dfn>CPRMV API - Generic YAML Serialisation Method</dfn>
 The core.yaml method is a serialisation method that serves as a basis for the support of YAML serialisations of RuleSet's for any RuleMethod that typically use YAML as a serialisation format.

The ... method is an example of such

This serialisation method is defined for support within API's that serve CPRMV metadated publications of which the CPRMV API is a reference implementation and should not be used directly and therefor it is definied in the cprmv-serve namespace.



subclass of: <a>SerialisationMethod</a>


properties (excluding inherited):


| Property | Type/Range | Cardinality | Definition |
| --- | --- | --- | --- |



