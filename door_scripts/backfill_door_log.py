#!/usr/bin/env python3
"""
One-time backfill for the dedicated door log.

As of 2026-09 the /door page reads from 'doorlog/{board}/' -- one small JSON
object per door text, written live by app/door_log.record_door_event. Before
that, door history lived only inside 'rawvotelog/{board}/' (one object per
*every* incoming text -- vote or door), which the page had to scan in full.

This script reads that raw log once, filters down to door commands, and
writes the equivalent 'doorlog/' objects so the page shows history from
before the cutover. Run it once after deploying the doorlog write path.

Backfilled records carry:
  triggered: null   -- the Shelly outcome was never persisted back then
  door:      derived from the message text ('door'/'bottom door' -> bottom,
             'top door' -> top, anything else -> unknown). Pre-2026-09 the
             top door did not exist, so every historical bare 'door' is
             correctly 'bottom'.

Existing 'doorlog/' objects are never overwritten, so it is safe to re-run
and safe to run after live records have started accumulating. Requires the
`mcb7` AWS CLI profile.

Usage:
  ./backfill_door_log.py --dry-run              # show what would be written
  ./backfill_door_log.py                        # write missing records
  ./backfill_door_log.py --board 7 --before 2026_09_02_00:00:00
"""
import argparse
import json

import boto3

PROFILE = "mcb7"
DATA_BUCKET = "cb7-dashboard-data-store"
RAW_LOG_FOLDER = "rawvotelog/"
DOOR_LOG_FOLDER = "doorlog/"
TIMESTAMP_FORMAT = "%Y_%m_%d_%H:%M:%S"

# The raw log has one object per incoming text ever received; finding the
# door ones needs a GET on every object (the key doesn't reveal the body).
# That's the whole reason the doorlog/ prefix exists -- but the backfill
# still has to pay it once. Print progress so the scan isn't a black box.
PROGRESS_EVERY = 500


def normalize(body):
    """Mirrors app/shelly_door._normalize."""
    return " ".join(body.strip().lower().split())


def is_door_command(body):
    """Mirrors app/shelly_door.is_door_command."""
    n = normalize(body)
    return n == "door" or n.startswith("door ") or n.endswith(" door")


def door_target(body):
    """Mirrors app/shelly_door.door_target: 'bottom' / 'top' / 'unknown'."""
    n = normalize(body)
    if n in ("door", "bottom door"):
        return "bottom"
    if n == "top door":
        return "top"
    return "unknown"


def iter_raw_door_texts(s3, community_board, since):
    """Yields (timestamp, number, raw_body) for every door text in the raw
    vote log, oldest first. `since` is an optional '%Y_%m_%d_%H:%M:%S' lower
    bound -- keys sort chronologically, so it maps straight to StartAfter."""
    prefix = RAW_LOG_FOLDER + community_board + "/"
    start_after = prefix + since if since else prefix
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=DATA_BUCKET, Prefix=prefix, StartAfter=start_after):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))
    keys.sort()
    print(f"scanning {len(keys)} raw-log objects...", flush=True)

    for i, key in enumerate(keys, 1):
        if i % PROGRESS_EVERY == 0:
            print(f"  ...{i}/{len(keys)}", flush=True)
        line = s3.get_object(Bucket=DATA_BUCKET, Key=key)["Body"].read().decode("utf-8").strip()
        # VoteLoggingClass.log_raw_vote_to_file writes:
        #   "{timestamp},{number},{message},{current_vote_name}"
        parts = line.split(",", 3)
        if len(parts) < 3:
            continue
        timestamp, number, body = parts[0], parts[1], parts[2]
        if not is_door_command(body):
            continue
        yield timestamp, number, body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", default="7", help="Community board number (default: 7)")
    parser.add_argument("--since", metavar="TIMESTAMP",
                        help="Only scan raw-log objects at/after this "
                             "'%%Y_%%m_%%d_%%H:%%M:%%S' Eastern timestamp. "
                             "Bounds the (necessarily full) scan; default: all history")
    parser.add_argument("--before", metavar="TIMESTAMP",
                        help="Only backfill texts strictly before this "
                             "'%%Y_%%m_%%d_%%H:%%M:%%S' Eastern timestamp "
                             "(default: no limit)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be written without writing")
    args = parser.parse_args()

    session = boto3.Session(profile_name=PROFILE)
    s3 = session.client("s3")

    dest_prefix = DOOR_LOG_FOLDER + args.board + "/"
    existing = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=DATA_BUCKET, Prefix=dest_prefix):
        existing.update(obj["Key"] for obj in page.get("Contents", []))

    written = skipped_existing = skipped_after = 0
    for timestamp, number, body in iter_raw_door_texts(s3, args.board, args.since):
        if args.before and timestamp >= args.before:
            skipped_after += 1
            continue
        key = dest_prefix + timestamp + "_" + number + ".txt"
        if key in existing:
            skipped_existing += 1
            continue
        record = {
            "timestamp": timestamp,
            "from": number,
            "raw": body,
            "door": door_target(body),
            "triggered": None,
        }
        print(f"{'would write' if args.dry_run else 'writing'} {key}  {record['raw']!r} -> {record['door']}")
        if not args.dry_run:
            s3.put_object(Bucket=DATA_BUCKET, Key=key, Body=json.dumps(record))
        written += 1

    verb = "would write" if args.dry_run else "wrote"
    print(f"\n{verb} {written}, skipped {skipped_existing} already present"
          + (f", skipped {skipped_after} at/after {args.before}" if args.before else ""))


if __name__ == "__main__":
    main()
