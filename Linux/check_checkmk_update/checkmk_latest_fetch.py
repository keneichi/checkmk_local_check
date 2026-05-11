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

# On limite volontairement à Checkmk 2.x
VER_RE = re.compile(
    r"\b(2)\.(\d+)\.(\d+)(?:p(\d+))?(?:\.(?:cre|cee|cce|raw|enterprise|cloud|community))?\b",
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
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)p(\d+)", v)
    if not m:
        return None
    return tuple(map(int, m.groups()))

def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "checkmk-latest-fetch/1.2 (+local)"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "ignore")

def looks_like_checkmk_context(text: str, start: int, end: int) -> bool:
    context = text[max(0, start - 120):min(len(text), end + 120)].lower()

    good_words = [
        "checkmk",
        "check-mk",
        "stable release",
        "release checkmk",
        "checkmk stable",
    ]

    bad_words = [
        "discourse",
        "python",
        "debian",
        "ubuntu",
        "openssl",
        "grafana",
    ]

    return any(w in context for w in good_words) and not any(w in context for w in bad_words)

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

        if not normalized:
            continue

        if not version_tuple(normalized):
            continue

        if not looks_like_checkmk_context(html, match.start(), match.end()):
            continue

        candidates.append(normalized)

    candidates = sorted(set(candidates), key=version_tuple)

    if not candidates:
        print("[checkmk_latest_fetch] ERR: no valid Checkmk 2.x version found in RSS", file=sys.stderr)
        sys.exit(2)

    latest = candidates[-1]

    with open(CACHE_FILE, "w") as f:
        f.write(latest + "\n")

    with open(META_FILE, "w") as f:
        f.write(time.strftime("%F %T") + " via RSS\n")
        f.write("candidates=" + ",".join(candidates) + "\n")

    print(f"[checkmk_latest_fetch] OK: latest={latest}")

if __name__ == "__main__":
    main()
