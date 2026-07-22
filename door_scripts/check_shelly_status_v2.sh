#!/bin/sh
# Read-only check of the CB office door Shelly Plus Uni's current status via the
# Shelly Cloud v2.0-beta API. Does not change any relay/switch state.
#
# Reads SHELLY_CLOUD_AUTH_KEY, SHELLY_DEVICE_ID from door_scripts/.env
# (gitignored, not committed).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/.env"

SHELLY_CLOUD_SERVER="shelly-212-eu.shelly.cloud"  # not sensitive, hardcoded

curl -s -X POST "https://${SHELLY_CLOUD_SERVER}/v2/devices/api/get?auth_key=${SHELLY_CLOUD_AUTH_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"ids\":[\"${SHELLY_DEVICE_ID}\"],\"select\":[\"status\"]}"
echo
