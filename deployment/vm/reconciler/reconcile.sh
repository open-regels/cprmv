#!/bin/sh
# Reconciles one tier of the CPRMV VM with the head of its branch on GitHub.
# Run every 2 minutes by cprmv-reconcile@<tier>.timer, as the cprmv user.
#
# Usage: reconcile.sh <tier>
# Env (defaults):
#   CPRMV_ROOT                  /opt/cprmv
#   CPRMV_REPO_URL              https://github.com/open-regels/cprmv.git
#   CPRMV_BRANCH                <tier>
#   CPRMV_IMAGE_REPO            ghcr.io/open-regels/cprmv-api
#   CPRMV_HEALTH_URL            http://127.0.0.1:8000/health
#   CPRMV_HEALTH_TIMEOUT        120   seconds `compose up --wait` may take
#   CPRMV_STALLED_AFTER         1800  seconds of waiting for an image before "stalled"
#   CPRMV_INSTALLED_RECONCILER  /usr/local/lib/cprmv/reconcile.sh
# Layout under $CPRMV_ROOT/<tier>/: repo/ (bare clone), releases/<sha>/
# (deployment/vm/<tier>/ at <sha>, plus .env), current -> releases/<sha>,
# state.json, www/deploy-status.json (served by Caddy), reconcile.lock.
#
# One run: lock, fetch, nothing-to-do check, failed list, image present,
# prepare, apply, verify, record, prune, write the status. A failed deploy
# restores the release that ran before it; only if that fails too is the state
# "broken". It never updates itself: deploy-status.json reports whether the
# installed copy matches the one in the target commit.
# Exit: 0, also when a deploy fails or the fetch fails (the status says so);
#       non-zero only on its own errors; 2 on bad usage.

# The single-quoted programs passed to jset are jq, whose $names are jq
# variables (--arg), not shell expansions.
# shellcheck disable=SC2016
set -eu

usage() {
  echo "usage: $0 <tier>" >&2
  exit 2
}

[ "$#" -eq 1 ] || usage
tier=$1
case $tier in '' | *[!a-z0-9-]*) usage ;; esac

root=${CPRMV_ROOT:-/opt/cprmv}
repo_url=${CPRMV_REPO_URL:-https://github.com/open-regels/cprmv.git}
branch=${CPRMV_BRANCH:-$tier}
image_repo=${CPRMV_IMAGE_REPO:-ghcr.io/open-regels/cprmv-api}
health_url=${CPRMV_HEALTH_URL:-http://127.0.0.1:8000/health}
health_timeout=${CPRMV_HEALTH_TIMEOUT:-120}
stalled_after=${CPRMV_STALLED_AFTER:-1800}
installed=${CPRMV_INSTALLED_RECONCILER:-/usr/local/lib/cprmv/reconcile.sh}
case $health_timeout in '' | *[!0-9]*) usage ;; esac
case $stalled_after in '' | *[!0-9]*) usage ;; esac

dir=$root/$tier
repo=$dir/repo
state_file=$dir/state.json
status_file=$dir/www/deploy-status.json
project=cprmv-$tier
warning=""

mkdir -p "$dir/releases" "$dir/www"

# Runs never overlap; a run that finds the lock held leaves quietly.
exec 9>"$dir/reconcile.lock"
flock -n 9 || exit 0

rm -rf "$dir"/.run.* # left by a run that was killed; the lock is ours now
work=$(mktemp -d "$dir/.run.XXXXXX")
trap 'rm -rf "$work"' EXIT
trap 'exit 1' HUP INT TERM

[ -s "$state_file" ] ||
  echo '{"state":null,"target":null,"running":null,"previous":null,"failed":[],"waiting":null,"last_attempt":null}' >"$state_file"

now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# jget <filter>: a value from state.json, empty when null.
jget() { jq -r "($1) // empty" "$state_file"; }

# jset [jq options] <filter>: update state.json atomically.
jset() {
  jq "$@" "$state_file" >"$state_file.tmp"
  mv -f "$state_file.tmp" "$state_file"
}

# bounded <seconds> <command...>: run with a time limit where `timeout` exists.
bounded() {
  if command -v timeout >/dev/null 2>&1; then
    timeout "$@"
  else
    shift
    "$@"
  fi
}

# write_status: deploy-status.json from state.json, via a temp file and rename.
write_status() {
  t=$(jget .target)
  match=null
  if [ -n "$t" ]; then
    if git -C "$repo" show "$t:deployment/vm/reconciler/reconcile.sh" >"$work/reconciler" 2>/dev/null &&
      [ -f "$installed" ] && cmp -s "$work/reconciler" "$installed"; then
      match=true
    else
      match=false
    fi
  fi
  jq --arg tier "$tier" --arg at "$(now)" --arg w "$warning" --argjson m "$match" '{
    tier: $tier,
    checked_at: $at,
    state: .state,
    target: (if .target then {sha: .target} else null end),
    running: .running,
    last_attempt: .last_attempt,
    reconciler: {commit: .target, matches_repo: $m},
    warning: (if $w == "" then null else $w end)
  }' "$state_file" >"$status_file.tmp"
  mv -f "$status_file.tmp" "$status_file"
}

