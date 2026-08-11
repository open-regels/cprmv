install:
	pip install pip-tools
	./pip-compile.sh
	cp ../rdf/0.4.2/cprmv.ttl ./data/
	cp ../rdf/0.4.2/cprmvmethods.ttl ./data/
	ls ../rdf/0.4.2/methods/*/method.ttl | xargs cat >> ./data/cprmvmethods.ttl
	cp -R ../rdf/0.4.2/methods/* ./methods

deps:
	./pip-compile.sh

tests:
	pytest test
