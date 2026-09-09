install:
	pip install pip-tools
	./pip-compile.sh

deps:
	./pip-compile.sh

deps-upgrade:
	./pip-compile.sh --upgrade

tests:
	pytest test
