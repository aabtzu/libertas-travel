#!/usr/bin/env bash
# launch-stats.sh — quick health + usage report for the prod app.
#
# Reads SECRET_KEY from the env (export it before running) and hits
# /api/debug on the production app. Pipes through jq for a friendly
# summary.
#
# Usage:
#   export SECRET_KEY='<the-X-Admin-Key-from-Render>'
#   ./scripts/launch-stats.sh
#   ./scripts/launch-stats.sh --raw       # full JSON dump
#   ./scripts/launch-stats.sh --staging   # use a different host
#
# Requires: curl, jq.

set -euo pipefail

HOST="${LIBERTAS_HOST:-https://libertas-travel.onrender.com}"
RAW=0

for arg in "$@"; do
  case "$arg" in
    --raw)     RAW=1 ;;
    --staging) HOST="https://libertas-travel-staging.onrender.com" ;;
    --host=*)  HOST="${arg#--host=}" ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0 ;;
    *)
      echo "Unknown arg: $arg" >&2
      exit 1 ;;
  esac
done

if [ -z "${SECRET_KEY:-}" ]; then
  echo "ERROR: SECRET_KEY is not set." >&2
  echo "  export SECRET_KEY='<your X-Admin-Key from Render dashboard>'" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required (brew install jq)." >&2
  exit 1
fi

resp=$(curl -fsS -H "X-Admin-Key: $SECRET_KEY" "$HOST/api/debug" || true)

if [ -z "$resp" ]; then
  echo "ERROR: empty response from $HOST/api/debug — check the host and SECRET_KEY." >&2
  exit 1
fi

if [ "$RAW" -eq 1 ]; then
  echo "$resp" | jq .
  exit 0
fi

echo "$resp" | jq -r '
  "=== Libertas — \(.cwd // "prod") ===",
  "",
  "Totals:",
  "  Users:  \(.users_count // "?")",
  "  Trips:  \(.trips_count // "?")",
  "  Venues: \(.venue_count // "?")",
  "",
  "Last 24 hours:",
  "  New users: \(.new_users_24h // 0)",
  "  New trips: \(.new_trips_24h // 0)",
  "",
  "Recent signups:",
  (.recent_users // [] | if length == 0 then "  (none)" else
    map("  • \(.username)  (\(.email))  \(.created_at)")[]
  end),
  "",
  "Recent trips:",
  (.trips // [] | if length == 0 then "  (none)" else
    map("  • [user \(.user_id)] \(.title)  →  /\(.link)  \(.created_at)")[]
  end),
  ""
'
