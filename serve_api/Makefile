install:
	pip install pip-tools
	./pip-compile.sh

methods:
	cp ../rdf/0.4.2/cprmv.ttl ./data/
	cp ../rdf/0.4.2/cprmvmethods.ttl ./data/
	ls ../rdf/0.4.2/methods/*/method.ttl | xargs cat >> ./data/cprmvmethods.ttl
	cp ../rdf/0.4.2/methods/*/*.xsl ./data

deps:
	./pip-compile.sh

tests:
	pytest test
