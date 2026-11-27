#!/usr/bin/env bats
# Tests for scripts/read-release.sh.

setup() {
  ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPT="$ROOT/scripts/read-release.sh"
  FILE="$BATS_TEST_TMPDIR/RELEASE"
}

@test "a valid release is printed as release=<value>" {
  printf 'v2026.11.0\n' >"$FILE"
  run bash "$SCRIPT" "$FILE"
  [ "$status" -eq 0 ]
  [ "$output" = "release=v2026.11.0" ]
}

@test "a file without a trailing newline is accepted" {
  printf 'v2026.12.17' >"$FILE"
  run bash "$SCRIPT" "$FILE"
  [ "$status" -eq 0 ]
  [ "$output" = "release=v2026.12.17" ]
}

@test "an absent file gives an empty release" {
  run bash "$SCRIPT" "$BATS_TEST_TMPDIR/does-not-exist"
  [ "$status" -eq 0 ]
  [ "$output" = "release=" ]
}

@test "the default path is serve_api/RELEASE under the working directory" {
  mkdir -p "$BATS_TEST_TMPDIR/repo/serve_api"
  printf 'v2027.01.3\n' >"$BATS_TEST_TMPDIR/repo/serve_api/RELEASE"
  cd "$BATS_TEST_TMPDIR/repo"
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [ "$output" = "release=v2027.01.3" ]
}

@test "a release without the v prefix fails and prints no release line" {
  printf '2026.11.0\n' >"$FILE"
  run bash "$SCRIPT" "$FILE"
  [ "$status" -eq 1 ]
  [[ "$output" != *"release="* ]]
  [[ "$output" == *"::error::"* ]]
}

@test "month 13 fails" {
  printf 'v2026.13.0\n' >"$FILE"
  run bash "$SCRIPT" "$FILE"
  [ "$status" -eq 1 ]
  [[ "$output" != *"release="* ]]
}

@test "month 00 and an unpadded month fail" {
  printf 'v2026.00.0\n' >"$FILE"
  run bash "$SCRIPT" "$FILE"
  [ "$status" -eq 1 ]
  printf 'v2026.1.0\n' >"$FILE"
  run bash "$SCRIPT" "$FILE"
  [ "$status" -eq 1 ]
}

@test "a multi-line value fails, so nothing can be injected into GITHUB_OUTPUT" {
  printf 'v2026.11.0\ninjected=1\n' >"$FILE"
  run bash "$SCRIPT" "$FILE"
  [ "$status" -eq 1 ]
  [[ "$output" != *"release="* ]]
  [[ "$output" != *"injected=1"* ]]
}

@test "trailing text on the same line fails" {
  printf 'v2026.11.0 extra\n' >"$FILE"
  run bash "$SCRIPT" "$FILE"
  [ "$status" -eq 1 ]
}

@test "a CRLF line ending fails" {
  printf 'v2026.11.0\r\n' >"$FILE"
  run bash "$SCRIPT" "$FILE"
  [ "$status" -eq 1 ]
}

@test "an empty file fails" {
  : >"$FILE"
  run bash "$SCRIPT" "$FILE"
  [ "$status" -eq 1 ]
}

@test "a NUL byte fails, even where bash would drop it" {
  printf 'v2026.11.0\0' >"$FILE"
  run bash "$SCRIPT" "$FILE"
  [ "$status" -eq 1 ]
  [[ "$output" != *"release="* ]]
  printf 'v2026.1\0001.0\n' >"$FILE"
  run bash "$SCRIPT" "$FILE"
  [ "$status" -eq 1 ]
  [[ "$output" != *"release="* ]]
}

@test "two trailing newlines fail (one line means one line)" {
  printf 'v2026.11.0\n\n' >"$FILE"
  run bash "$SCRIPT" "$FILE"
  [ "$status" -eq 1 ]
  [[ "$output" != *"release="* ]]
}

@test "a leading space fails" {
  printf ' v2026.11.0\n' >"$FILE"
  run bash "$SCRIPT" "$FILE"
  [ "$status" -eq 1 ]
}

@test "more than one argument is a usage error" {
  run bash "$SCRIPT" a b
  [ "$status" -eq 2 ]
}
