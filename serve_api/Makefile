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
#
# The 14-day cooldown (SECURITY-PIPELINE.md, "Cooldown"): pip resolves only
# files uploaded at least 14 days ago. pip 26.1 is the first to take the P<n>D
# duration form, hence the pip pin next to pip-tools. The cutoff is set for
# the compile only, not for the bootstrap install: the image's own pip never
# sees it, so it cannot reject P14D (pip 26.0 knows no duration form) or
# refuse to install pip 26.3 itself. It is the
# environment variable PIP_UPLOADED_PRIOR_TO, never pip-compile's
# --uploaded-prior-to flag: pip-compile writes the flag into the header of
# requirements.txt, the `audit` job recompiles with ./pip-compile.sh and
# compares the files byte for byte, and Renovate's pip-compile manager rejects
# a header option it does not know ("Option ... not supported (yet)") and stops
# maintaining the file. The variable is applied and not recorded. `audit` sets
# no cutoff and keeps the committed pins, so it is unaffected.
deps-linux:
	MSYS_NO_PATHCONV=1 docker run --rm -e PIP_ROOT_USER_ACTION=ignore -e PIP_DISABLE_PIP_VERSION_CHECK=1 -v "$(CURDIR):/s" -w /s $(PY_IMAGE) \
		sh -c "pip install -q pip==26.3 pip-tools==7.6.2 && sed -i 's/\r$$//' pip-compile.sh && PIP_UPLOADED_PRIOR_TO=P14D ./pip-compile.sh $(ARGS)"

deps-upgrade:
	$(MAKE) deps-linux ARGS=--upgrade

tests:
	pytest test
