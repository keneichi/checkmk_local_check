#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

def run(cmd):
    return subprocess.check_output(cmd, text=True)

def get_datastore_path(datastore: str) -> str:
    out = run(["proxmox-backup-manager", "datastore", "list", "--output-format", "json"])
    data = json.loads(out)
    for ds in data:
        if ds.get("name") == datastore:
            return ds["path"]
    raise RuntimeError(f"Datastore '{datastore}' introuvable")

def parse_ts(name: str):
    if not ISO_RE.match(name):
        return None
    return datetime.strptime(name, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

def newest_snapshot_dir(base: str, require_manifest: bool):
    if not os.path.isdir(base):
        return None

    best = None
    for entry in os.listdir(base):
        ts = parse_ts(entry)
        if ts is None:
            continue
        snap_dir = os.path.join(base, entry)
        if not os.path.isdir(snap_dir):
            continue
        if require_manifest:
            # Un snapshot valide doit avoir un index.json.blob (pxar client) ou un manifest.blob (VM/CT)
            if not (
                os.path.exists(os.path.join(snap_dir, "index.json.blob")) or
                os.path.exists(os.path.join(snap_dir, "manifest.blob"))
            ):
                continue

        if best is None or ts > best[0]:
            best = (ts, snap_dir)
    return best  # (datetime, path) ou None

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--datastore", required=True, help="Nom du datastore PBS (ex: backup)")
    p.add_argument("--type", required=True, help="Type PBS (host|vm|ct)")
    p.add_argument("--id", required=True, help="Backup ID (ex: srvmedia)")
    p.add_argument("--service", default=None, help="Nom du service Checkmk")
    p.add_argument("--warn-days", type=float, default=8.0)
    p.add_argument("--crit-days", type=float, default=14.0)
    p.add_argument("--no-manifest-check", action="store_true", help="Ne pas exiger manifest.blob")
    args = p.parse_args()

    service = args.service or f"PBS snapshot age {args.type}/{args.id} ({args.datastore})"

    try:
        ds_path = get_datastore_path(args.datastore)
        group_path = os.path.join(ds_path, args.type, args.id)
        newest = newest_snapshot_dir(group_path, require_manifest=not args.no_manifest_check)

        if newest is None:
            print(f"2 \"{service}\" - Aucun snapshot trouvé dans {group_path}")
            return 0

        ts, snap_dir = newest
        now = datetime.now(timezone.utc)
        age_days = (now - ts).total_seconds() / 86400.0

        if age_days >= args.crit_days:
            state = 2
            label = "CRIT"
        elif age_days >= args.warn_days:
            state = 1
            label = "WARN"
        else:
            state = 0
            label = "OK"

        perf = f"age_days={age_days:.2f};{args.warn_days};{args.crit_days}"
        print(f"{state} \"{service}\" {perf} - {label}: dernier snapshot {ts.isoformat()} (âge {age_days:.2f} jours) [{snap_dir}]")
        return 0

    except Exception as e:
        print(f"3 \"{service}\" - UNKNOWN: {e}")
        return 0

if __name__ == "__main__":
    sys.exit(main())
