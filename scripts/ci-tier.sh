#!/bin/sh
# Maps a git ref to its deployment tier. Prints KEY=value lines, for appending
# to $GITHUB_OUTPUT. Exits non-zero for a ref that has no tier.
#   refs/heads/acc  -> acceptance tier
#   refs/heads/main -> stable tier
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: ci-tier.sh <git ref>" >&2
  exit 2
fi

case "$1" in
  refs/heads/acc)
    printf '%s\n' \
      'tier=acc' \
      'host=acc.cprmv.open-regels.nl' \
      'environment=acceptance' \
      'branch=acc'
    ;;
  refs/heads/main)
    printf '%s\n' \
      'tier=stable' \
      'host=cprmv.open-regels.nl' \
      'environment=stable' \
      'branch=main'
    ;;
  *)
    echo "ci-tier.sh: no tier for ref '$1'" >&2
    exit 1
    ;;
esac
