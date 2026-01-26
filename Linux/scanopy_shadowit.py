#!/usr/bin/env python3
import json
import os
import sys
import urllib.request
import urllib.parse
from ipaddress import ip_address

# -----------------------
# Config via variables d'env (recommandé)
# -----------------------
SCANOPY_BASE_URL = os.getenv("SCANOPY_BASE_URL", "http://10.44.0.16:60072")
SCANOPY_TOKEN = os.getenv("SCANOPY_TOKEN", "ScanOpy_Token")
SCANOPY_NETWORK_ID = os.getenv("SCANOPY_NETWORK_ID", "Id_Network_ScanOpy")  # optionnel (UUID Scanopy)

CHECKMK_BASE_URL = os.getenv("CHECKMK_BASE_URL", "https://monitoring.univers-shima.fr")
CHECKMK_SITE = os.getenv("CHECKMK_SITE", "monitoring")
CHECKMK_USER = os.getenv("CHECKMK_USER", "scanopy")
CHECKMK_SECRET = os.getenv("CHECKMK_SECRET", "CheckMK_User_Password")

IGNORE_SCANOPY_TAG = os.getenv("SCANOPY_IGNORE_TAG", "nocheckmk")
WARN_AT = int(os.getenv("SCANOPY_WARN_AT", "1"))
CRIT_AT = int(os.getenv("SCANOPY_CRIT_AT", "5"))

TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))

SERVICE_NAME = "Scanopy Shadow IT"

CHECKMK_EXTRA_IP_LABEL = os.getenv("CHECKMK_EXTRA_IP_LABEL", "vpn_ip")

def http_get(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = r.read().decode("utf-8", errors="replace")
    return json.loads(data)

def scanopy_list_hosts():
    if not SCANOPY_TOKEN:
        raise RuntimeError("SCANOPY_TOKEN manquant")

    params = {"limit": "0"}
    if SCANOPY_NETWORK_ID:
        params["network_id"] = SCANOPY_NETWORK_ID

    url = f"{SCANOPY_BASE_URL.rstrip('/')}/api/v1/hosts?{urllib.parse.urlencode(params)}"
    j = http_get(url, headers={"Authorization": f"Bearer {SCANOPY_TOKEN}", "Accept": "application/json"})

    if not j.get("success"):
        raise RuntimeError(f"Scanopy API error: {j.get('error', 'unknown')}")
    return j.get("data", [])

def scanopy_list_tags():
    url = f"{SCANOPY_BASE_URL.rstrip('/')}/api/v1/tags"
    j = http_get(url, headers={"Authorization": f"Bearer {SCANOPY_TOKEN}", "Accept": "application/json"})
    if not j.get("success"):
        raise RuntimeError(f"Scanopy tags API error: {j.get('error', 'unknown')}")
    return {t["id"]: t["name"].lower() for t in j.get("data", [])}

def extract_scanopy_host_ips_tags(h: dict):
    """
    On essaie d'être tolérant sur le schéma.
    On récupère:
      - tags: liste de strings
      - ips: toutes les IP trouvées dans interfaces[]
    """
    tags = h.get("tags") or []
    if isinstance(tags, dict):
        # au cas où ce soit un mapping
        tags = list(tags.keys())

    ips = set()
    for iface in (h.get("interfaces") or []):
        # champs possibles selon schéma
        for k in ("ip", "ip_address", "address", "ipv4"):
            v = iface.get(k)
            if v:
                ips.add(str(v))

    # fallback éventuel si Scanopy met une ip "directe"
    for k in ("ip", "ip_address", "primary_ip"):
        v = h.get(k)
        if v:
            ips.add(str(v))

    # normalise et filtre les trucs pas IP
    norm = set()
    for s in ips:
        try:
            norm.add(str(ip_address(s)))
        except Exception:
            pass

    name = h.get("name") or h.get("hostname") or h.get("display_name") or h.get("id") or "unknown"
    return str(name), norm, set([str(t).lower() for t in tags])

def checkmk_list_hosts():
    if not CHECKMK_SECRET:
        raise RuntimeError("CHECKMK_SECRET manquant")

    base = f"{CHECKMK_BASE_URL.rstrip('/')}/{CHECKMK_SITE}/check_mk/api/1.0"
    url = f"{base}/domain-types/host_config/collections/all?effective_attributes=false&include_links=false"

    headers = {
        "Authorization": f"Bearer {CHECKMK_USER} {CHECKMK_SECRET}",
        "Accept": "application/json",
    }
    j = http_get(url, headers=headers)

    # Checkmk renvoie en général {"value":[...]} sur les collections
    hosts = j.get("value") or []
    return hosts

def extract_checkmk_host_ips(h: dict):
    ext = h.get("extensions") or {}
    attrs = ext.get("attributes") or {}

    name = h.get("id") or h.get("title") or h.get("host_name") or "unknown"

    ips = set()

    # IP principale
    ip_ = attrs.get("ipaddress")
    if ip_:
        ips.add(str(ip_))

    # Labels -> ip additionnelle (ex: vpn_ip=10.0.0.1)
    labels = attrs.get("labels") or {}
    if isinstance(labels, dict) and CHECKMK_EXTRA_IP_LABEL in labels:
        ips.add(str(labels[CHECKMK_EXTRA_IP_LABEL]))

    return str(name), ips


def main():
    try:
        scanopy_hosts = scanopy_list_hosts()
        checkmk_hosts = checkmk_list_hosts()
        scanopy_tags = scanopy_list_tags()
    
        checkmk_ips = set()
        checkmk_names = set()

        for ch in checkmk_hosts:
            n, ips = extract_checkmk_host_ips(ch)
            checkmk_names.add(n.lower())

            for ip_ in ips:
                try:
                    checkmk_ips.add(str(ip_address(ip_)))
                except Exception:
                    pass

        orphans = []
        for sh in scanopy_hosts:
            name, ips, tag_ids = extract_scanopy_host_ips_tags(sh)

            # Traduction ID → nom
            tag_names = set(scanopy_tags.get(tid, "").lower() for tid in tag_ids)

            if IGNORE_SCANOPY_TAG.lower() in tag_names:
                continue

            # match par IP (prioritaire) sinon par nom
            in_checkmk = False
            if ips and (ips & checkmk_ips):
                in_checkmk = True
            elif name.lower() in checkmk_names:
                in_checkmk = True

            if not in_checkmk:
                # on garde une info lisible
                shown_ip = sorted(list(ips))[0] if ips else "no-ip"
                orphans.append(f"{name}({shown_ip})")

        count = len(orphans)
        if count >= CRIT_AT:
            state = 2
        elif count >= WARN_AT:
            state = 1
        else:
            state = 0

        if state == 0:
            msg = "OK - aucun hôte Scanopy non supervisé"
        else:
            # évite un output trop long
            preview = ", ".join(orphans[:20])
            if count > 20:
                preview += f", ... (+{count-20})"
            msg = f"{count} hôte(s) vus par Scanopy mais absents de Checkmk: {preview}"

        # format local check: <state> "<service>" <perfdata> <text>
        print(f'{state} "{SERVICE_NAME}" - {msg}')

    except Exception as e:
        print(f'2 "{SERVICE_NAME}" - erreur script: {e}')
        return 0

if __name__ == "__main__":
    sys.exit(main())

