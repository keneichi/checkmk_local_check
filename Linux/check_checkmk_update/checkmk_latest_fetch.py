#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import time
import urllib.request

RSS_URLS = [
    "https://forum.checkmk.com/c/announcements/18.rss",
    "https://forum.checkmk.com/tag/checkmk-release.rss",
]

CACHE_DIR = "/var/lib/check_mk_agent/cache"
CACHE_FILE = os.path.join(CACHE_DIR, "checkmk_latest_version.txt")
META_FILE = CACHE_FILE + ".meta"
TIMEOUT = 15

# Compatible :
# 2.4.0p10
# 2.4.0p10.cre
# 2.5.0
# 2.5.0.community
# 2.5.1p1.community
VER_RE = re.compile(
    r"\b(\d+)\.(\d+)\.(\d+)(?:p(\d+))?(?:\.(?:cre|cee|cce|raw|enterprise|cloud|community))?\b",
    re.IGNORECASE,
)

def normalize_version(v: str):
    m = VER_RE.search(v.strip())
    if not m:
        return None

    major = int(m.group(1))
    minor = int(m.group(2))
    patch = int(m.group(3))
    patchlevel = int(m.group(4) or 0)

    return f"{major}.{minor}.{patch}p{patchlevel}"

def version_tuple(v: str):
    nv = normalize_version(v)
    if not nv:
        return None

    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)p(\d+)", nv)
    if not m:
        return None

    return tuple(map(int, m.groups()))

def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "checkmk-latest-fetch/1.1 (+local)"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "ignore")

def main():
    os.makedirs(CACHE_DIR, exist_ok=True)

    html = None
    last_err = None

    for url in RSS_URLS:
        try:
            html = fetch_text(url)
            if html and len(html) > 100:
                break
        except Exception as e:
            last_err = e
            continue

    if not html:
        print(f"[checkmk_latest_fetch] ERR: unable to fetch RSS ({last_err})", file=sys.stderr)
        sys.exit(1)

    candidates = []

    for match in VER_RE.finditer(html):
        raw = match.group(0)
        normalized = normalize_version(raw)

        if normalized and version_tuple(normalized):
            candidates.append(normalized)

    if not candidates:
        print("[checkmk_latest_fetch] ERR: no version found in RSS", file=sys.stderr)
        sys.exit(2)

    latest = max(candidates, key=version_tuple)

    with open(CACHE_FILE, "w") as f:
        f.write(latest + "\n")

    with open(META_FILE, "w") as f:
        f.write(time.strftime("%F %T") + " via RSS\n")

    print(f"[checkmk_latest_fetch] OK: latest={latest}")

if __name__ == "__main__":
    main()
