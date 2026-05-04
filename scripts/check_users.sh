#!/bin/bash
# Print signup + trip activity from Render production.
#
# Reads SECRET_KEY from ~/.profile (where prod secrets live).
# Pass --raw to see the full JSON dump instead of the summary.
#
# Examples:
#   scripts/check_users.sh           # summary
#   scripts/check_users.sh --raw     # full debug payload

set -e

URL="${LIBERTAS_URL:-https://libertas-travel.onrender.com}"

# Source ~/.profile from $HOME so its relative `source .bash_aliases`
# resolves. Subshell isolates any env changes from the rest of the script.
SECRET_KEY=$(cd "$HOME" && bash -c 'source ./.profile >/dev/null 2>&1; printf "%s" "${SECRET_KEY:-}"')
export SECRET_KEY

if [ -z "${SECRET_KEY:-}" ]; then
  echo "SECRET_KEY not set. Add it to ~/.profile." >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required (brew install jq)." >&2
  exit 1
fi

response=$(curl -fsS -H "X-Admin-Key: $SECRET_KEY" "$URL/api/debug")

if [ "${1:-}" = "--raw" ]; then
  echo "$response" | jq .
  exit 0
fi

echo "$response" | jq '{
  totals: {
    users: .users_count,
    trips: .trips_count
  },
  last_24h: {
    new_users: .new_users_24h,
    new_trips: .new_trips_24h
  },
  recent_users: .recent_users,
  recent_trips: .trips
}'
