#!/bin/sh
# Waits until the tier's VM reports, in its public deploy-status.json, that
# it runs <sha>. Run by the deploy job of ci.yml after the image is pushed.
#
# Usage: wait-for-deploy.sh <status_url> <sha> <repo_url> <branch> <health_url>
# Env:   WAIT_TIMEOUT   seconds to wait before giving up (default 900)
#        WAIT_INTERVAL  seconds between polls (default 20)
# Needs: curl, jq and git on PATH. The URLs may be file:// URLs.
# Exit:  0 deployed: state is not broken, the status reports running.sha ==
#          <sha>, and <health_url> reports build.sha == <sha>; or <branch> no
#          longer points at <sha> ("superseded": a newer commit will be
#          deployed instead);
#        1 state is broken, this sha failed or was restored, or timed out;
#        2 bad usage.
# A status or health response that cannot be fetched or parsed, a build.sha
# that does not match yet, or a failing ls-remote, is not a verdict: polling
# continues.
set -u

usage() {
  echo "usage: $0 <status_url> <sha> <repo_url> <branch> <health_url>" >&2
  exit 2
}

[ "$#" -eq 5 ] || usage
url=$1
sha=$2
repo=$3
branch=$4
health=$5
timeout=${WAIT_TIMEOUT:-900}
interval=${WAIT_INTERVAL:-20}
case $timeout in '' | *[!0-9]*) usage ;; esac
case $interval in '' | *[!0-9]*) usage ;; esac

# clean <text>: drop control characters (newlines, CR, ...), so a value taken
# from a status cannot start a line of its own, such as a workflow command.
clean() {
  printf '%s' "$1" | tr -d '\000-\037\177'
}

# fail <message>: say so, and as a workflow annotation on GitHub Actions.
fail() {
  echo "$1"
  [ "${GITHUB_ACTIONS:-}" = "true" ] && echo "::error::$1"
  exit 1
}

# remote_head: ls-remote bounded in time, so a stalled server cannot outlast
# WAIT_TIMEOUT.
remote_head() {
  export GIT_TERMINAL_PROMPT=0 GIT_HTTP_LOW_SPEED_LIMIT=1000 GIT_HTTP_LOW_SPEED_TIME=15
  if command -v timeout >/dev/null 2>&1; then
    timeout 20 git ls-remote "$repo" "refs/heads/$branch"
  else
    git ls-remote "$repo" "refs/heads/$branch"
  fi
}

start=$(date +%s)
last="no status fetched yet"

while :; do
  if body=$(curl -fsS --max-time 15 "$url" 2>/dev/null) &&
    fields=$(printf '%s' "$body" | jq -r '[
      (.state // ""),
      (.running.sha // ""),
      (.last_attempt.sha // ""),
      (.last_attempt.result // "")
    ] | map(tostring) | join("|")' 2>/dev/null); then
    IFS='|' read -r state running attempt_sha result <<EOF
$fields
EOF
    last="state $(clean "${state:-unknown}"), running $(clean "${running:-none}")"

    if [ "$state" = broken ]; then
      fail "the VM reports state broken; nothing reliable runs and it needs a person; see $url"
    fi
    if [ "$attempt_sha" = "$sha" ] && { [ "$result" = failed ] || [ "$result" = restored ]; }; then
      fail "deploy of $sha failed on the VM (result: $(clean "$result")); see $url"
    fi
    if [ "$running" = "$sha" ]; then
      if hbody=$(curl -fsS --max-time 15 "$health" 2>/dev/null) &&
        built=$(printf '%s' "$hbody" | jq -r '.build.sha // "" | tostring' 2>/dev/null); then
        if [ "$built" = "$sha" ]; then
          echo "deployed: $url reports running $sha and $health agrees"
          exit 0
        fi
        last="$last; health at $health reports build $(clean "${built:-none}"), not $sha"
      else
        last="$last; health at $health not readable"
      fi
    fi
  else
    last="status at $url not readable"
  fi

  if head=$(remote_head 2>/dev/null); then
    new=$(clean "${head%%[[:space:]]*}")
    if [ -n "$new" ] && [ "$new" != "$sha" ]; then
      echo "superseded by $new: $branch moved on, so $sha will not be deployed"
      exit 0
    fi
  fi

  if [ $(($(date +%s) - start)) -ge "$timeout" ]; then
    fail "timed out after ${timeout}s waiting for $url to report $sha; last seen: $last"
  fi
  echo "waiting for $sha ($last)"
  sleep "$interval"
done
