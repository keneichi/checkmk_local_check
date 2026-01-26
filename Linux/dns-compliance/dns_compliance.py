#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import os

SERVICE_PTR = "DNS_PTR_consistency"
SERVICE_A = "DNS_A_consistency"
SERVICE_HOST = "DNS_HOSTNAME_consistency"

CONFIG_FILE = "/etc/checkmk_dns_compliance.conf"
# Exemple:
# enabled=true
# domain=aslion.lan
# ip=10.44.1.254
# fqdn=proxmox-lan.aslion.lan


def load_config():
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
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 53))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip


def clean(name: str) -> str:
    return (name or "").rstrip(".").lower()


def emit(state: int, service: str, msg: str, perf: str = ""):
    # local check: "<state> <service> - <text> | <perf>"
    if perf:
        print(f"{state} {service} - {msg} | {perf}")
    else:
        print(f"{state} {service} - {msg}")


def main():
    cfg = load_config()
    enabled = cfg.get("enabled", "true").lower()

    # --- Hostname (court) ---
    try:
        hostname = socket.gethostname()
        short = hostname.split(".")[0]
    except Exception as e:
        msg = f"UNKNOWN - Impossible de déterminer le hostname : {e}"
        emit(3, SERVICE_PTR, msg)
        emit(3, SERVICE_A, msg)
        emit(3, SERVICE_HOST, msg)
        return

    # --- Désactivation volontaire ---
    if enabled == "false":
        msg = "Check désactivé pour ce host (exception volontaire)"
        perf = f"fqdn=disabled ip=0.0.0.0 short={short}"
        emit(0, SERVICE_PTR, msg, perf)
        emit(0, SERVICE_A, msg, perf)
        emit(0, SERVICE_HOST, msg, perf)
        return

    # --- FQDN attendu ---
    domain = cfg.get("domain")
    forced_fqdn = cfg.get("fqdn")

    if forced_fqdn:
        expected_fqdn = forced_fqdn
    elif domain:
        expected_fqdn = f"{short}.{domain}"
    else:
        expected_fqdn = socket.getfqdn()

    # --- IP attendue ---
    try:
        expected_ip = cfg.get("ip") or get_primary_ip()
    except Exception as e:
        msg = f"UNKNOWN - Impossible de déterminer l'IP à vérifier : {e}"
        perf = f"fqdn={expected_fqdn} ip=0.0.0.0 short={short}"
        emit(3, SERVICE_PTR, msg, perf)
        emit(3, SERVICE_A, msg, perf)
        emit(3, SERVICE_HOST, msg, perf)
        return

    # --- FQDN système (OS) ---
    try:
        system_fqdn = socket.getfqdn()
    except Exception as e:
        system_fqdn = ""
        host_err = f"Impossible de lire le FQDN système : {e}"
    else:
        host_err = None

    expected_fqdn_c = clean(expected_fqdn)
    system_fqdn_c = clean(system_fqdn)

    # =========================
    # 1) PTR : IP -> FQDN
    # =========================
    ptr_problem = None
    try:
        ptr_name, _, _ = socket.gethostbyaddr(expected_ip)
        if clean(ptr_name) != expected_fqdn_c:
            ptr_problem = f"PTR {expected_ip} -> {ptr_name} (attendu: {expected_fqdn})"
    except Exception as e:
        ptr_problem = f"PTR {expected_ip} échec : {e}"

    if ptr_problem:
        emit(2, SERVICE_PTR, ptr_problem,
             f"fqdn={expected_fqdn} ip={expected_ip} short={short} domain={domain or 'auto'} "
             f"ip_override={bool(cfg.get('ip'))} fqdn_override={bool(forced_fqdn)}")
    else:
        emit(0, SERVICE_PTR, f"PTR OK ({expected_ip} -> {expected_fqdn})",
             f"fqdn={expected_fqdn} ip={expected_ip} short={short} domain={domain or 'auto'} "
             f"ip_override={bool(cfg.get('ip'))} fqdn_override={bool(forced_fqdn)}")

    # =========================
    # 2) A : FQDN -> IP(s)
    # =========================
    a_problem = None
    try:
        results = socket.getaddrinfo(expected_fqdn, None, proto=socket.IPPROTO_TCP)
        a_ips = sorted({res[4][0] for res in results})
        if expected_ip not in a_ips:
            a_problem = f"A {expected_fqdn} -> {', '.join(a_ips) or 'aucune IP'} (attendu: {expected_ip})"
    except Exception as e:
        a_problem = f"A {expected_fqdn} échec : {e}"

    if a_problem:
        emit(2, SERVICE_A, a_problem,
             f"fqdn={expected_fqdn} ip={expected_ip} short={short} domain={domain or 'auto'} "
             f"ip_override={bool(cfg.get('ip'))} fqdn_override={bool(forced_fqdn)}")
    else:
        emit(0, SERVICE_A, f"A OK ({expected_fqdn} -> {expected_ip})",
             f"fqdn={expected_fqdn} ip={expected_ip} short={short} domain={domain or 'auto'} "
             f"ip_override={bool(cfg.get('ip'))} fqdn_override={bool(forced_fqdn)}")

    # =========================
    # 3) Identité machine : FQDN OS == FQDN attendu
    # =========================
    if host_err:
        emit(3, SERVICE_HOST, f"UNKNOWN - {host_err}",
             f"expected_fqdn={expected_fqdn} system_fqdn=unknown short={short}")
    else:
        # Tu peux décider WARN au lieu de CRIT, mais CRIT est souvent ok en conformité
        if system_fqdn_c != expected_fqdn_c:
            emit(2, SERVICE_HOST,
                 f"FQDN système != FQDN attendu (system={system_fqdn}, attendu={expected_fqdn})",
                 f"expected_fqdn={expected_fqdn} system_fqdn={system_fqdn} short={short}")
        else:
            emit(0, SERVICE_HOST,
                 f"Hostname/FQDN OK (system={system_fqdn})",
                 f"expected_fqdn={expected_fqdn} system_fqdn={system_fqdn} short={short}")


if __name__ == "__main__":
    main()
