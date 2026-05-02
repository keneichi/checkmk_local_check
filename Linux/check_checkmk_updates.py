#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import subprocess

CACHE_FILE = "/var/lib/check_mk_agent/cache/checkmk_latest_version.txt"
SERVICE = "checkmk_update_available"

# Regex compatible :
# 2.4.0p10.cre
# 2.5.0.community
# 2.5.1p2.community
VER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:p(\d+))?(?:\.[a-zA-Z0-9_-]+)?")

def parse_tuple_str(vs: str):
    m = VER_RE.fullmatch(vs.strip())
    if not m:
        return None
    major = int(m.group(1))
    minor = int(m.group(2))
    patch = int(m.group(3))
    patchlevel = int(m.group(4) or 0)
    return major, minor, patch, patchlevel

def get_local_version():
    cmds = [
        ["omd", "version"],
        ["cmk", "--version"],
    ]
    for cmd in cmds:
        try:
            out = subprocess.check_output(cmd, text=True, timeout=5)
            m = VER_RE.search(out)
            if m:
                major = m.group(1)
                minor = m.group(2)
                patch = m.group(3)
                patchlevel = m.group(4) or "0"
                return f"{major}.{minor}.{patch}p{patchlevel}"
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

    # Même branche, version Z plus haute
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
