#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local check Checkmk : compare la version locale à la dernière version stable connue (cache).
Statuts :
- CRIT si changement de branche majeure (X.Y plus grand)
- WARN si même branche mais Z ou patch p plus grand
- OK sinon
Sortie format local check : "<state> <service> - message | current=... latest=..."
"""

import os
import re
import subprocess
import sys

CACHE_FILE = "/var/lib/check_mk_agent/cache/checkmk_latest_version.txt"
SERVICE = "checkmk_update_available"

VER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)p(\d+)")

def parse_tuple_str(vs: str):
    m = VER_RE.fullmatch(vs.strip())
    if not m:
        return None
    return tuple(map(int, m.groups()))

def get_local_version():
    # Exemple: "OMD - Open Monitoring Distribution Version 2.4.0p10.cre"
    cmds = [
        ["omd", "version"],
        ["cmk", "--version"],
    ]
    for cmd in cmds:
        try:
            out = subprocess.check_output(cmd, text=True, timeout=5)
            m = VER_RE.search(out)
            if m:
                return f"{m.group(1)}.{m.group(2)}.{m.group(3)}p{m.group(4)}"
        except Exception:
            continue
    return None

def get_latest_version():
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE) as f:
            v = f.read().strip()
            return v if v else None
    except Exception:
        return None

def compare(cur_t, lat_t):
    cM, cY, cZ, cP = cur_t
    lM, lY, lZ, lP = lat_t

    # Nouvelle branche majeure (X.Y)
    if (lM, lY) > (cM, cY):
        return 2, "Nouvelle branche disponible"
    # Même branche, Z plus haut
    if (lM, lY, lZ) > (cM, cY, cZ):
        return 1, "Nouvelle version mineure disponible"
    # Même X.Y.Z, patch p plus haut
    if (lM, lY, lZ, lP) > (cM, cY, cZ, cP):
        return 1, "Nouveau patch disponible"
    return 0, "À jour"

def main():
    cur_s = get_local_version()
    if not cur_s:
        print(f"3 {SERVICE} - UNKNOWN - impossible de lire la version locale (omd/cmk)")
        return
    lat_s = get_latest_version()
    if not lat_s:
        print(f"3 {SERVICE} - UNKNOWN - cache absent ou illisible ({CACHE_FILE}) | current={cur_s}")
        return

    cur_t = parse_tuple_str(cur_s)
    lat_t = parse_tuple_str(lat_s)
    if not cur_t or not lat_t:
        print(f"3 {SERVICE} - UNKNOWN - parsing version (current='{cur_s}' latest='{lat_s}')")
        return

    code, msg = compare(cur_t, lat_t)
    print(f"{code} {SERVICE} - {msg} | current={cur_s} latest={lat_s}")

if __name__ == "__main__":
    main()
