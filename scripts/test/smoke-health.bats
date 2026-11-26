#!/usr/bin/env bats
# Tests for scripts/smoke-health.sh.
# `docker` is a stub on PATH that logs every call to $BATS_TEST_TMPDIR/docker.log.
# `docker exec` prints $BATS_TEST_TMPDIR/health.json, or fails when it is absent.
# Assumes `jq` is already on PATH.

setup() {
  ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPT="$ROOT/scripts/smoke-health.sh"
  SHA="1111111111111111111111111111111111111111"
  OTHER="2222222222222222222222222222222222222222"
  export DOCKER_LOG="$BATS_TEST_TMPDIR/docker.log"
  export HEALTH="$BATS_TEST_TMPDIR/health.json"
  mkdir -p "$BATS_TEST_TMPDIR/bin"
  cat > "$BATS_TEST_TMPDIR/bin/docker" <<'STUB'
#!/bin/sh
echo "$*" >> "$DOCKER_LOG"
case $1 in
  exec) [ -f "$HEALTH" ] && cat "$HEALTH" || exit 1 ;;
esac
exit 0
STUB
  chmod +x "$BATS_TEST_TMPDIR/bin/docker"
  PATH="$BATS_TEST_TMPDIR/bin:$PATH"
}

health_reports() { # health_reports <sha-json-value>
  printf '{"status":"ok","build":{"sha":%s}}\n' "$1" > "$HEALTH"
}

@test "healthy and matching sha exits 0" {
  health_reports "\"$SHA\""
  run sh "$SCRIPT" img:tag "$SHA"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ok: img:tag reports build.sha $SHA"* ]]
  grep -q '^run -d --name cprmv-smoke img:tag$' "$DOCKER_LOG"
  grep -q '^rm -f cprmv-smoke$' "$DOCKER_LOG"
}

@test "mismatching sha exits 1 and names both" {
  health_reports "\"$OTHER\""
  run sh "$SCRIPT" img:tag "$SHA"
  [ "$status" -eq 1 ]
  [[ "$output" == *"$OTHER"* ]]
  [[ "$output" == *"$SHA"* ]]
  grep -q '^rm -f cprmv-smoke$' "$DOCKER_LOG"
}

@test "a null build.sha exits 1" {
  health_reports null
  run sh "$SCRIPT" img:tag "$SHA"
  [ "$status" -eq 1 ]
  [[ "$output" == *"'null'"* ]]
}

@test "no answer from /health exits 1 within the deadline and shows the logs" {
  export SMOKE_TIMEOUT=1
  start=$SECONDS
  run sh "$SCRIPT" img:tag "$SHA"
  [ "$status" -eq 1 ]
  [ $((SECONDS - start)) -le 10 ]
  [[ "$output" == *"did not answer within 1 seconds"* ]]
  grep -q '^logs cprmv-smoke$' "$DOCKER_LOG"
  grep -q '^rm -f cprmv-smoke$' "$DOCKER_LOG"
}

@test "wrong usage exits 2" {
  run sh "$SCRIPT" img:tag
  [ "$status" -eq 2 ]
}
