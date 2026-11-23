install:
	pip install pip-tools
	./pip-compile.sh
	pip install -r requirements-dev.txt

methods:
	cp ../rdf/0.4.3/cprmv.ttl ./data/
	cp ../rdf/0.4.3/cprmvmethods.ttl ./data/
	ls ../rdf/0.4.3/methods/*/method.ttl | xargs cat >> ./data/cprmvmethods.ttl
	cp ../rdf/0.4.3/methods/*/*.xsl ./data

deps:
	./pip-compile.sh

deps-upgrade:
	./pip-compile.sh --upgrade

tests:
	pytest test
