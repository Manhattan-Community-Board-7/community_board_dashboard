import json

import boto3
import pytz
from datetime import datetime, timedelta

# Kept separate from VoteLoggingClass/main.py's voting path so this
# door-specific plumbing doesn't get tangled up with vote logic -- same
# reasoning shelly_door.py itself lives on its own.
DATA_BUCKET = 'cb7-dashboard-data-store'
DOOR_LOG_FOLDER = 'doorlog/'
TIMESTAMP_FORMAT = '%Y_%m_%d_%H:%M:%S'

_s3_resource = boto3.resource('s3')


def record_door_event(community_board, sms_number, raw_message, door, triggered):
    """
    Writes one JSON object per incoming door text to
    'doorlog/{board}/{timestamp}_{number}.txt'. Called from
    parse_incoming_text for every door command -- valid or not -- so the
    /door page is a full audit trail, including failed and unrecognized
    attempts.

    Best-effort: a logging failure must never break the SMS reply, so all
    exceptions are swallowed (same stance as VoteLoggingClass).

    Fields:
      timestamp  '%Y_%m_%d_%H:%M:%S' Eastern, matches the object key
      from       sender's SMS number
      raw        exactly what they texted ('Door', 'Top door', 'door foo')
      door       normalized target: 'bottom' / 'top' / 'unknown'
      triggered  True/False -- did the Shelly relay actually fire
    """
    eastern = pytz.timezone('America/New_York')
    timestamp = datetime.now(eastern).strftime(TIMESTAMP_FORMAT)
    key = DOOR_LOG_FOLDER + community_board + '/' + timestamp + '_' + sms_number + '.txt'
    record = {
        'timestamp': timestamp,
        'from': sms_number,
        'raw': raw_message,
        'door': door if door in ('bottom', 'top') else 'unknown',
        'triggered': bool(triggered),
    }
    try:
        _s3_resource.Object(DATA_BUCKET, key).put(Body=json.dumps(record))
    except Exception as e:
        print(f"Error writing door log entry: {str(e)}")


def get_door_log(community_board, days=30):
    """
    Returns every door text from the last `days`, oldest first, as
    [{'from', 'timestamp', 'door', 'raw', 'triggered'}, ...].

    Reads only the dedicated 'doorlog/{board}/' objects record_door_event
    writes -- a few dozen a month -- rather than scanning the raw vote log
    (every incoming text, thousands per meeting month) and throwing almost
    all of it away. Object keys are '{timestamp}_{number}.txt' with a
    zero-padded timestamp, so lexicographic key order is chronological
    order -- used here as a Marker cutoff to skip older objects entirely.

    Entries before the doorlog cutover (2026-09, backfilled by
    door_scripts/backfill_door_log.py) have triggered=None (the Shelly
    outcome was never recorded then) and, for bare 'door' texts,
    door='bottom' (the only door back then).
    """
    eastern = pytz.timezone('America/New_York')
    cutoff = datetime.now(eastern) - timedelta(days=days)
    prefix = DOOR_LOG_FOLDER + community_board + '/'
    start_after = prefix + cutoff.strftime(TIMESTAMP_FORMAT)

    entries = []
    try:
        bucket = _s3_resource.Bucket(DATA_BUCKET)
        # bucket.objects.filter() maps to the older ListObjects (not
        # ListObjectsV2), whose equivalent of StartAfter is Marker.
        for obj_summary in bucket.objects.filter(Prefix=prefix, Marker=start_after):
            body = obj_summary.get()['Body'].read().decode('utf-8')
            try:
                record = json.loads(body)
            except ValueError:
                print(f"Skipping unparseable door log object: {obj_summary.key}")
                continue
            entries.append({
                'from': record.get('from'),
                'timestamp': record.get('timestamp'),
                'door': record.get('door', 'unknown'),
                'raw': record.get('raw', ''),
                # True / False for live events; None for backfilled ones
                # where the Shelly outcome was never recorded.
                'triggered': record.get('triggered'),
            })
    except Exception as e:
        print(f"Error listing door log: {str(e)}")

    entries.sort(key=lambda e: e['timestamp'])
    return entries
