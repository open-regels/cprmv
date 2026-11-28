#!/bin/sh

set -e

usage () {
    cat <<'EOF'
Usage: ./pip-compile.sh [options] [-- extra pip-compile args]

Compile requirements.txt and requirements-dev.txt from pyproject.toml.
Without options, existing pinned versions are kept and only missing or
changed entries are resolved.

Options:
  -u, --upgrade           Upgrade all dependencies to their latest allowed version
  -P, --upgrade-package P Upgrade only package P (repeatable, implies --upgrade)
  -h, --help              Show this help

Examples:
  ./pip-compile.sh                       # refresh, keep current pins
  ./pip-compile.sh --upgrade             # upgrade everything
  ./pip-compile.sh -P rdflib -P fastapi  # upgrade just these packages
EOF
}

upgrade_args=""

while [ $# -gt 0 ]; do
    case "$1" in
        -u|--upgrade)
            upgrade_args="${upgrade_args} --upgrade"
            ;;
        -P|--upgrade-package)
            if [ $# -lt 2 ]; then
                echo "Error: $1 requires a package name" >&2
                exit 2
            fi
            upgrade_args="${upgrade_args} --upgrade-package $2"
            shift
            ;;
        --upgrade-package=*)
            upgrade_args="${upgrade_args} --upgrade-package ${1#*=}"
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
        *)
            echo "Error: unknown option '$1'" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

if ! command -v pip-compile >/dev/null 2>&1; then
    echo "Error: pip-compile not found. Install it with: pip install pip-tools" >&2
    exit 1
fi

run () {
    header='\033[95m'
    endstyle='\033[0m'
    printf "${header}%s${endstyle}\n" "$*"
    eval "$*"
}

common="${upgrade_args}"

# Never add --uploaded-prior-to here (or pass it through "$@"): pip-compile
# writes it into the header of both files, the `audit` job's byte-for-byte
# recompile then fails, and Renovate's pip-compile manager rejects the unknown
# header option and stops maintaining the files. The 14-day cooldown is the
# environment variable PIP_UPLOADED_PRIOR_TO=P14D, which `make deps-linux` sets;
# pip applies it and pip-compile does not record it (see serve_api/Makefile).

# Update the compiled requirements files
# shellcheck disable=SC2086 # $common holds separate pip-compile options, split on purpose
run pip-compile $common --generate-hashes --allow-unsafe --strip-extras --output-file requirements.txt pyproject.toml "$@"
# The development file is constrained by the shipped one, compiled just above, so
# every shipped package has the same version in both and the tests run against
# what the image ships. Compiled on their own, the two drifted apart (typer and
# fastapi-cloud-cli, found on Renovate pull request #43).
# shellcheck disable=SC2086 # $common holds separate pip-compile options, split on purpose
run pip-compile $common --generate-hashes --allow-unsafe --strip-extras --extra dev,tools --constraint requirements.txt --output-file requirements-dev.txt pyproject.toml "$@"
