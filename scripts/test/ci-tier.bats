#!/usr/bin/env bats
# Tests for scripts/ci-tier.sh.

setup() {
  ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPT="$ROOT/scripts/ci-tier.sh"
}

@test "acc maps to the acceptance tier" {
  run sh "$SCRIPT" refs/heads/acc
  [ "$status" -eq 0 ]
  [ "${lines[0]}" = "tier=acc" ]
  [ "${lines[1]}" = "host=acc.cprmv.open-regels.nl" ]
  [ "${lines[2]}" = "environment=acceptance" ]
  [ "${lines[3]}" = "branch=acc" ]
  [ "${#lines[@]}" -eq 4 ]
}

@test "main maps to the stable tier" {
  run sh "$SCRIPT" refs/heads/main
  [ "$status" -eq 0 ]
  [ "${lines[0]}" = "tier=stable" ]
  [ "${lines[1]}" = "host=cprmv.open-regels.nl" ]
  [ "${lines[2]}" = "environment=stable" ]
  [ "${lines[3]}" = "branch=main" ]
  [ "${#lines[@]}" -eq 4 ]
}

@test "an unknown ref fails and prints no mapping" {
  run sh "$SCRIPT" refs/heads/feature/x
  [ "$status" -ne 0 ]
  [[ "$output" != *"tier="* ]]
}

@test "a tag ref fails" {
  run sh "$SCRIPT" refs/tags/acc
  [ "$status" -ne 0 ]
}

@test "no argument fails" {
  run sh "$SCRIPT"
  [ "$status" -ne 0 ]
}
