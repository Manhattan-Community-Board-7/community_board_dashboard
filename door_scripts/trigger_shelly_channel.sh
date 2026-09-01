#!/bin/sh
# Turn on a single Shelly output channel via the Cloud v2.0-beta API. Mirrors
# shelly_door.py's trigger_door() but lets you pick which door.
#
# Reads SHELLY_CLOUD_AUTH_KEY and the per-door SHELLY_DEVICE_ID_* /
# SHELLY_CHANNEL_* vars from door_scripts/.env (gitignored, not committed).
#
# Usage: ./trigger_shelly_channel.sh [bottom|top]   (default: bottom)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/.env"

DOOR="${1:-bottom}"
case "$DOOR" in
  bottom) DEVICE_ID="$SHELLY_DEVICE_ID_BOTTOM"; CHANNEL="$SHELLY_CHANNEL_BOTTOM" ;;
  top)    DEVICE_ID="$SHELLY_DEVICE_ID_TOP";    CHANNEL="$SHELLY_CHANNEL_TOP" ;;
  *) echo "usage: $0 [bottom|top]" >&2; exit 1 ;;
esac

SHELLY_CLOUD_SERVER="shelly-212-eu.shelly.cloud"  # not sensitive, hardcoded

curl -s -X POST "https://${SHELLY_CLOUD_SERVER}/v2/devices/api/set/switch?auth_key=${SHELLY_CLOUD_AUTH_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"id\":\"${DEVICE_ID}\",\"channel\":${CHANNEL},\"on\":true}"
echo
