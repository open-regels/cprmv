#!/usr/bin/env bats
# Tests for scripts/audit-requirements.sh.
# Needs network (pip-audit queries the advisory database, like the real audit)
# and assumes `pip-audit` and `jq` are already on PATH: this file does not
# install them. CI installs pip-audit==2.10.1; locally run it in a Python image.

setup() {
  ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPT="$ROOT/scripts/audit-requirements.sh"
  FIX="$ROOT/scripts/test/fixtures"
  export AUDIT_REPORT_FILE="$BATS_TEST_TMPDIR/report.md"
  export PIP_AUDIT_ACCEPTED="$BATS_TEST_TMPDIR/accepted.txt"
  : > "$AUDIT_REPORT_FILE"
  : > "$PIP_AUDIT_ACCEPTED"
}

audit() {
  sh "$SCRIPT" test "$FIX/$1/requirements.txt" "$FIX/$1/requirements-dev.txt"
}

@test "shipped finding fails" {
  run audit shipped-vulnerable
  [ "$status" -eq 2 ]
  grep -q 'urllib3' "$AUDIT_REPORT_FILE"
  grep -Eq '(GHSA|PYSEC)-' "$AUDIT_REPORT_FILE"
}

@test "dev-only finding is reported, not failed" {
  run audit dev-only-vulnerable
  [ "$status" -eq 0 ]
  grep -qi 'development only' "$AUDIT_REPORT_FILE"
  # urllib3 must appear after the "development only" heading.
  sed -n '/[Dd]evelopment only/,$p' "$AUDIT_REPORT_FILE" | grep -q 'urllib3'
}

@test "accepted id is ignored" {
  run audit shipped-vulnerable
  [ "$status" -eq 2 ]
  {
    echo '# ids reported by the previous test'
    grep -Eo '(GHSA|PYSEC)-[A-Za-z0-9-]+' "$AUDIT_REPORT_FILE" | sort -u
  } > "$PIP_AUDIT_ACCEPTED"
  : > "$AUDIT_REPORT_FILE"
  run audit shipped-vulnerable
  [ "$status" -eq 0 ]
  grep -qi 'accepted' "$AUDIT_REPORT_FILE"
}

@test "clean is clean" {
  run audit clean
  [ "$status" -eq 0 ]
  grep -q 'No known advisories' "$AUDIT_REPORT_FILE"
}

# Stub pip-audit on PATH, to exercise tool failures without the network.
stub() {
  mkdir -p "$BATS_TEST_TMPDIR/bin"
  printf '#!/bin/sh\n%s\n' "$1" > "$BATS_TEST_TMPDIR/bin/pip-audit"
  chmod +x "$BATS_TEST_TMPDIR/bin/pip-audit"
  PATH="$BATS_TEST_TMPDIR/bin:$PATH"
}

@test "pip-audit failing with no output is a tool error" {
  stub 'exit 1'
  run audit clean
  [ "$status" -eq 2 ]
  grep -q 'could not run' "$AUDIT_REPORT_FILE"
  ! grep -q 'No known advisories' "$AUDIT_REPORT_FILE"
}

@test "a missing requirements file is a tool error" {
  run sh "$SCRIPT" test "$BATS_TEST_TMPDIR/nope.txt" "$FIX/clean/requirements-dev.txt"
  [ "$status" -eq 2 ]
  grep -q 'could not run for test' "$AUDIT_REPORT_FILE"
}

@test "a skipped shipped dependency is a tool error" {
  stub 'echo "{\"dependencies\":[{\"name\":\"Foo_Bar\",\"skip_reason\":\"not on PyPI\"}],\"fixes\":[]}"; exit 0'
  run audit clean
  [ "$status" -eq 2 ]
  grep -q 'Foo_Bar' "$AUDIT_REPORT_FILE"
  grep -q 'not on PyPI' "$AUDIT_REPORT_FILE"
}

@test "a skipped development dependency is listed, not failed" {
  stub 'case "$*" in *requirements-dev.txt*) echo "{\"dependencies\":[{\"name\":\"foo\",\"skip_reason\":\"not on PyPI\"}],\"fixes\":[]}";; *) echo "{\"dependencies\":[],\"fixes\":[]}";; esac; exit 0'
  run audit clean
  [ "$status" -eq 0 ]
  grep -q 'not on PyPI' "$AUDIT_REPORT_FILE"
}

@test "package names are normalised when separating development only findings" {
  stub 'case "$*" in *requirements-dev.txt*) echo "{\"dependencies\":[{\"name\":\"Foo_Bar\",\"version\":\"1\",\"vulns\":[{\"id\":\"PYSEC-1\",\"fix_versions\":[]}]}],\"fixes\":[]}";; *) echo "{\"dependencies\":[{\"name\":\"foo-bar\",\"version\":\"1\",\"vulns\":[{\"id\":\"PYSEC-1\",\"fix_versions\":[]}]}],\"fixes\":[]}";; esac; exit 1'
  run audit clean
  [ "$status" -eq 2 ]
  ! grep -qi 'development only' "$AUDIT_REPORT_FILE"
}
