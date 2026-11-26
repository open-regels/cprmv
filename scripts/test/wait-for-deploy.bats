#!/usr/bin/env bats
# Tests for scripts/wait-for-deploy.sh.
# No network: status and health are file:// URLs and the "repository" is a local
# bare repo, all under $BATS_TEST_TMPDIR. Assumes `jq`, `git` and `curl` are
# already on PATH: this file does not install them.

setup() {
  ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPT="$ROOT/scripts/wait-for-deploy.sh"
  export WAIT_INTERVAL=0
  export WAIT_TIMEOUT=2
  unset GITHUB_ACTIONS

  # A bare repo whose branch `acc` points at $HEAD_SHA.
  REPO="$BATS_TEST_TMPDIR/repo.git"
  work="$BATS_TEST_TMPDIR/work"
  git init -q --bare "$REPO"
  git init -q "$work"
  git -C "$work" -c user.name=t -c user.email=t@example.invalid \
    commit -q --allow-empty -m one
  git -C "$work" push -q "$REPO" HEAD:refs/heads/acc
  HEAD_SHA="$(git -C "$REPO" rev-parse refs/heads/acc)"
  STATUS="$BATS_TEST_TMPDIR/deploy-status.json"
  HEALTH="$BATS_TEST_TMPDIR/health.json"
  OTHER="1111111111111111111111111111111111111111"
  THIRD="2222222222222222222222222222222222222222"
}

wait_for() { # wait_for <sha> [status_url] [health_url]
  sh "$SCRIPT" "${2:-file://$STATUS}" "$1" "$REPO" acc "${3:-file://$HEALTH}"
}

health_reports() { # health_reports <sha>
  printf '{"status":"ok","build":{"sha":"%s"}}\n' "$1" > "$HEALTH"
}

@test "deployed when running sha matches and health agrees" {
  printf '{"state":"waiting","running":{"sha":"%s"}}\n' "$HEAD_SHA" > "$STATUS"
  health_reports "$HEAD_SHA"
  run wait_for "$HEAD_SHA"
  [ "$status" -eq 0 ]
  [[ "$output" == *deployed* ]]
}

@test "not deployed while health reports another build" {
  printf '{"state":"waiting","running":{"sha":"%s"}}\n' "$HEAD_SHA" > "$STATUS"
  health_reports "$OTHER"
  run wait_for "$HEAD_SHA"
  [ "$status" -eq 1 ]
  [[ "$output" == *"timed out"* ]]
  [[ "$output" == *health* ]]
}

@test "not deployed while health is unreachable" {
  printf '{"state":"waiting","running":{"sha":"%s"}}\n' "$HEAD_SHA" > "$STATUS"
  run wait_for "$HEAD_SHA" "file://$STATUS" "file:///nonexistent/health.json"
  [ "$status" -eq 1 ]
  [[ "$output" == *"timed out"* ]]
  [[ "$output" == *"file:///nonexistent/health.json"* ]]
}

@test "fails fast when this sha failed" {
  printf '{"state":"failed","running":{"sha":"%s"},"last_attempt":{"sha":"%s","result":"restored"}}\n' \
    "$OTHER" "$HEAD_SHA" > "$STATUS"
  SECONDS=0
  run wait_for "$HEAD_SHA"
  [ "$status" -eq 1 ]
  [[ "$output" == *"deploy of $HEAD_SHA failed"* ]]
  [[ "$output" == *restored* ]]
  [[ "$output" != *"timed out"* ]]
  [ "$SECONDS" -lt 2 ]
}

@test "an older failed sha does not fail this run" {
  printf '{"state":"waiting","running":{"sha":"%s"},"last_attempt":{"sha":"%s","result":"failed"}}\n' \
    "$OTHER" "$OTHER" > "$STATUS"
  run wait_for "$HEAD_SHA"
  [ "$status" -eq 1 ]
  [[ "$output" == *"timed out"* ]]
  [[ "$output" != *failed* ]]
}

@test "broken fails" {
  printf '{"state":"broken","running":{"sha":"%s"}}\n' "$OTHER" > "$STATUS"
  run wait_for "$HEAD_SHA"
  [ "$status" -eq 1 ]
  [[ "$output" == *"state broken"* ]]
  [[ "$output" != *"timed out"* ]]
}

@test "broken fails even when running sha and health match" {
  printf '{"state":"broken","running":{"sha":"%s"}}\n' "$HEAD_SHA" > "$STATUS"
  health_reports "$HEAD_SHA"
  run wait_for "$HEAD_SHA"
  [ "$status" -eq 1 ]
  [[ "$output" == *"state broken"* ]]
}

@test "superseded when the branch moved" {
  printf '{"state":"waiting","running":{"sha":"%s"}}\n' "$THIRD" > "$STATUS"
  run wait_for "$OTHER"
  [ "$status" -eq 0 ]
  [[ "$output" == *superseded* ]]
  [[ "$output" == *"$HEAD_SHA"* ]]
}

@test "unreachable status keeps polling until timeout" {
  run wait_for "$HEAD_SHA" "file:///nonexistent/deploy-status.json"
  [ "$status" -eq 1 ]
  [[ "$output" == *"timed out"* ]]
  [[ "$output" == *"file:///nonexistent/deploy-status.json"* ]]
}

@test "a value in the status cannot start a workflow command line" {
  printf '{"state":"waiting\\n::error::injected","running":{"sha":"%s"}}\n' "$OTHER" > "$STATUS"
  run wait_for "$HEAD_SHA"
  [ "$status" -eq 1 ]
  [[ "$output" == *"timed out"* ]]
  run sh -c 'printf "%s\n" "$1" | grep -c "^::error::injected"' _ "$output"
  [ "$output" = 0 ]
}

@test "a non-numeric timeout or interval is a usage error" {
  WAIT_TIMEOUT=soon run wait_for "$HEAD_SHA"
  [ "$status" -eq 2 ]
  WAIT_INTERVAL=-1 run wait_for "$HEAD_SHA"
  [ "$status" -eq 2 ]
}
