#!/usr/bin/env bash
# Keep the SQLite state outside main's history.
#
# The database lives as the single file of a single-commit branch `data-store`, which
# is force-pushed after every run. Main's history no longer grows by a binary snapshot
# per day, and old snapshots become unreachable instead of accumulating.
#
#   scripts/db_store.sh restore   # before the crawl
#   scripts/db_store.sh save      # after the crawl (needs contents: write)
set -euo pipefail

DB="${OPPORTUNITY_RADAR_DB:-data/opportunities.sqlite3}"
BRANCH="${OPPOR_DATA_BRANCH:-data-store}"
FILE="opportunities.sqlite3"

restore() {
  mkdir -p "$(dirname "$DB")"
  # Distinguish "branch does not exist" (exit 2) from a network/auth failure: on a
  # failure we must stop, otherwise a fresh database would be saved over the real one.
  set +e
  git ls-remote --exit-code --heads origin "$BRANCH" > /dev/null
  status=$?
  set -e
  if [ "$status" -eq 0 ]; then
    git fetch --quiet --depth=1 origin "$BRANCH"
    git show "FETCH_HEAD:$FILE" > "$DB"
    echo "Restored $DB from $BRANCH ($(wc -c < "$DB") bytes)"
    return
  fi
  if [ "$status" -ne 2 ]; then
    echo "Could not query origin for $BRANCH (exit $status); refusing to continue" >&2
    exit 1
  fi
  if [ -f "$DB" ]; then
    echo "No $BRANCH branch yet; using the $DB present in the checkout"
    return
  fi
  # One-time migration: main used to track the database. Recover its last version.
  git fetch --quiet --depth=100 origin main || true
  rev="$(git rev-list -n 1 FETCH_HEAD -- "$DB" 2>/dev/null || true)"
  if [ -n "$rev" ] && git show "$rev^:$DB" > "$DB" 2>/dev/null; then
    echo "Recovered $DB from main history ($rev^)"
  else
    rm -f "$DB"
    echo "No previous database found; starting fresh"
  fi
}

save() {
  if [ ! -f "$DB" ]; then
    echo "Nothing to save: $DB does not exist" >&2
    exit 1
  fi
  blob="$(git hash-object -w "$DB")"
  tree="$(printf '100644 blob %s\t%s\n' "$blob" "$FILE" | git mktree)"
  commit="$(git commit-tree "$tree" -m "data: sqlite snapshot $(date -u +%Y-%m-%dT%H:%M:%SZ)")"
  git push --quiet --force origin "$commit:refs/heads/$BRANCH"
  echo "Saved $DB to $BRANCH ($commit)"
}

case "${1:-}" in
  restore) restore ;;
  save) save ;;
  *) echo "usage: $0 restore|save" >&2; exit 2 ;;
esac
