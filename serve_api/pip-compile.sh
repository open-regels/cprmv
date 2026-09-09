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

common="--allow-unsafe --generate-hashes${upgrade_args}"

# Update the compiled requirements files
run pip-compile $common --output-file requirements.txt pyproject.toml "$@"
run pip-compile $common --extra dev,tools --output-file requirements-dev.txt pyproject.toml "$@"
