# The hashed requirements files are compiled on Linux and install on Linux only
# (Windows: use WSL or the container). install does not recompile; use deps.
install:
	pip install pip-tools==7.6.2
	pip install -r requirements-dev.txt

methods:
	cp ../rdf/0.4.3/cprmv.ttl ./data/
	cp ../rdf/0.4.3/cprmvmethods.ttl ./data/
	ls ../rdf/0.4.3/methods/*/method.ttl | xargs cat >> ./data/cprmvmethods.ttl
	cp ../rdf/0.4.3/methods/*/*.xsl ./data

# Recompile the hashed requirements (Linux container, as CI does).
deps: deps-linux

PY_IMAGE = python:3.14-bookworm@sha256:fbaf91204f2758a70a7f7d6cf3c2871851227152a54e6a7b5b59941c4566b6b5

# Compile the hashed requirements on Linux/Python 3.14, as CI does. Extra
# arguments go to pip-compile.sh, e.g. make deps-linux ARGS=--upgrade
# (the sed strips CRs a Windows checkout may have put in the script).
deps-linux:
	MSYS_NO_PATHCONV=1 docker run --rm -e PIP_ROOT_USER_ACTION=ignore -e PIP_DISABLE_PIP_VERSION_CHECK=1 -v "$(CURDIR):/s" -w /s $(PY_IMAGE) \
		sh -c "pip install -q pip-tools==7.6.2 && sed -i 's/\r$$//' pip-compile.sh && ./pip-compile.sh $(ARGS)"

deps-upgrade:
	$(MAKE) deps-linux ARGS=--upgrade

tests:
	pytest test
