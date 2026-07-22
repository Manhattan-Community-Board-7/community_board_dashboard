#!/bin/sh
# Turn on a single Shelly output channel via the Cloud v2.0-beta API, to
# physically determine which channel (0 or 1) is wired to the CB office door
# relay. Mirrors shelly_door.py's trigger_door() but lets you pick the channel.
#
# Reads SHELLY_CLOUD_SERVER, SHELLY_CLOUD_AUTH_KEY, SHELLY_DEVICE_ID,
# SHELLY_DOOR_CHANNEL from door_scripts/.env (gitignored, not committed).
#
# Usage: ./trigger_shelly_channel.sh [channel-number]
#   Defaults to SHELLY_DOOR_CHANNEL from .env (currently 1, confirmed via
#   physical test on 2026-07-22) if no argument is given.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/.env"

CHANNEL="${1:-$SHELLY_DOOR_CHANNEL}"

curl -s -X POST "https://${SHELLY_CLOUD_SERVER}/v2/devices/api/set/switch?auth_key=${SHELLY_CLOUD_AUTH_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"id\":\"${SHELLY_DEVICE_ID}\",\"channel\":${CHANNEL},\"on\":true}"
echo
