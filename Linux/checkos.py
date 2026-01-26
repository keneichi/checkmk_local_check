#!/usr/bin/env python3
# /usr/lib/check_mk_agent/local/os_debian_version.py
import re, time, glob
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

URL_STABLE_RELEASE = "https://deb.debian.org/debian/dists/stable/Release"
CACHE_FILE = Path("/var/tmp/debian_stable_Release")
CACHE_TTL = 3600  # 1h
TIMEOUT = 5

def cmk(state, name, msg, perf=None):
    print(f"{state} {name} - {msg}" + ("" if not perf else " | " + " ".join(perf)))

def read_text(p):
    try:
        return Path(p).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def local_debian_version():
    # /etc/debian_version: "12.6" ou "bookworm/sid"
    dv = read_text("/etc/debian_version").strip()
    m = re.match(r"^(\d+)(?:\.(\d+))?$", dv)
    if m:
        major = int(m.group(1)); minor = int(m.group(2) or 0)
    else:
        # fallback via /etc/os-release
        osr = read_text("/etc/os-release")
        mid = re.search(r'^ID="?([^"\n]+)"?$', osr, re.M)
        if (mid.group(1).lower() if mid else "") != "debian":
            return None, None, None, None  # pas Debian
        vid = re.search(r'^VERSION_ID="?([^"\n]+)"?$', osr, re.M)
        if vid and re.match(r"^\d+(?:\.\d+)?$", vid.group(1)):
            parts = vid.group(1).split(".")
            major = int(parts[0]); minor = int(parts[1] if len(parts) > 1 else 0)
        else:
            return None, None, None, dv or "unknown"
    codename = re.search(r'^VERSION_CODENAME="?([^"\n]+)"?$', read_text("/etc/os-release"), re.M)
    return major, minor, (codename.group(1) if codename else ""), dv or f"{major}.{minor}"

def fetch_stable_release_text():
    now = time.time()
    if CACHE_FILE.exists() and now - CACHE_FILE.stat().st_mtime < CACHE_TTL:
        return CACHE_FILE.read_text(encoding="utf-8", errors="ignore")
    try:
        req = Request(URL_STABLE_RELEASE, headers={"User-Agent": "cmk-os-version/2.0"})
        with urlopen(req, timeout=TIMEOUT) as r:
            data = r.read().decode("utf-8", errors="ignore")
        CACHE_FILE.write_text(data, encoding="utf-8")
        return data
    except (URLError, HTTPError):
        # fallback: Release local d’APT si "apt update" déjà passé
        for f in sorted(glob.glob("/var/lib/apt/lists/*_dists_*_Release")):
            try:
                return Path(f).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
        raise

def parse_release(text):
    # lignes "Key: Value"
    kv = {}
    for line in text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip()] = v.strip()
    code = kv.get("Codename", "")
    ver = kv.get("Version", "")  # ex: "12.11"
    m = re.match(r"^(\d+)(?:\.(\d+))?$", ver)
    st_major = int(m.group(1)) if m else None
    st_minor = int(m.group(2) or 0) if m else 0
    return code, ver, st_major, st_minor

def main():
    cur_major, cur_minor, cur_code, cur_label = local_debian_version()
    if cur_major is None:
        cmk(3, "os_version", "UNKNOWN: OS non-Debian ou version illisible")
        return

    try:
        rel_txt = fetch_stable_release_text()
        st_code, st_label, st_major, st_minor = parse_release(rel_txt)
    except Exception as e:
        cmk(3, "os_version",
            f"UNKNOWN: impossible de récupérer Release stable ({e})",
            [f"release={cur_major}", f"update={cur_minor}"])
        return

    perf = [f"release={cur_major}", f"update={cur_minor}"]
    if st_major is not None:
        perf += [f"stable_release={st_major}", f"stable_update={st_minor}"]

    # Cas: machine plus récente que stable (testing/unstable) → WARN
    if st_major is not None and (cur_major, cur_minor) > (st_major, st_minor):
        cmk(1, "os_version",
            f"WARN: version locale {cur_label} (codename {cur_code or 'N/A'}) plus récente que stable {st_label or 'N/A'} ({st_code or 'N/A'})",
            perf)
        return

    # Règles demandées
    if st_major is None:
        # pas d’info de point release → on se base sur codename si dispo
        if st_code and cur_code and st_code != cur_code:
            # delta majeure inconnu → WARN par défaut
            cmk(1, "os_version",
                f"WARN: stable={st_code}, local={cur_code or 'N/A'} (pas d’info Version dans Release)",
                perf)
        else:
            cmk(0, "os_version",
                f"OK: Debian {cur_label} ({cur_code or 'N/A'})",
                perf)
        return

    delta_major = st_major - cur_major

    # 1) CRIT si pas sur la dernière point release de ta majeure
    if delta_major == 0 and cur_minor < st_minor:
        cmk(2, "os_version",
            f"CRIT: point release disponible → {cur_major}.{cur_minor} → {st_major}.{st_minor}",
            perf)
        return

    # 3) CRIT si ≥ 2 majeures de retard
    if delta_major >= 2:
        cmk(2, "os_version",
            f"CRIT: {cur_major}.x trop ancien (stable={st_major}.{st_minor})",
            perf)
        return

    # 2) WARN si en retard d’une seule majeure
    if delta_major == 1:
        cmk(1, "os_version",
            f"WARN: {cur_major}.x en retard d’une majeure (stable={st_major}.{st_minor})",
            perf)
        return

    # sinon OK (à jour sur la majeure et la point release)
    cmk(0, "os_version",
        f"OK: Debian {cur_major}.{cur_minor} ({cur_code or 'N/A'}) à jour (stable={st_label or 'N/A'})",
        perf)

if __name__ == "__main__":
    main()
