#!/bin/sh
# Starts an image, waits for GET /health, and checks that it reports the commit
# it was built from. Run by the build job against the local image and again
# against the pushed one.
#
# Usage: smoke-health.sh <image-ref> <expected-sha>
# Env:   SMOKE_TIMEOUT  seconds to wait for /health (default 60)
# Needs: docker and jq on PATH. The container (cprmv-smoke) is always removed.
# Exit:  0 healthy and build.sha == <expected-sha>; 1 no answer in time or a
#        different build.sha (null included); 2 bad usage.
set -u

[ "$#" -eq 2 ] || {
  echo "usage: $0 <image-ref> <expected-sha>" >&2
  exit 2
}
image=$1
expected=$2
timeout=${SMOKE_TIMEOUT:-60}
case $timeout in '' | *[!0-9]*)
  echo "usage: SMOKE_TIMEOUT must be a number of seconds" >&2
  exit 2
  ;;
esac

docker run -d --name cprmv-smoke "$image" >/dev/null || exit 1
trap 'docker rm -f cprmv-smoke >/dev/null 2>&1' EXIT

body=
deadline=$(($(date +%s) + timeout))
while :; do
  if body=$(docker exec cprmv-smoke python -c \
    "from urllib.request import urlopen; print(urlopen('http://localhost:8000/health', timeout=5).read().decode())" 2>/dev/null); then
    break
  fi
  body=
  [ "$(date +%s)" -lt "$deadline" ] || break
  sleep 2
done

if [ -z "$body" ]; then
  echo "::error::/health did not answer within $timeout seconds"
  docker logs cprmv-smoke
  exit 1
fi

echo "$body"
actual=$(printf '%s' "$body" | jq -r '.build.sha')
if [ "$actual" != "$expected" ]; then
  echo "::error::build.sha is '$actual', expected '$expected'"
  exit 1
fi
echo "ok: $image reports build.sha $actual"
