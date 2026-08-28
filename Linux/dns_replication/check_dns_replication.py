#!/usr/bin/env python3

import configparser
import subprocess
import sys
from pathlib import Path


CONFIG_FILE = Path("/etc/check_mk/local_check_conf/dns-replication.ini")
LOCAL_DNS = "127.0.0.1"


def get_soa_serial(server, zone, timeout):
    """Return the SOA serial for a zone from the specified DNS server."""

    try:
        result = subprocess.run(
            [
                "dig",
                f"@{server}",
                zone,
                "SOA",
                "+short",
                f"+time={timeout}",
                "+tries=1",
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 1,
        )
    except subprocess.TimeoutExpired:
        return None, f"timeout querying {server}"

    if result.returncode != 0:
        return None, f"dig failed querying {server}"

    output = result.stdout.strip()

    if not output:
        return None, f"no SOA returned by {server}"

    # Typical SOA output:
    # srvads.shima.lan. root.shima.lan. 2026082801 10800 3600 604800 3600

    fields = output.split()

    if len(fields) < 3:
        return None, f"invalid SOA response from {server}"

    try:
        serial = int(fields[2])
    except ValueError:
        return None, f"invalid SOA serial returned by {server}"

    return serial, None


def load_config():
    config = configparser.ConfigParser()

    if not CONFIG_FILE.exists():
        print(
            '3 "DNS replication" - '
            f"UNKNOWN - configuration file not found: {CONFIG_FILE}"
        )
        sys.exit(0)

    try:
        config.read(CONFIG_FILE)

        secondary = config.get("general", "secondary")
        timeout = config.getint("general", "timeout", fallback=3)

        zones_raw = config.get("zones", "zones")
        zones = [
            zone.strip()
            for zone in zones_raw.splitlines()
            if zone.strip()
        ]

    except (configparser.Error, ValueError, KeyError) as exc:
        print(
            '3 "DNS replication" - '
            f"UNKNOWN - invalid configuration: {exc}"
        )
        sys.exit(0)

    if not zones:
        print(
            '3 "DNS replication" - '
            "UNKNOWN - no zones configured"
        )
        sys.exit(0)

    return secondary, timeout, zones


def main():
    secondary, timeout, zones = load_config()

    for zone in zones:

        local_serial, local_error = get_soa_serial(
            LOCAL_DNS,
            zone,
            timeout,
        )

        if local_error:
            print(
                f'3 "DNS replication {zone}" - '
                f"UNKNOWN - local DNS error: {local_error}"
            )
            continue

        secondary_serial, secondary_error = get_soa_serial(
            secondary,
            zone,
            timeout,
        )

        if secondary_error:
            print(
                f'2 "DNS replication {zone}" - '
                f"CRIT - secondary DNS {secondary}: {secondary_error}; "
                f"local serial={local_serial}"
            )
            continue

        if local_serial == secondary_serial:
            print(
                f'0 "DNS replication {zone}" - '
                f"OK - serial {local_serial} identical on local and {secondary}"
            )
        else:
            print(
                f'1 "DNS replication {zone}" - '
                f"WARN - serial mismatch: "
                f"local={local_serial}, "
                f"{secondary}={secondary_serial}"
            )

if __name__ == "__main__":
    main()
