#!/bin/sh

set -e

run () {
    header='\033[95m'
    endstyle='\033[0m'
    echo "${header}$*${endstyle}"
    eval "$*"
}

# Update the compiled requirements files
run pip-compile --allow-unsafe --generate-hashes --upgrade --output-file requirements.txt pyproject.toml
run pip-compile --allow-unsafe --generate-hashes --upgrade --extra dev,tools --output-file requirements-dev.txt pyproject.toml
