#!/bin/sh
# Audits pinned Python requirements against the PyPI advisory database with
# pip-audit and writes a Markdown summary.
#
# pip-audit reports no severity, so any advisory in a shipped dependency fails.
# An advisory in a package that only the development requirements pull in is
# listed but does not fail: it is not shipped.
#
# Usage: audit-requirements.sh <label> <requirements.txt> <requirements-dev.txt>
# Env:   AUDIT_REPORT_FILE   append the Markdown section here
#        PIP_AUDIT_ACCEPTED  accepted advisory ids, one per line, `#` comments
#                            (default: pip-audit-accepted.txt beside this script)
# Needs: pip-audit and jq on PATH. Reads the pins only; installs nothing.
# Exit:  0 clean or development-only findings; 2 a shipped finding or a tool
#        error, which must not read as "clean".
set -u

if [ "$#" -ne 3 ]; then
  echo "usage: $0 <label> <requirements.txt> <requirements-dev.txt>" >&2
  exit 2
fi
label=$1
prod_file=$2
dev_file=$3

here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
accepted_file=${PIP_AUDIT_ACCEPTED:-$here/pip-audit-accepted.txt}

tmp=$(mktemp -d) || exit 2
trap 'rm -rf "$tmp"' EXIT

# Accepted ids: strip comments and blanks.
: > "$tmp/accepted"
if [ -f "$accepted_file" ]; then
  sed -e 's/#.*//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "$accepted_file" |
    grep -v '^$' > "$tmp/accepted" || true
fi

# could_not_run <message>: say so on stderr and in the report, so the tracking
# issue names the ref, then fail. A tool error must never read as "clean".
could_not_run() {
  echo "::error::$label: $1" >&2
  if [ -n "${AUDIT_REPORT_FILE:-}" ]; then
    {
      echo "### $label"
      echo
      echo "**Audit could not run for $label**: $1"
      echo
    } >> "$AUDIT_REPORT_FILE"
  fi
  exit 2
}

# audit <file> <out.json>: pip-audit exits 1 when it finds something, so the
# exit status is not the signal; a non-empty, parsable report is.
audit() {
  out=$2
  [ -f "$1" ] || return 1
  set -- --disable-pip --no-deps -r "$1" --format json --progress-spinner off
  while IFS= read -r id; do
    set -- "$@" --ignore-vuln "$id"
  done < "$tmp/accepted"
  pip-audit "$@" > "$out" 2> "$out.err" || true
  [ -s "$out" ] &&
    jq -e '(.dependencies // null) | type == "array"' "$out" > /dev/null 2>&1
}

audit "$prod_file" "$tmp/prod.json" ||
  could_not_run "pip-audit produced no parsable report for $prod_file"
audit "$dev_file" "$tmp/dev.json" ||
  could_not_run "pip-audit produced no parsable report for $dev_file"

# A dependency pip-audit skipped was not audited. In the shipped file that is a
# tool error; in the development file it is listed.
skipped='.dependencies[] | select(.skip_reason != null) | "- **\(.name)**: \(.skip_reason)"'
jq -r "$skipped" "$tmp/prod.json" > "$tmp/prod-skipped.md"
if [ -s "$tmp/prod-skipped.md" ]; then
  could_not_run "pip-audit skipped shipped dependencies in $prod_file: $(tr '\n' ' ' < "$tmp/prod-skipped.md")"
fi
jq -r "$skipped" "$tmp/dev.json" > "$tmp/dev-skipped.md"

# One bullet per vulnerable package.
list='.dependencies[] | select((.vulns // [] | length) > 0) |
  "- **\(.name) \(.version)**: " + ([.vulns | unique_by(.id)[] | .id + (if (.fix_versions | length) > 0 then " (fixed in " + (.fix_versions | join(", ")) + ")" else "" end)] | join(", "))'

jq -r "$list" "$tmp/prod.json" > "$tmp/prod.md"
jq '[.dependencies[] | select((.vulns // [] | length) > 0) | .name | ascii_downcase | gsub("[-_.]+"; "-")]'   "$tmp/prod.json" > "$tmp/prod-names.json"
# Development only: vulnerable packages that are not also vulnerable when shipped.
jq --slurpfile shipped "$tmp/prod-names.json"   '.dependencies |= map(select((.name | ascii_downcase | gsub("[-_.]+"; "-")) as $n | ($shipped[0] | index($n)) | not))'   "$tmp/dev.json" > "$tmp/dev-only.json"
jq -r "$list" "$tmp/dev-only.json" > "$tmp/dev.md"

{
  echo "### $label"
  echo
  if [ -s "$tmp/prod.md" ]; then
    echo "**Shipped dependencies**"
    echo
    cat "$tmp/prod.md"
    echo
  fi
  if [ -s "$tmp/dev.md" ]; then
    echo "**Advisories in development only dependencies** (not shipped, do not fail)"
    echo
    cat "$tmp/dev.md"
    echo
  fi
  if [ -s "$tmp/dev-skipped.md" ]; then
    echo "**Development only dependencies pip-audit skipped** (not audited, do not fail)"
    echo
    cat "$tmp/dev-skipped.md"
    echo
  fi
  if [ ! -s "$tmp/prod.md" ] && [ ! -s "$tmp/dev.md" ] && [ ! -s "$tmp/dev-skipped.md" ]; then
    echo "No known advisories."
    echo
  fi
  if [ -s "$tmp/accepted" ]; then
    echo "Accepted advisories ignored: $(paste -sd, "$tmp/accepted" | sed 's/,/, /g')"
    echo
  fi
} > "$tmp/body.md"

cat "$tmp/body.md"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  cat "$tmp/body.md" >> "$GITHUB_STEP_SUMMARY"
fi
if [ -n "${AUDIT_REPORT_FILE:-}" ]; then
  cat "$tmp/body.md" >> "$AUDIT_REPORT_FILE"
fi

if [ -s "$tmp/prod.md" ]; then
  echo "::error::$label: advisory in shipped dependencies" >&2
  exit 2
fi
exit 0
