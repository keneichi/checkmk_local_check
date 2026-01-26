#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import os

SERVICE_PTR = "DNS_PTR_consistency"
SERVICE_A = "DNS_A_consistency"
CONFIG_FILE = "/etc/checkmk_dns_compliance.conf"  # ex : /etc/checkmk_dns_compliance.conf


def load_config():
    """
    Lit le fichier de configuration.
    Retourne un dict :
    {
      "enabled": "true/false",
      "domain": "aslion.lan",
      "ip": "10.44.1.254",
      "fqdn": "proxmox-lan.aslion.lan"
    }
    """
    cfg = {}
    if not os.path.isfile(CONFIG_FILE):
        return cfg

    try:
        with open(CONFIG_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip().lower()] = v.strip()
    except Exception:
        pass

    return cfg


def get_primary_ip():
    """
    Détermine l'IP utilisée par défaut par la machine.
    (Sans envoyer de trafic réel)
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 53))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip


def main():
    # Charger config
    cfg = load_config()
    enabled = cfg.get("enabled", "true").lower()

    # Hostname court
    try:
        hostname = socket.gethostname()
        short = hostname.split(".")[0]
    except Exception as e:
        # Si on n'a même pas de hostname, on sort en UNKNOWN pour les deux checks
        msg = f"UNKNOWN - Impossible de déterminer le hostname : {e}"
        print(f"3 {SERVICE_PTR} - {msg}")
        print(f"3 {SERVICE_A} - {msg}")
        return

    # Si désactivé : on sort deux OK "désactivés"
    if enabled == "false":
        msg = "Check désactivé pour ce host (exception volontaire)"
        print(f"0 {SERVICE_PTR} - {msg} | fqdn=disabled ip=0.0.0.0 short={short}")
        print(f"0 {SERVICE_A} - {msg} | fqdn=disabled ip=0.0.0.0 short={short}")
        return

    # Domaine / FQDN
    domain = cfg.get("domain")
    forced_fqdn = cfg.get("fqdn")

    if forced_fqdn:
        fqdn = forced_fqdn
    elif domain:
        fqdn = f"{short}.{domain}"
    else:
        # Fallback sur fqdn système
        fqdn = socket.getfqdn()

    # IP (override possible)
    try:
        ip = cfg.get("ip") or get_primary_ip()
    except Exception as e:
        msg = f"UNKNOWN - Impossible de déterminer l'IP à vérifier : {e}"
        print(f"3 {SERVICE_PTR} - {msg} | fqdn={fqdn} ip=0.0.0.0 short={short}")
        print(f"3 {SERVICE_A} - {msg} | fqdn={fqdn} ip=0.0.0.0 short={short}")
        return

    # ---- Vérif PTR ----
    ptr_problem = None
    try:
        ptr_name, aliaslist, addrlist = socket.gethostbyaddr(ip)
        ptr_clean = ptr_name.rstrip(".").lower()
        fqdn_clean = fqdn.rstrip(".").lower()
        if ptr_clean != fqdn_clean:
            ptr_problem = f"PTR {ip} -> {ptr_name} (attendu: {fqdn})"
    except Exception as e:
        ptr_problem = f"PTR {ip} échec : {e}"

    # ---- Vérif A ----
    a_problem = None
    try:
        results = socket.getaddrinfo(fqdn, None, proto=socket.IPPROTO_TCP)
        a_ips = sorted({res[4][0] for res in results})
        if ip not in a_ips:
            a_problem = f"A {fqdn} -> {', '.join(a_ips) or 'aucune IP'} (attendu: {ip})"
    except Exception as e:
        a_problem = f"A {fqdn} échec : {e}"

    # ---- Sortie PTR ----
    if ptr_problem:
        state_ptr = 2
        msg_ptr = ptr_problem
    else:
        state_ptr = 0
        msg_ptr = f"PTR OK (IP={ip} -> {fqdn})"

    print(
        f"{state_ptr} {SERVICE_PTR} - {msg_ptr} | "
        f"fqdn={fqdn} ip={ip} short={short} domain={domain or 'auto'} "
        f"ip_override={bool(cfg.get('ip'))} fqdn_override={bool(forced_fqdn)}"
    )

    # ---- Sortie A ----
    if a_problem:
        state_a = 2
        msg_a = a_problem
    else:
        state_a = 0
        msg_a = f"A OK ({fqdn} -> {ip})"

    print(
        f"{state_a} {SERVICE_A} - {msg_a} | "
        f"fqdn={fqdn} ip={ip} short={short} domain={domain or 'auto'} "
        f"ip_override={bool(cfg.get('ip'))} fqdn_override={bool(forced_fqdn)}"
    )


if __name__ == "__main__":
    main()
