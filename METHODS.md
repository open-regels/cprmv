# About Methods

Methods within the context of CPRMV are the methods with which sets of rules are created, used, explained and referenced.
Methods can have different purposes and typically are combined with other methods in relation to a ruleset.

In the RDF specification of CPRMV, also all acknowledged methods are defined in terms of CPRMV concepts.
As of CPRMV version 0.4.2, all these methods are also included within the ReSpec documentation and 
implemented as separate plugin modules in the CPRMV Serve API.

# Method Development hints

This section will get to be more elaborated. For now some hints:

- methods are defined within their own subfolder within the methods subfolder in the rdf specification folder (starting with 0.4.2: /rdf/0.4.2/methods)
- methods to be used within the CPRMV API need also have a python implementation in the methods subfolder of the api (for instance /serve_api/methods/dmn13.py)
- the cprmv:id of a method definition must match how the method is named in RDF (so it defines the triple: (cprmvmethods:dmn13 cprmv:id "dmn13"), the value being the same as the name of the subject disregarding the namespace)
- only methods that are cprmv:acknowledged as one of the cprmv:rulemethods, as well as acknowledged as one of the publicationmethods or cprmv:referencemethods or cprmv:serialisationmethods will be loaded by the CPRMV API
- a publication method must be an (indirect) child of the class cprmv:PublicationMethod
- a reference method must be an (indirect) child of the class cprmv:ReferenceMethod
- a serialisation method must be an (indirect) child of the class cprmv:SerialisationMethod
- For now: other generic types of methods have no influence on the CPRMV API's behaviour (for instance AnalaysisMethods) 
- The CPRMV api automatically also uses methods that are parent methods of the ones it loads
- all core.* methods are used within the CPRMV api too therefor but are not to be used directly (and the same applies to frbr-sru and operaton which are types of publication systems but not yet tied to actual ones)
- The class hierarchy within RDF must match the clas hierarchy in Python. In python all method names with '.' and '-' characters defined in RDF, have these characters converted to an underscore (operaton.open-regels.nl in RDF becomes operaton_open_regels_nl in Python)
- A method module may define multiple methods (and that must then be the same both in RDF as Python). The name of the methods must begin or end with the method module name. For example: in the method module 'open-regels.nl', the method 'operaton.open-regels.nl' is defined in RDF and in a similar way the module python file must be called open_regels_nl.py containing the class definition: class operaton_open_regels_nl(core_web, dmn13):
- Currently the only useful real base method for PublicationMethods is 'core-web' which contains the functionality of downloading a publication somewhere from the web 
- Currently the only useful real base method for SerialisationMethods is 'core-xml' which contains the functionality of transforming a publication to RDF knowledge in terms of CPRMV concepts using a XSL transformation and XSL stylesheet bundled in these methods (for instance the 'bwb' method (which is defined as a core-xml method))
- Other supported and useful base methods may be operaton (any Operaton server, but not yet a specific one) and frbr-sru (possibly any FRBR SRU REST interface like the one provided in the context of Dutch Government, but not yet the specific one of the Dutch Government) 
- Currently, as was also the case prior to 0.4.2: the only supported ReferenceMethods are cprmvapi (the default used and implemented in the /rules end point of the CPRMV API), juriconnect (works only in relation with bwb serialisation method), eli (which defines the methods elifmx4 (eucullar and fmx4 only) and elinl (experimental, works with all suppoerted serialisation methods supported by the rules endpoint))
- All these base methods are combined in specific publication repositories, configured to make the CPRMV API work with existing repositories in production: Operaton on open-regels.nl, BWB and CVDR publications on repository.overheid.nl (also using the FRBR SRU search API to determin versions in effect at a specific date), and FMX4 publications from EU's CELLAR
- To make the CPRMV API work, when method definitions within the rdf subfolders are changed, do a 'make methods' in the serve_api folder. This will put all method definitions in /data/cprmvmethods.ttl and copy als XSL files to /data also, so the CPRMV API uses up to date method definitions
- Note hat the python implementations only have one version which is the same as the CPRMV API version, and the CPRMV API (currently) only supports one version of CPRMV information.
- See the implementations of the base method classes in /serve_api/methods (PublicationMethod.py for instance) to see what methods can be overridden. See the operaton.py class as an example of that.
- The CPRMV API adds /serve_api/methods to the loader path such that an "from operaton import operaton" works within another method module.
- The CPRMV API injects information from the cprmv methods knowledge graph into instances of the methods it loads (the whole knowledge graph is accesible from the code using: self.app.cprmvsettings["CPRMVMETHODS_KG"]).
- The CPRMV API injects the FastAPI app context in the methods it loads (self.app), notably also the SSL_CONTEXT (self.app.SSL_CONTEXT)
- The CPRMV API copies all predicate-objects in the RDF information tied to parent method classes (multiple levels, max 10) to the child method class it loads. These often contain values of which there should only be one defined. But care must be taken this is actually the case given the whole class hierarchy in the RDF information. So do not define a generic or example 'cprmv-serve:publication-id-format' in the 'cprmvmethods:bwb' method as this may override the one set in repository.overheid.nl-bwb which extends from 'cprmvmethods:bwb'... To place this information within the repository.overheid.nl-bwb method, it means the publication id format (with which a publication can be recognised to be mapped to a publication method and used to be referred to) is defined at the level of repository.overheid.nl and not BWB in general (which perhaps might be a fair thing to do).. The reason why the CPRMV API copies information is that this makes the information more easily accessible without having to know the class hierarchy within the method implementations.
