#!/usr/bin/env python3
"""
Quick audit trail for "door" text messages: pulls incoming SMS records
straight from the S3 raw-vote-log (main.py's parse_incoming_text writes one
object there for every incoming text -- vote or not -- before any routing
happens, so it has the sender number regardless of what CloudWatch does or
doesn't log), filters down to just the "door" commands, and pairs each one
with Shelly's API response pulled from CloudWatch logs.

CloudWatch used to be the primary source here (the old hand-rolled
lambda_app.py printed the raw event on every invocation), but the
apig-wsgi migration (aca874c, 2026-08-04) dropped that print and nothing
replaced it -- CloudWatch no longer has the incoming From/Body at all.
The S3 raw-vote-log doesn't depend on that print and has always had it.

Not a production feature -- just a diagnostic script for while we're
validating this. Requires the `mcb7` AWS CLI profile.

Usage: ./view_door_texts.py [--since 6h] [--board 7]
"""
import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import boto3

LOG_GROUP = "/aws/lambda/CBFunction"
PROFILE = "mcb7"
REGION = "us-east-1"
DATA_BUCKET = "cb7-dashboard-data-store"
RAW_LOG_TIMESTAMP_FORMAT = "%Y_%m_%d_%H:%M:%S"
RAW_LOG_TZ = ZoneInfo("America/New_York")  # matches VoteLoggingClass.get_time_stamp_with_seconds()

# Shelly's response normally lands ~1s after the triggering text; give it
# some slack for slow API calls without accidentally pairing across two
# unrelated door commands sent close together.
SHELLY_PAIRING_WINDOW_SECONDS = 15

DURATION_RE = re.compile(r'^(\d+)([smhdw])$')
DURATION_UNIT_SECONDS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}


def is_door_command(body):
    # Mirrors app/shelly_door.is_door_command: 'door', 'bottom door',
    # 'top door', or an invalid 'door ...' variant.
    n = ' '.join(body.strip().lower().split())
    return n == 'door' or n.startswith('door ') or n.endswith(' door')


def parse_since(since):
    match = DURATION_RE.match(since.strip())
    if not match:
        raise SystemExit(f"--since must look like '30m', '6h', '2d', etc. (got {since!r})")
    amount, unit = int(match.group(1)), match.group(2)
    return timedelta(seconds=amount * DURATION_UNIT_SECONDS[unit])


def fetch_members(community_board):
    session = boto3.Session(profile_name=PROFILE)
    s3 = session.client('s3')
    key = f'/{community_board}/members.json'
    obj = s3.get_object(Bucket=DATA_BUCKET, Key=key)
    members = json.loads(obj['Body'].read().decode('utf-8'))
    return {sms_number: info['name'] for sms_number, info in members.items()}


def fetch_door_texts(community_board, since_delta):
    """
    Pulls every "door" text sent within the last `since_delta`. Object keys
    are 'rawvotelog/{board}/{timestamp}_{number}.txt' with a zero-padded
    timestamp, so lexicographic key order is chronological order -- used
    here as a StartAfter cutoff so we don't have to list the whole history.
    """
    session = boto3.Session(profile_name=PROFILE)
    s3 = session.client('s3')
    prefix = f'rawvotelog/{community_board}/'

    cutoff_et = (datetime.now(timezone.utc) - since_delta).astimezone(RAW_LOG_TZ)
    start_after = prefix + cutoff_et.strftime(RAW_LOG_TIMESTAMP_FORMAT)

    keys = []
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=DATA_BUCKET, Prefix=prefix, StartAfter=start_after):
        keys.extend(obj['Key'] for obj in page.get('Contents', []))
    keys.sort()

    texts = []
    for key in keys:
        obj = s3.get_object(Bucket=DATA_BUCKET, Key=key)
        line = obj['Body'].read().decode('utf-8').strip()
        # Written by VoteLoggingClass.log_raw_vote_to_file as:
        #   "{timestamp},{incoming_number},{incoming_msg},{current_vote_name}"
        parts = line.split(',', 3)
        if len(parts) < 3:
            continue
        raw_timestamp, number, body = parts[0], parts[1], parts[2]
        if not is_door_command(body):
            continue
        try:
            local_dt = datetime.strptime(raw_timestamp, RAW_LOG_TIMESTAMP_FORMAT).replace(tzinfo=RAW_LOG_TZ)
        except ValueError:
            continue
        texts.append({
            'timestamp_et': raw_timestamp,
            'utc': local_dt.astimezone(timezone.utc),
            'from': number,
            'body': body,
        })

    texts.sort(key=lambda t: t['utc'])
    return texts


def fetch_shelly_responses(since):
    result = subprocess.run(
        [
            "aws", "logs", "tail", LOG_GROUP,
            "--profile", PROFILE,
            "--region", REGION,
            "--since", since,
            "--filter-pattern", '"Shelly door trigger response"',
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    responses = []
    for line in result.stdout.splitlines():
        if "Shelly door trigger response" not in line:
            continue
        raw_timestamp = line.split()[0] if line else ''
        try:
            utc = datetime.fromisoformat(raw_timestamp).astimezone(timezone.utc)
        except ValueError:
            continue
        text = line.split("Shelly door trigger response:", 1)[1].strip()
        responses.append({'utc': utc, 'text': text})
    responses.sort(key=lambda r: r['utc'])
    return responses


def pair_shelly_response(door_text, unused_responses):
    """Finds and consumes the nearest not-yet-used Shelly response that
    followed this door text within SHELLY_PAIRING_WINDOW_SECONDS."""
    best = None
    for response in unused_responses:
        delta = (response['utc'] - door_text['utc']).total_seconds()
        if 0 <= delta <= SHELLY_PAIRING_WINDOW_SECONDS:
            if best is None or response['utc'] < best['utc']:
                best = response
    if best:
        unused_responses.remove(best)
    return best


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--since', default='6h', help='How far back to look, e.g. 1h, 6h, 2d (default: 6h)')
    parser.add_argument('--board', default='7', help='Community board number for the members list and raw log (default: 7)')
    args = parser.parse_args()

    since_delta = parse_since(args.since)
    members = fetch_members(args.board)
    texts = fetch_door_texts(args.board, since_delta)

    if not texts:
        print(f"No door texts found for board {args.board} in the last {args.since}.")
        return

    shelly_responses = fetch_shelly_responses(args.since)

    for text in texts:
        name = members.get(text['from'], 'Unknown')
        print(f"{text['timestamp_et']}  IN   from={text['from']} ({name})  body={text['body']!r}")
        response = pair_shelly_response(text, shelly_responses)
        if response:
            print(f"{'':>19}  SHELLY  {response['text']}")
        else:
            print(f"{'':>19}  SHELLY  (no matching response found in CloudWatch)")


if __name__ == '__main__':
    main()
