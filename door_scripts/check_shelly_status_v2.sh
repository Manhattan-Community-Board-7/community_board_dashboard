#!/bin/sh
# Read-only check of a CB office door Shelly's current status via the Shelly
# Cloud v2.0-beta API. Does not change any relay/switch state.
#
# Reads SHELLY_CLOUD_AUTH_KEY and the per-door SHELLY_DEVICE_ID_* vars from
# door_scripts/.env (gitignored, not committed).
#
# Usage: ./check_shelly_status_v2.sh [bottom|top]   (default: bottom)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/.env"

DOOR="${1:-bottom}"
case "$DOOR" in
  bottom) DEVICE_ID="$SHELLY_DEVICE_ID_BOTTOM" ;;
  top)    DEVICE_ID="$SHELLY_DEVICE_ID_TOP" ;;
  *) echo "usage: $0 [bottom|top]" >&2; exit 1 ;;
esac

SHELLY_CLOUD_SERVER="shelly-212-eu.shelly.cloud"  # not sensitive, hardcoded

curl -s -X POST "https://${SHELLY_CLOUD_SERVER}/v2/devices/api/get?auth_key=${SHELLY_CLOUD_AUTH_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"ids\":[\"${DEVICE_ID}\"],\"select\":[\"status\"]}"
echo
