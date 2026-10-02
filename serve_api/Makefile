install:
	pip install pip-tools
	./pip-compile.sh
	pip install -r requirements-dev.txt

deps:
	./pip-compile.sh

deps-upgrade:
	./pip-compile.sh --upgrade

tests:
	pytest test