# finish <state>: record the state, write the status, end the run.
finish() {
  jset --arg s "$1" '.state = $s'
  write_status
  exit 0
}

is_sha() {
  case $1 in '' | *[!0-9a-f]*) return 1 ;; esac
  [ "${#1}" -eq 40 ]
}

# healthy <sha>: compose reports the API of release <sha> healthy.
healthy() {
  rel=$dir/releases/$1
  [ -f "$rel/compose.yml" ] && [ -f "$rel/.env" ] || return 1
  h=$(docker compose -p "$project" -f "$rel/compose.yml" --env-file "$rel/.env" \
    ps --format '{{.Health}}' cprmv-api 2>/dev/null) || return 1
  [ "$h" = healthy ]
}

# prepare <sha>: make sure the image is here, resolve its digest, export the
# release, write .env. Output goes to $work/out.
prepare() {
  rel=$dir/releases/$1
  tag=$image_repo:sha-$1
  if ! docker image inspect "$tag" >/dev/null 2>&1; then
    docker pull -q "$tag" >>"$work/out" 2>&1 || return 1
  fi
  digest=$(docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "$tag" 2>>"$work/out" |
    sed -n "s|^$image_repo@\(sha256:[0-9a-f]\{64\}\)\$|\1|p" | head -n 1) || return 1
  if [ -z "$digest" ]; then
    echo "no $image_repo digest for $tag" >>"$work/out"
    return 1
  fi
  rm -rf "$rel" && mkdir -p "$rel" || return 1
  git -C "$repo" archive -o "$work/release.tar" "$1" "deployment/vm/$tier" >>"$work/out" 2>&1 || return 1
  tar -xf "$work/release.tar" -C "$rel" --strip-components=3 >>"$work/out" 2>&1 || return 1
  if [ -L "$rel/compose.yml" ] || [ ! -f "$rel/compose.yml" ]; then
    echo "deployment/vm/$tier/compose.yml in $1 is missing or a symlink" >>"$work/out"
    return 1
  fi
  rm -f "$rel/.env" || return 1
  printf 'CPRMV_IMAGE=%s@%s\nCPRMV_IMAGE_DIGEST=%s\n' "$image_repo" "$digest" "$digest" >"$rel/.env" || return 1
}

# attempt <sha>: prepare the release if needed, bring it up, and check that
# /health reports <sha>. Output goes to $work/out (emptied first).
attempt() {
  rel=$dir/releases/$1
  : >"$work/out" || return 1
  if [ ! -f "$rel/.env" ] || [ ! -f "$rel/compose.yml" ]; then
    prepare "$1" || return 1
  fi
  docker compose -p "$project" -f "$rel/compose.yml" --env-file "$rel/.env" \
    up -d --wait --wait-timeout "$health_timeout" --remove-orphans >>"$work/out" 2>&1 || return 1
  if ! body=$(curl -fsS --max-time 10 "$health_url" 2>>"$work/out"); then
    echo "GET $health_url failed" >>"$work/out"
    return 1
  fi
  built=$(printf '%s' "$body" | jq -r '.build.sha // "null"' 2>/dev/null) || built=unreadable
  [ "$built" = "$1" ] && return 0
  echo "GET $health_url reports build.sha $built, expected $1" >>"$work/out"
  return 1
}

digest_of() { sed -n 's/^CPRMV_IMAGE_DIGEST=//p' "$dir/releases/$1/.env"; }

# link_current <sha>: repoint `current` in one rename (GNU mv -T).
link_current() {
  rm -f "$dir/.current.tmp"
  ln -s "releases/$1" "$dir/.current.tmp"
  mv -fT "$dir/.current.tmp" "$dir/current"
}

# prune: drop every release, and its image tag, except running and previous.
prune() {
  keep1=$(jget .running.sha)
  keep2=$(jget .previous.sha)
  for r in "$dir"/releases/*; do
    [ -d "$r" ] || continue
    s=${r##*/}
    if [ "$s" = "$keep1" ] || [ "$s" = "$keep2" ]; then continue; fi
    rm -rf "$r"
    docker image rm "$image_repo:sha-$s" >/dev/null 2>&1 || true
  done
}

# keep_running: while the target is not deployed, re-apply the running release
# if compose reports it unhealthy. Only a warning either way: no commit is
# marked failed and last_attempt is left alone.
keep_running() {
  r=$(jget .running.sha)
  is_sha "$r" || return 0
  healthy "$r" && return 0
  if attempt "$r"; then
    link_current "$r"
    note="compose reported running release $r unhealthy; re-applied it"
  else
    note="compose reported running release $r unhealthy; re-applying it failed: $(tail -n 1 "$work/out")"
  fi
  warning="${warning:+$warning; }$note"
}

# wait_on_image: the target's image is not to be had yet. Waiting, and stalled
# after CPRMV_STALLED_AFTER seconds on the same target.
wait_on_image() {
  epoch=$(date +%s)
  if [ "$(jget .waiting.sha)" != "$target" ]; then
    jset --arg t "$target" --arg at "$(now)" --argjson e "$epoch" \
      '.waiting = {sha: $t, since: $at, since_epoch: $e}'
  fi
  since=$(jget .waiting.since_epoch)
  keep_running
  if [ $((epoch - ${since:-$epoch})) -ge "$stalled_after" ]; then
    finish stalled
  fi
  finish waiting
}

