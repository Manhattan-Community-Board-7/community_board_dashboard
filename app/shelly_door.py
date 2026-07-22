import os
import json
import urllib3

# Shelly Cloud config for the office door relay (Shelly Plus Uni).
# These are read from Lambda env vars (same pattern as TWILIO_API_KEY/API_KEY
# in lambda_app.py) and are not committed anywhere.
SHELLY_CLOUD_SERVER = os.environ.get('SHELLY_CLOUD_SERVER')  # e.g. "shelly-212-eu.shelly.cloud"
SHELLY_CLOUD_AUTH_KEY = os.environ.get('SHELLY_CLOUD_AUTH_KEY')
SHELLY_DEVICE_ID = os.environ.get('SHELLY_DEVICE_ID')
# Confirmed via physical test 2026-07-22: channel 1 drives the door relay.
SHELLY_DOOR_CHANNEL = os.environ.get('SHELLY_DOOR_CHANNEL', '1')

DOOR_TRIGGERED_MESSAGE = 'Door is unlocked. Please enter within 15s and close it behind you.'
DOOR_ERROR_MESSAGE = 'Could not trigger the door right now. Please contact the board office.'

_http = urllib3.PoolManager()


def is_door_command(incoming_msg):
    return incoming_msg.strip().lower() == 'door'


def trigger_door():
    """Calls the Shelly Cloud v2 API to pulse the office door relay. Returns True on success."""
    try:
        response = _http.request(
            'POST',
            f'https://{SHELLY_CLOUD_SERVER}/v2/devices/api/set/switch?auth_key={SHELLY_CLOUD_AUTH_KEY}',
            body=json.dumps({
                'id': SHELLY_DEVICE_ID,
                'channel': int(SHELLY_DOOR_CHANNEL),
                'on': True,
            }),
            headers={'Content-Type': 'application/json'},
            timeout=5.0,
        )
        return response.status == 200
    except Exception as e:
        print(f"Error triggering Shelly door relay: {str(e)}")
        return False
