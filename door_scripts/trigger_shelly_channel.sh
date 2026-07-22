#!/bin/sh
# Turn on a single Shelly output channel via the Cloud v2.0-beta API. Mirrors
# shelly_door.py's trigger_door() but lets you pick the channel.
#
# Reads SHELLY_CLOUD_AUTH_KEY, SHELLY_DEVICE_ID from door_scripts/.env
# (gitignored, not committed).
#
# Usage: ./trigger_shelly_channel.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/.env"

SHELLY_CLOUD_SERVER="shelly-212-eu.shelly.cloud"  # not sensitive, hardcoded
CHANNEL="1"  # downstairs door relay, confirmed via physical test 2026-07-22

curl -s -X POST "https://${SHELLY_CLOUD_SERVER}/v2/devices/api/set/switch?auth_key=${SHELLY_CLOUD_AUTH_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"id\":\"${SHELLY_DEVICE_ID}\",\"channel\":${CHANNEL},\"on\":true}"
echo
