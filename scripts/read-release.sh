#!/usr/bin/env bash
# Reads the release number from serve_api/RELEASE (or the file given) and prints
# `release=<value>`, for appending to $GITHUB_OUTPUT. Used by the build and
# publish jobs in ci.yml, which pass it to the image as BUILD_RELEASE.
#
# The file is written only by a release (/bump-release) and holds one line,
# vYYYY.MM.N. Before the first release it does not exist: that prints `release=`
# and exits 0, and /health reports "release": null.
#
# The value is validated as a WHOLE string, with bash's [[ =~ ]], before anything
# is printed. A line-by-line check (grep) would accept a file with a valid first
# line and more lines after it, and those lines would land in $GITHUB_OUTPUT as
# extra outputs. A CR, a second line or anything else fails the job.
#
# Command substitution drops ALL trailing newlines and bash drops NUL bytes, so
# the value alone would accept "v2026.11.0\n\n" or a NUL inside the number. The
# file is therefore also compared byte for byte with the value plus at most one
# newline, which is exactly what scripts/write-sbom.py accepts too.
#
# Usage: read-release.sh [file]     default: serve_api/RELEASE
# Exit:  0 printed (empty when the file is absent); 1 malformed; 2 bad usage.
set -euo pipefail

if [ "$#" -gt 1 ]; then
  echo "usage: read-release.sh [file]" >&2
  exit 2
fi
file=${1:-serve_api/RELEASE}

if [ ! -e "$file" ]; then
  echo "release="
  exit 0
fi

malformed() {
  echo "::error::$file is not a release number vYYYY.MM.N (one line, nothing else)" >&2
  exit 1
}

# Braces so bash's own "ignored null byte" warning is not printed.
{ release=$(cat -- "$file"); } 2>/dev/null
if ! cmp -s -- "$file" <(printf '%s\n' "$release") &&
  ! cmp -s -- "$file" <(printf '%s' "$release"); then
  malformed
fi
if ! [[ "$release" =~ ^v[0-9]{4}\.(0[1-9]|1[0-2])\.[0-9]+$ ]]; then
  malformed
fi
echo "release=$release"
