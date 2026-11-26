#!/usr/bin/env bats
# Tests for deployment/vm/reconciler/reconcile.sh.
# No network: the "GitHub repository" is a local bare repo, and `docker` and
# `curl` are the stubs in test/stubs/, put first on PATH. The stubs log every
# call to $STUB_DIR/calls.log and are driven by files in $STUB_DIR:
#   daemon_down          `docker info` fails (daemon not reachable)
#   image_missing_<sha>  `docker manifest inspect` finds no image for <sha>
#   pull_fails_<sha>     `docker pull` of <sha> fails
#   digest_<sha>         the digest `docker image inspect` reports for <sha>
#   up_fails_<sha>       `docker compose ... up` for release <sha> fails
#   ps_health            what `docker compose ps` reports (default: healthy)
#   health_sha           the build.sha /health serves (default: the last sha
#                        brought up; nothing up = connection refused)
# Assumes git, jq, flock (util-linux) and coreutils are already on PATH: this
# file installs nothing. Runs the script with `sh` (dash on Debian).

setup() {
  SRC="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  SCRIPT="$SRC/reconcile.sh"
  export STUB_DIR="$BATS_TEST_TMPDIR/stub"
  mkdir -p "$STUB_DIR"
  export PATH="$SRC/test/stubs:$PATH"
  export CPRMV_ROOT="$BATS_TEST_TMPDIR/opt"
  export CPRMV_REPO_URL="$BATS_TEST_TMPDIR/origin.git"
  export CPRMV_INSTALLED_RECONCILER="$SCRIPT"
  unset CPRMV_BRANCH CPRMV_IMAGE_REPO CPRMV_HEALTH_URL CPRMV_HEALTH_TIMEOUT CPRMV_STALLED_AFTER
  D="$CPRMV_ROOT/acc"
  STATUS="$D/www/deploy-status.json"

  git init -q --bare "$CPRMV_REPO_URL"
  WORK="$BATS_TEST_TMPDIR/work"
  git init -q "$WORK"
  mkdir -p "$WORK/deployment/vm/acc" "$WORK/deployment/vm/reconciler"
  cp "$SCRIPT" "$WORK/deployment/vm/reconciler/reconcile.sh"
}

# commit <label>: a new head on acc whose compose.yml differs; sets $SHA.
commit() {
  printf 'services: {} # %s\n' "$1" >"$WORK/deployment/vm/acc/compose.yml"
  git -C "$WORK" add -A
  git -C "$WORK" -c user.name=t -c user.email=t@example.invalid commit -q -m "$1"
  git -C "$WORK" push -q "$CPRMV_REPO_URL" HEAD:refs/heads/acc
  SHA="$(git -C "$WORK" rev-parse HEAD)"
}

reconcile() { sh "$SCRIPT" acc; }
st() { jq -r "$@" "$STATUS"; }
state() { jq -r "$@" "$D/state.json"; }
calls() { cat "$STUB_DIR/calls.log" 2>/dev/null || true; }
ups() { calls | grep '^docker compose .* up ' || true; }
clear_calls() { rm -f "$STUB_DIR/calls.log"; }

# deploy <label>: commit and reconcile successfully; sets $SHA.
deploy() {
  commit "$1"
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(st .state)" = running ]
  [ "$(st .running.sha)" = "$SHA" ]
}