# deploy <target> [reapply]: apply it; on failure restore what ran before.
deploy() {
  target=$1
  why=${2:+compose reported release $target unhealthy or not running}
  at=$(now)
  old=$(jget .running.sha)
  is_sha "$old" || old=""
  if attempt "$target"; then
    if [ "$old" = "$target" ]; then
      jset --arg d "$(digest_of "$target")" '.running.digest = $d'
    else
      jset --arg t "$target" --arg d "$(digest_of "$target")" --arg at "$at" '
        .previous = (if .running then {sha: .running.sha, digest: .running.digest} else .previous end)
        | .running = {sha: $t, digest: $d, since: $at}'
    fi
    jset --arg t "$target" --arg at "$at" '.last_attempt = {sha: $t, result: "deployed", at: $at, error: null}'
    [ -z "$why" ] || warning="$why; re-applied it"
    link_current "$target"
    prune
    finish running
  fi

  error=$(tail -n 20 "$work/out")
  jset --arg t "$target" --arg at "$at" --arg e "$error" '
    .failed = (((.failed // []) - [$t]) + [$t])[-50:]
    | .last_attempt = {sha: $t, result: "failed", at: $at, error: $e}'

  # What to restore: the release that ran before this attempt, or, when the
  # attempt was a re-apply of the running release, the one before that.
  if [ -n "$old" ] && [ "$old" != "$target" ]; then
    cand=$old
  else
    cand=$(jget .previous.sha)
    [ "$cand" != "$target" ] || cand=""
  fi
  is_sha "$cand" || cand=""
  if [ -z "$cand" ]; then
    [ -z "$why" ] || warning="$why; re-applying it failed and there is no earlier release to restore"
    jset '.running = null'
    finish failed
  fi

  if attempt "$cand"; then
    if [ "$cand" != "$old" ]; then
      jset --arg c "$cand" --arg d "$(digest_of "$cand")" --arg at "$at" '
        .running = {sha: $c, digest: $d, since: $at} | .previous = null'
    fi
    jset '.last_attempt.result = "restored"'
    [ -z "$why" ] || warning="$why; re-applying it failed, restored $cand"
    link_current "$cand"
    prune
    finish failed
  fi
  warning="restore of $cand failed: $(tail -n 1 "$work/out")"
  jset --arg c "$cand" '.previous = {sha: $c, digest: (if .running.sha == $c then .running.digest else .previous.digest end)}
    | .running = null'
  finish broken
}

# 1. Fetch the branch head into repo/, a bare repository this script owns. An
# existing repository there (bare, or a clone) is used as it is.
export GIT_TERMINAL_PROMPT=0 GIT_HTTP_LOW_SPEED_LIMIT=1000 GIT_HTTP_LOW_SPEED_TIME=30
gd=$(git -C "$repo" rev-parse --git-dir 2>/dev/null) || gd=""
case $gd in . | .git) ;; *) git init -q --bare "$repo" ;; esac
if ! bounded 120 git -C "$repo" fetch -q --no-tags "$repo_url" \
  "+refs/heads/$branch:refs/remotes/origin/$branch" >"$work/fetch" 2>&1; then
  warning="fetch of $branch from $repo_url failed, nothing changed: $(tail -n 1 "$work/fetch")"
  st=$(jget .state)
  finish "${st:-waiting}"
fi
target=$(git -C "$repo" rev-parse --verify -q "refs/remotes/origin/$branch^{commit}")
if ! is_sha "$target"; then
  echo "$branch resolved to '$target', not a 40-character sha" >&2
  exit 1
fi

# Without the Docker daemon nothing can be judged: change nothing, say so.
if ! bounded 60 docker info >/dev/null 2>&1; then
  warning="docker daemon not reachable, nothing changed"
  st=$(jget .state)
  finish "${st:-waiting}"
fi
jset --arg t "$target" '.target = $t'

# 2. Nothing to do when the target runs and is healthy; re-apply it when not.
if [ "$target" = "$(jget .running.sha)" ]; then
  healthy "$target" && finish running
  deploy "$target" reapply
fi

# 3. A failed target is not retried; the fix is a new commit. What runs is
# still kept healthy.
if jq -e --arg t "$target" 'any(.failed[]?; . == $t)' "$state_file" >/dev/null; then
  keep_running
  [ "$(jget .state)" = broken ] && finish broken
  finish failed
fi

# 4. No image yet, or it cannot be pulled yet: waiting, then stalled.
docker manifest inspect "$image_repo:sha-$target" >/dev/null 2>&1 || wait_on_image
if ! docker pull -q "$image_repo:sha-$target" >"$work/pull" 2>&1; then
  warning="pull of sha-$target failed, retried next run: $(tail -n 1 "$work/pull")"
  wait_on_image
fi
jset '.waiting = null'

# 5-9. Prepare, apply, verify, record, prune, write the status.
deploy "$target"
