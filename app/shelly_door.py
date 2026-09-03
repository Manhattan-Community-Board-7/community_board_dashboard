import os
import json
import urllib3

# Shelly Cloud config for the office door relays.
# The auth key and device ids are read from Lambda env vars (same pattern as
# TWILIO_API_KEY/API_KEY in lambda_app.py) and are not committed anywhere.
SHELLY_CLOUD_SERVER = 'shelly-212-eu.shelly.cloud'  # not sensitive, hardcoded
SHELLY_CLOUD_AUTH_KEY = os.environ.get('SHELLY_CLOUD_AUTH_KEY')

# Bottom door - Shelly Plus Uni. Channel 1 drives this relay, confirmed via
# physical test 2026-07-22. Device id stays in the original SHELLY_DEVICE_ID
# env var (unchanged, so no redeploy config churn for the existing door).
BOTTOM_DOOR = {
    'name': 'bottom',
    'device_id': os.environ.get('SHELLY_DEVICE_ID'),
    'channel': 1,
}
# Top door - the door at the top of the elevators. Shelly 1 Gen 4
# (S4SW-001X16EU), a single-relay device on channel 0. Added 2026-09; its
# device id is in the SHELLY_TOP_DEVICE_ID env var.
TOP_DOOR = {
    'name': 'top',
    'device_id': os.environ.get('SHELLY_TOP_DEVICE_ID'),
    'channel': 0,
}

_DOORS = {'bottom': BOTTOM_DOOR, 'top': TOP_DOOR}

BOTTOM_DOOR_TRIGGERED_MESSAGE = (
    "Bottom door is unlocked. Please enter within 15s and close it behind you. "
    "Text 'top door' to unlock the door at the top of the elevators."
)
TOP_DOOR_TRIGGERED_MESSAGE = (
    'Top door is unlocked. Please enter within 15s and close it behind you.'
)
DOOR_ERROR_MESSAGE = 'Could not trigger the door right now. Please contact the board office.'
DOOR_UNKNOWN_MESSAGE = "Unknown door command. Text 'bottom door' or 'top door'."

_TRIGGERED_MESSAGES = {
    'bottom': BOTTOM_DOOR_TRIGGERED_MESSAGE,
    'top': TOP_DOOR_TRIGGERED_MESSAGE,
}

_http = urllib3.PoolManager()


def _normalize(incoming_msg):
    """Lower-cased, outer whitespace stripped, internal runs collapsed to one space."""
    return ' '.join(incoming_msg.strip().lower().split())


def is_door_command(incoming_msg):
    """True for any door-unlock text: 'door', 'bottom door', 'top door', or an
    invalid 'door' variant like 'door foo'. Routes incoming texts in
    parse_incoming_text; door_scripts/backfill_door_log.py mirrors this logic
    to pull historical door texts out of the raw vote log."""
    n = _normalize(incoming_msg)
    return n == 'door' or n.startswith('door ') or n.endswith(' door')


def door_target(incoming_msg):
    """For a message where is_door_command() is True, return which door to
    unlock: 'bottom' ('door' or 'bottom door'), 'top' ('top door'), or None
    when the door name is anything else."""
    n = _normalize(incoming_msg)
    if n in ('door', 'bottom door'):
        return 'bottom'
    if n == 'top door':
        return 'top'
    return None


def triggered_message(target):
    """The SMS reply to send after successfully unlocking `target`."""
    return _TRIGGERED_MESSAGES[target]


def trigger_door(target):
    """Calls the Shelly Cloud v2 API to pulse the given door's relay
    ('bottom' or 'top'). Returns True on success."""
    door = _DOORS[target]
    try:
        response = _http.request(
            'POST',
            f'https://{SHELLY_CLOUD_SERVER}/v2/devices/api/set/switch?auth_key={SHELLY_CLOUD_AUTH_KEY}',
            body=json.dumps({
                'id': door['device_id'],
                'channel': door['channel'],
                'on': True,
            }),
            headers={'Content-Type': 'application/json'},
            timeout=5.0,
        )
        response_body = response.data.decode('utf-8')
        print(f"Shelly {target} door trigger response: status={response.status} body={response_body}")
        # Shelly's v2 set/switch endpoint returns HTTP 200 with an empty body on
        # success (confirmed via CloudWatch logs 2026-07-28) rather than a JSON
        # {"isok": true} payload, so status alone is the success signal.
        return response.status == 200
    except Exception as e:
        print(f"Error triggering Shelly {target} door relay: {str(e)}")
        return False
