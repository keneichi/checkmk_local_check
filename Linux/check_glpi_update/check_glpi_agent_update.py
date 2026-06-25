## This files goes into /usr/lib/check_mk_agent/local ## 
#!/usr/bin/env python3
import json
import os
import re
import subprocess
import time
import urllib.request

SERVICE = "GLPI_Agent_Update"
API_URL = "https://api.github.com/repos/glpi-project/glpi-agent/releases/latest"
CACHE_FILE = "/var/tmp/check_glpi_agent_update.json"
CACHE_TTL = 6 * 3600
MAX_CACHE_AGE_CRIT = 3 * 24 * 3600


def version_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v))


def get_installed_version():
    try:
        out = subprocess.check_output(
            ["glpi-agent", "--version"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10
        )
    except Exception as e:
        print(f"2 {SERVICE} - CRIT - impossible d'exécuter glpi-agent --version: {e}")
        raise SystemExit(0)

    match = re.search(r"(\d+(?:\.\d+)+)", out)
    if not match:
        print(f"2 {SERVICE} - CRIT - version locale introuvable dans: {out.strip()}")
        raise SystemExit(0)

    return match.group(1)


def fetch_latest_version():
    req = urllib.request.Request(
        API_URL,
        headers={"User-Agent": "checkmk-glpi-agent-update"}
    )

    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.loads(response.read().decode())

    tag = data.get("tag_name", "")
    version = tag.lstrip("v")

    if not re.match(r"^\d+(\.\d+)+$", version):
        raise ValueError(f"tag GitHub invalide: {tag}")

    cache = {
        "latest_version": version,
        "fetched_at": int(time.time())
    }

    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

    return version, 0


def get_latest_version():
    now = int(time.time())

    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                cache = json.load(f)

            age = now - int(cache["fetched_at"])

            if age < CACHE_TTL:
                return cache["latest_version"], age
        except Exception:
            pass

    try:
        return fetch_latest_version()
    except Exception:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE) as f:
                cache = json.load(f)

            age = now - int(cache["fetched_at"])
            return cache["latest_version"], age

        print(f"2 {SERVICE} - CRIT - impossible de récupérer la dernière version et aucun cache disponible")
        raise SystemExit(0)


installed = get_installed_version()
latest, cache_age = get_latest_version()

if version_tuple(installed) < version_tuple(latest):
    state = 1
    status = "WARN"
    msg = f"nouvelle version disponible: installé={installed}, latest={latest}"
elif version_tuple(installed) == version_tuple(latest):
    state = 0
    status = "OK"
    msg = f"agent à jour: installé={installed}, latest={latest}"
else:
    state = 0
    status = "OK"
    msg = f"version locale plus récente que GitHub: installé={installed}, latest={latest}"

if cache_age > MAX_CACHE_AGE_CRIT:
    state = 2
    status = "CRIT"
    msg += f" - cache trop vieux: {cache_age // 3600}h"

print(f"{state} {SERVICE} cache_age={cache_age}s {status} - {msg}")
