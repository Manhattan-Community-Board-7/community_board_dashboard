import boto3
import pytz
from datetime import datetime, timedelta

import shelly_door

# Kept separate from VoteLoggingClass/main.py's voting path so this
# door-specific plumbing doesn't get tangled up with vote logic -- same
# reasoning shelly_door.py itself lives on its own.
DATA_BUCKET = 'cb7-dashboard-data-store'
RAW_LOG_FOLDER = 'rawvotelog/'
RAW_LOG_TIMESTAMP_FORMAT = '%Y_%m_%d_%H:%M:%S'

_s3_resource = boto3.resource('s3')


def get_door_log(community_board, days=30):
    """
    Returns every "door" text sent in the last `days`, oldest first, as
    [{'from': sms_number, 'timestamp': 'YYYY_MM_DD_HH:MM:SS'}, ...].
    Reads the same rawvotelog objects VoteLoggingClass.log_raw_vote_to_file
    writes for every incoming text (door command or vote), filtered down to
    just door commands. Object keys are '{timestamp}_{number}.txt' with a
    zero-padded timestamp, so lexicographic key order is chronological
    order -- used here as a Marker cutoff to avoid listing the whole
    history.
    """
    eastern = pytz.timezone('America/New_York')
    cutoff = datetime.now(eastern) - timedelta(days=days)
    prefix = RAW_LOG_FOLDER + community_board + '/'
    start_after = prefix + cutoff.strftime(RAW_LOG_TIMESTAMP_FORMAT)

    entries = []
    try:
        bucket = _s3_resource.Bucket(DATA_BUCKET)
        # bucket.objects.filter() maps to the older ListObjects (not
        # ListObjectsV2), whose equivalent of StartAfter is Marker.
        for obj_summary in bucket.objects.filter(Prefix=prefix, Marker=start_after):
            body = obj_summary.get()['Body'].read().decode('utf-8').strip()
            parts = body.split(',', 3)
            if len(parts) < 3:
                continue
            timestamp, sms_number, message = parts[0], parts[1], parts[2]
            if not shelly_door.is_door_command(message):
                continue
            entries.append({'from': sms_number, 'timestamp': timestamp})
    except Exception as e:
        print(f"Error listing door log: {str(e)}")

    entries.sort(key=lambda e: e['timestamp'])
    return entries