@test "first run deploys the head" {
  commit one
  printf '%064d\n' 7 >"$STUB_DIR/digest_$SHA"
  d="$(cat "$STUB_DIR/digest_$SHA")"
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(st .tier)" = acc ]
  [ "$(st .state)" = running ]
  [ "$(st .target.sha)" = "$SHA" ]
  [ "$(st .running.sha)" = "$SHA" ]
  [ "$(st .running.digest)" = "sha256:$d" ]
  [ "$(st .last_attempt.sha)" = "$SHA" ]
  [ "$(st .last_attempt.result)" = deployed ]
  [ "$(st .warning)" = null ]
  [[ "$(st .checked_at)" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
  grep -qx "CPRMV_IMAGE=ghcr.io/open-regels/cprmv-api@sha256:$d" "$D/releases/$SHA/.env"
  grep -qx "CPRMV_IMAGE_DIGEST=sha256:$d" "$D/releases/$SHA/.env"
  [ -f "$D/releases/$SHA/compose.yml" ]
  [ "$(cd "$D/current" && pwd -P)" = "$(cd "$D/releases/$SHA" && pwd -P)" ]
  calls | grep -q "^docker pull .*ghcr.io/open-regels/cprmv-api:sha-$SHA\$"
  [ "$(ups | wc -l)" -eq 1 ]
  ups | grep -q -- "-p cprmv-acc .*-f $D/releases/$SHA/compose.yml .*up -d --wait .*--remove-orphans"
  [ ! -e "$STATUS.tmp" ]
  [ "$(git -C "$D/repo" rev-parse --is-bare-repository)" = true ]
}

@test "second run changes nothing" {
  deploy one
  first="$(jq -S 'del(.checked_at)' "$STATUS")"
  clear_calls
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(jq -S 'del(.checked_at)' "$STATUS")" = "$first" ]
  ! calls | grep -Eq '^docker (pull|compose .* up )'
  calls | grep -q '^docker compose .* ps '
}

@test "image not yet built waits, then stalls" {
  deploy one
  a="$SHA"
  commit two
  touch "$STUB_DIR/image_missing_$SHA"
  clear_calls
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(st .state)" = waiting ]
  [ "$(st .target.sha)" = "$SHA" ]
  [ "$(st .running.sha)" = "$a" ]
  [ -z "$(ups)" ]
  # A second waiting run keeps the original since.
  jq '.waiting.since = "2000-01-01T00:00:00Z"' "$D/state.json" >"$D/s" && mv "$D/s" "$D/state.json"
  run reconcile
  [ "$(st .state)" = waiting ]
  [ "$(state .waiting.since)" = 2000-01-01T00:00:00Z ]
  # 2000 s on the same target is past the default 1800 s.
  jq '.waiting.since_epoch -= 2000' "$D/state.json" >"$D/s" && mv "$D/s" "$D/state.json"
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(st .state)" = stalled ]
  [ "$(st .running.sha)" = "$a" ]
  [ -z "$(ups)" ]
  ! calls | grep -q '^docker pull'
}

@test "failed deploy restores the previous" {
  deploy one
  a="$SHA"
  commit two
  b="$SHA"
  touch "$STUB_DIR/up_fails_$b"
  clear_calls
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(ups | wc -l)" -eq 2 ]
  ups | sed -n 1p | grep -q "releases/$b/compose.yml"
  ups | sed -n 2p | grep -q "releases/$a/compose.yml"
  [ "$(st .state)" = failed ]
  [ "$(st .running.sha)" = "$a" ]
  [ "$(st .last_attempt.sha)" = "$b" ]
  [ "$(st .last_attempt.result)" = restored ]
  [ "$(st .last_attempt.error | wc -l)" -eq 20 ]
  st .last_attempt.error | tail -n 1 | grep -q "compose error line 25 for $b"
  [ "$(state '.failed | index("'"$b"'")')" != null ]
  [ "$(cd "$D/current" && pwd -P)" = "$(cd "$D/releases/$a" && pwd -P)" ]
}

@test "wrong sha on /health counts as failure" {
  deploy one
  a="$SHA"
  echo "$a" >"$STUB_DIR/health_sha"
  commit two
  b="$SHA"
  clear_calls
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(ups | wc -l)" -eq 2 ]
  ups | sed -n 1p | grep -q "releases/$b/compose.yml"
  ups | sed -n 2p | grep -q "releases/$a/compose.yml"
  [ "$(st .state)" = failed ]
  [ "$(st .running.sha)" = "$a" ]
  [ "$(st .last_attempt.result)" = restored ]
  st .last_attempt.error | grep -q "$a"
  [ "$(state '.failed | index("'"$b"'")')" != null ]
}

@test "failed sha is not retried" {
  deploy one
  commit two
  b="$SHA"
  touch "$STUB_DIR/up_fails_$b"
  run reconcile
  [ "$(st .state)" = failed ]
  rm "$STUB_DIR/up_fails_$b"
  clear_calls
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(st .state)" = failed ]
  [ "$(st .target.sha)" = "$b" ]
  [ "$(st .last_attempt.sha)" = "$b" ]
  ! calls | grep -Eq '^docker (pull|manifest|compose .* up )'
}

@test "new commit after a failure is tried" {
  deploy one
  a="$SHA"
  commit two
  touch "$STUB_DIR/up_fails_$SHA"
  run reconcile
  [ "$(st .state)" = failed ]
  commit three
  c="$SHA"
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(st .state)" = running ]
  [ "$(st .running.sha)" = "$c" ]
  [ "$(st .last_attempt.result)" = deployed ]
  [ "$(state .previous.sha)" = "$a" ]
}

@test "restore failing is broken" {
  deploy one
  a="$SHA"
  commit two
  b="$SHA"
  touch "$STUB_DIR/up_fails_$b" "$STUB_DIR/up_fails_$a"
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(st .state)" = broken ]
  [ "$(st .running)" = null ]
  [ "$(st .last_attempt.sha)" = "$b" ]
  [ "$(st .last_attempt.result)" = failed ]
  st .warning | grep -q "restore of $a"
  # Stays broken until acc moves, without retrying.
  clear_calls
  run reconcile
  [ "$(st .state)" = broken ]
  [ -z "$(ups)" ]
}

@test "first deploy fails with no previous" {
  commit one
  touch "$STUB_DIR/up_fails_$SHA"
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(st .state)" = failed ]
  [ "$(st .running)" = null ]
  [ "$(st .last_attempt.result)" = failed ]
  [ "$(state '.failed | index("'"$SHA"'")')" != null ]
  [ "$(ups | wc -l)" -eq 1 ]
  clear_calls
  run reconcile
  [ "$(st .state)" = failed ]
  [ -z "$(ups)" ]
}

@test "unhealthy current release is re-applied" {
  deploy one
  echo unhealthy >"$STUB_DIR/ps_health"
  clear_calls
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(ups | wc -l)" -eq 1 ]
  ups | grep -q "releases/$SHA/compose.yml"
  [ "$(st .state)" = running ]
  [ "$(st .running.sha)" = "$SHA" ]
  [ "$(st .last_attempt.result)" = deployed ]
  st .warning | grep -q unhealthy
}

@test "fetch failure leaves the running release alone" {
  deploy one
  before="$(jq -S 'del(.checked_at, .warning)' "$STATUS")"
  clear_calls
  CPRMV_REPO_URL="$BATS_TEST_TMPDIR/nowhere.git" run reconcile
  [ "$status" -eq 0 ]
  ! calls | grep -q '^docker'
  [ "$(jq -S 'del(.checked_at, .warning)' "$STATUS")" = "$before" ]
  [ "$(st .state)" = running ]
  st .warning | grep -q fetch
}

@test "prune keeps current and previous" {
  deploy one
  a="$SHA"
  deploy two
  b="$SHA"
  deploy three
  c="$SHA"
  [ "$(ls "$D/releases" | sort)" = "$(printf '%s\n' "$b" "$c" | sort)" ]
  calls | grep -q "^docker image rm .*sha-$a\$"
  ! calls | grep -Eq "^docker image rm .*sha-($b|$c)\$"
}

@test "reports whether the installed reconciler matches" {
  deploy one
  [ "$(st .reconciler.commit)" = "$SHA" ]
  [ "$(st .reconciler.matches_repo)" = true ]
  echo "# not the same" >"$BATS_TEST_TMPDIR/other.sh"
  CPRMV_INSTALLED_RECONCILER="$BATS_TEST_TMPDIR/other.sh" run reconcile
  [ "$status" -eq 0 ]
  [ "$(st .reconciler.matches_repo)" = false ]
}

@test "a held lock skips the run" {
  commit one
  mkdir -p "$D"
  run flock "$D/reconcile.lock" sh "$SCRIPT" acc
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$(calls)" ]
  [ ! -e "$STATUS" ]
}

@test "docker daemon unreachable changes nothing" {
  deploy one
  before="$(jq -S 'del(.checked_at, .warning)' "$STATUS")"
  state_before="$(cat "$D/state.json")"
  commit two
  touch "$STUB_DIR/daemon_down"
  clear_calls
  run reconcile
  [ "$status" -eq 0 ]
  ! calls | grep -Eq '^docker (pull|manifest|compose)'
  [ "$(jq -S 'del(.checked_at, .warning)' "$STATUS")" = "$before" ]
  [ "$(cat "$D/state.json")" = "$state_before" ]
  st .warning | grep -q "docker daemon not reachable"
}

@test "failed target keeps the running release healthy" {
  deploy one
  a="$SHA"
  commit two
  b="$SHA"
  touch "$STUB_DIR/up_fails_$b"
  run reconcile
  [ "$(st .state)" = failed ]
  failed_before="$(state -c .failed)"
  attempt_before="$(st -c .last_attempt)"
  echo unhealthy >"$STUB_DIR/ps_health"
  clear_calls
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(ups | wc -l)" -eq 1 ]
  ups | grep -q "releases/$a/compose.yml"
  [ "$(st .state)" = failed ]
  [ "$(st .running.sha)" = "$a" ]
  [ "$(state -c .failed)" = "$failed_before" ]
  [ "$(st -c .last_attempt)" = "$attempt_before" ]
  st .warning | grep -q "re-applied"
}

@test "waiting keeps the running release healthy" {
  deploy one
  a="$SHA"
  commit two
  touch "$STUB_DIR/image_missing_$SHA"
  echo unhealthy >"$STUB_DIR/ps_health"
  clear_calls
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(ups | wc -l)" -eq 1 ]
  ups | grep -q "releases/$a/compose.yml"
  [ "$(st .state)" = waiting ]
  [ "$(st .running.sha)" = "$a" ]
  [ "$(st .last_attempt.sha)" = "$a" ]
  [ "$(state '.failed | length')" -eq 0 ]
  st .warning | grep -q "re-applied"
}

@test "a failed re-apply of the running release does not fail the run" {
  deploy one
  a="$SHA"
  commit two
  touch "$STUB_DIR/image_missing_$SHA"
  echo unhealthy >"$STUB_DIR/ps_health"
  touch "$STUB_DIR/up_fails_$a"
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(st .state)" = waiting ]
  [ "$(st .running.sha)" = "$a" ]
  [ "$(state '.failed | length')" -eq 0 ]
  st .warning | grep -q "re-applying it failed"
}

@test "pull failure waits instead of failing" {
  deploy one
  a="$SHA"
  commit two
  b="$SHA"
  touch "$STUB_DIR/pull_fails_$b"
  clear_calls
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(st .state)" = waiting ]
  [ "$(st .running.sha)" = "$a" ]
  [ "$(st .last_attempt.sha)" = "$a" ]
  [ "$(state '.failed | length')" -eq 0 ]
  [ -z "$(ups)" ]
  st .warning | grep -q pull
  CPRMV_STALLED_AFTER=0 run reconcile
  [ "$(st .state)" = stalled ]
  rm "$STUB_DIR/pull_fails_$b"
  run reconcile
  [ "$(st .state)" = running ]
  [ "$(st .running.sha)" = "$b" ]
}

@test "failed re-apply of the target restores the previous" {
  deploy one
  a="$SHA"
  deploy two
  b="$SHA"
  echo unhealthy >"$STUB_DIR/ps_health"
  touch "$STUB_DIR/up_fails_$b"
  clear_calls
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(ups | wc -l)" -eq 2 ]
  ups | sed -n 1p | grep -q "releases/$b/compose.yml"
  ups | sed -n 2p | grep -q "releases/$a/compose.yml"
  [ "$(st .state)" = failed ]
  [ "$(st .running.sha)" = "$a" ]
  [ "$(state .previous)" = null ]
  [ "$(state '.failed | index("'"$b"'")')" != null ]
  [ "$(cd "$D/current" && pwd -P)" = "$(cd "$D/releases/$a" && pwd -P)" ]
  st .warning | grep -q "restored $a"
}

@test "no matching digest fails the target and restores" {
  deploy one
  a="$SHA"
  commit two
  b="$SHA"
  : >"$STUB_DIR/digest_$b"
  clear_calls
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(st .state)" = failed ]
  [ "$(st .running.sha)" = "$a" ]
  [ "$(st .last_attempt.result)" = restored ]
  st .last_attempt.error | grep -q digest
  [ "$(ups | wc -l)" -eq 1 ]
  ups | grep -q "releases/$a/compose.yml"
}

@test "a commit without its tier directory fails and restores" {
  deploy one
  a="$SHA"
  git -C "$WORK" rm -q -r deployment/vm/acc
  git -C "$WORK" -c user.name=t -c user.email=t@example.invalid commit -q -m gone
  git -C "$WORK" push -q "$CPRMV_REPO_URL" HEAD:refs/heads/acc
  b="$(git -C "$WORK" rev-parse HEAD)"
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(st .state)" = failed ]
  [ "$(st .last_attempt.sha)" = "$b" ]
  [ "$(st .last_attempt.result)" = restored ]
  [ "$(st .running.sha)" = "$a" ]
}

@test "an existing clone in repo/ is used, not littered" {
  commit one
  mkdir -p "$D"
  git clone -q "$CPRMV_REPO_URL" "$D/repo"
  run reconcile
  [ "$status" -eq 0 ]
  [ "$(st .running.sha)" = "$SHA" ]
  [ ! -e "$D/repo/HEAD" ]
  [ -z "$(git -C "$D/repo" status --porcelain)" ]
}
