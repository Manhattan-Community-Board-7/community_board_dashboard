#!/usr/bin/env python3
"""
Quick audit trail for "door" text messages: pulls recent CBFunction Lambda
logs from CloudWatch, decodes incoming Twilio SMS bodies, and prints a
timeline of who texted "door" and what Shelly's API actually said back.

Not a production feature -- just a diagnostic script for while we're
validating this. Requires the `mcb7` AWS CLI profile.

Usage: ./view_door_texts.py [--since 6h]
"""
import argparse
import base64
import json
import re
import subprocess
from urllib.parse import parse_qs

import boto3

LOG_GROUP = "/aws/lambda/CBFunction"
PROFILE = "mcb7"
REGION = "us-east-1"
MEMBERS_BUCKET = "cb7-dashboard-data-store"


def fetch_log_lines(since):
    result = subprocess.run(
        [
            "aws", "logs", "tail", LOG_GROUP,
            "--profile", PROFILE,
            "--region", REGION,
            "--since", since,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()


def extract_incoming_text(line):
    if "/default/incomingtext" not in line:
        return None
    match = re.search(r"'body': '([^']+)'", line)
    if not match:
        return None
    decoded = base64.b64decode(match.group(1)).decode('utf-8')
    params = parse_qs(decoded)
    return {
        'from': params.get('From', [''])[0],
        'body': params.get('Body', [''])[0],
        'city': params.get('FromCity', [''])[0],
    }


def extract_shelly_response(line):
    if "Shelly door trigger response" not in line:
        return None
    return line.split("Shelly door trigger response:", 1)[1].strip()


def fetch_members(community_board):
    session = boto3.Session(profile_name=PROFILE)
    s3 = session.client('s3')
    key = f'/{community_board}/members.json'
    obj = s3.get_object(Bucket=MEMBERS_BUCKET, Key=key)
    members = json.loads(obj['Body'].read().decode('utf-8'))
    return {sms_number: info['name'] for sms_number, info in members.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--since', default='6h', help='How far back to look, e.g. 1h, 6h, 2d (default: 6h)')
    parser.add_argument('--board', default='7', help='Community board number for the members list (default: 7)')
    args = parser.parse_args()

    members = fetch_members(args.board)
    lines = fetch_log_lines(args.since)

    for line in lines:
        timestamp = line.split()[0] if line else ''

        incoming = extract_incoming_text(line)
        if incoming:
            name = members.get(incoming['from'], 'Unknown')
            print(f"{timestamp}  IN   from={incoming['from']} ({name})  body={incoming['body']!r}")
            continue

        shelly = extract_shelly_response(line)
        if shelly:
            print(f"{timestamp}  SHELLY  {shelly}")


if __name__ == '__main__':
    main()
