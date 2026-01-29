#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import ipaddress
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Optional, Set, Tuple

import requests

try:
    import dns.resolver
    import dns.reversename
except Exception:
    dns = None

ENV_FILE = "/etc/check_mk/local_check_conf/lan-compliance.env"
DEFAULT_TIMEOUT = 3  # seconds


@dataclass
class IpItem:
    ip: str
    display: str
    tag_ids: List[str]


def load_env(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def mk_line(status: int, service: str, msg: str) -> str:
    return f"{status} {service} - {msg}"


def fetch_scanopy_json(path: str) -> dict:
    scanopy_url = os.getenv("SCANOPY_BASE_URL", "")
    token = os.getenv("SCANOPY_TOKEN", "")
    if not scanopy_url or not token:
        raise RuntimeError("SCANOPY_BASE_URL or SCANOPY_TOKEN missing in env")

    url = f"{scanopy_url.rstrip('/')}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    payload = r.json()
    if not payload.get("success", False):
        raise RuntimeError(payload.get("error", "ScanOpy API error"))
    return payload


def parse_allowed_cidrs() -> List[ipaddress._BaseNetwork]:
    raw = os.getenv("ALLOWED_CIDRS", "10.44.0.0/16")
    nets = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        nets.append(ipaddress.ip_network(part, strict=False))
    return nets


def ip_allowed(ip: str, nets: List[ipaddress._BaseNetwork]) -> bool:
    addr = ipaddress.ip_address(ip)
    return any(addr in n for n in nets)


def get_scanopy_ip_items() -> List[IpItem]:
    allowed_nets = parse_allowed_cidrs()
    payload = fetch_scanopy_json("/api/v1/hosts?limit=0")
    data = payload.get("data", [])

    out: List[IpItem] = []
    for h in data:
        name = h.get("name") or ""
        hostname = h.get("hostname") or ""
        display = hostname or name or "unknown"
        tag_ids = h.get("tags") or []

        interfaces = h.get("interfaces") or []
        ips: Set[str] = set()
        for iface in interfaces:
            ip = iface.get("ip_address")
            if not ip:
                continue
            try:
                ipaddress.ip_address(ip)
            except ValueError:
                continue
            if not ip_allowed(ip, allowed_nets):
                continue
            ips.add(ip)

        for ip in sorted(ips):
            out.append(IpItem(ip=ip, display=display, tag_ids=tag_ids))

    return out


def is_ignored(tag_ids: List[str]) -> bool:
    nodns_id = os.getenv("NODNS_TAG_ID", "").strip()
    return bool(nodns_id and nodns_id in (tag_ids or []))


def dns_ptr(ip: str) -> List[str]:
    if dns is not None:
        resolver = dns.resolver.Resolver()
        resolver.lifetime = DEFAULT_TIMEOUT
        rev = dns.reversename.from_address(ip)
        answers = resolver.resolve(rev, "PTR")
        return [str(a).rstrip(".") for a in answers]

    p = subprocess.run(["dig", "+short", "-x", ip],
                       capture_output=True, text=True, timeout=DEFAULT_TIMEOUT)
    return [l.strip().rstrip(".") for l in p.stdout.splitlines() if l.strip()]


def dns_a_ips_only(fqdn: str) -> List[str]:
    """Return only IPs from A lookup (filters out CNAME-ish outputs from dig)."""
    if dns is not None:
        resolver = dns.resolver.Resolver()
        resolver.lifetime = DEFAULT_TIMEOUT
        answers = resolver.resolve(fqdn, "A")
        return [str(a).strip() for a in answers]

    p = subprocess.run(["dig", "+short", fqdn, "A"],
                       capture_output=True, text=True, timeout=DEFAULT_TIMEOUT)
    raw = [l.strip() for l in p.stdout.splitlines() if l.strip()]

    ips = []
    for x in raw:
        x = x.strip().rstrip(".")
        try:
            ipaddress.ip_address(x)
            ips.append(x)
        except ValueError:
            pass
    return ips


def safe_suffix(ip: str) -> str:
    return ip.replace(".", "_")


# ---- Summary formatting helpers ----

def _take(items: List[str], n: int) -> Tuple[List[str], int]:
    if len(items) <= n:
        return items, 0
    return items[:n], len(items) - n

def render_group(title: str, lines: List[str], max_per_cat: int) -> List[str]:
    if not lines:
        return []
    shown, more = _take(lines, max_per_cat)
    out = [f"{title} ({len(lines)})"]
    out += shown
    if more:
        out.append(f"+{more} more")
    return out

def clamp_total(lines: List[str], max_lines: int) -> Tuple[List[str], int]:
    if len(lines) <= max_lines:
        return lines, 0
    return lines[:max_lines], len(lines) - max_lines


# ---- Checks ----

def check_ptr(ip: str) -> Tuple[int, List[str], str]:
    try:
        ptrs = dns_ptr(ip)
    except Exception as e:
        return 3, [], f"PTR lookup error: {e}"

    if len(ptrs) == 0:
        return 2, [], "No PTR record"
    if len(ptrs) > 1:
        return 2, ptrs, f"Multiple PTR records: {', '.join(ptrs)}"
    return 0, ptrs, f"PTR OK: {ptrs[0]}"


def check_a(ip: str, ptrs: List[str]) -> Tuple[int, List[str], str]:
    if len(ptrs) == 0:
        return 0, [], "Skipped (no PTR record)"
    if len(ptrs) > 1:
        return 0, [], "Skipped (multiple PTR records)"

    fqdn = ptrs[0]
    try:
        ips = dns_a_ips_only(fqdn)
    except Exception as e:
        return 3, [], f"A lookup error: {e}"

    if len(ips) == 0:
        return 1, [], f"No A record for {fqdn}"

    if len(ips) > 1:
        if ip in ips:
            return 1, ips, f"Multiple A for {fqdn}: {', '.join(ips)} (consider CNAME)"
        return 1, ips, f"Multiple A for {fqdn}: {', '.join(ips)} (IP mismatch)"

    if ips[0] != ip:
        return 1, ips, f"A mismatch for {fqdn}: {ips[0]} != {ip}"

    return 0, ips, f"A OK: {fqdn} -> {ip}"


def main() -> int:
    sep = " ; "
    load_env(ENV_FILE)

    full_detail = os.getenv("FULL_DETAIL", "false").lower() in ("1", "true", "yes")
    max_lines = int(os.getenv("DETAIL_MAX_LINES", "25"))
    max_cat = int(os.getenv("DETAIL_MAX_PER_CATEGORY", "10"))

    try:
        items = get_scanopy_ip_items()
    except Exception as e:
        print(mk_line(2, "DNS_SCANOPY", f"Failed to fetch ScanOpy hosts: {e}"))
        return 0

    checked = ignored = 0

    # Issue buckets (strings are already short + readable)
    ptr_no: List[str] = []
    ptr_multi: List[str] = []
    ptr_err: List[str] = []

    a_no: List[str] = []
    a_multi: List[str] = []
    a_mismatch: List[str] = []
    a_err: List[str] = []

    for it in items:
        if is_ignored(it.tag_ids):
            ignored += 1
            continue

        checked += 1
        suffix = safe_suffix(it.ip)

        ptr_status, ptrs, ptr_msg = check_ptr(it.ip)

        # collect PTR issues
        if ptr_status == 2 and ptr_msg.startswith("No PTR"):
            ptr_no.append(f"{it.ip} ({it.display})")
        elif ptr_status == 2 and ptr_msg.startswith("Multiple PTR"):
            ptr_multi.append(f"{it.ip} -> {', '.join(ptrs)}")
        elif ptr_status == 3:
            ptr_err.append(f"{it.ip} ({it.display}): {ptr_msg}")

        a_status, a_ips, a_msg = check_a(it.ip, ptrs)

        # collect A issues (only when actually checked / error)
        if a_status == 1 and a_msg.startswith("No A"):
            a_no.append(f"{ptrs[0]} ({it.ip})")
        elif a_status == 1 and a_msg.startswith("Multiple A"):
            a_multi.append(f"{ptrs[0]} -> {', '.join(a_ips)}")
        elif a_status == 1 and a_msg.startswith("A mismatch"):
            a_mismatch.append(f"{ptrs[0]} ({it.ip}) -> {a_ips[0]}")
        elif a_status == 3:
            a_err.append(f"{it.ip} ({it.display}): {a_msg}")

        # optional full detail output (per IP services)
        if full_detail:
            print(mk_line(ptr_status, f"DNS_PTR_{suffix}", f"{it.display} - {it.ip} - {ptr_msg}"))
            print(mk_line(a_status,   f"DNS_A_{suffix}",   f"{it.display} - {it.ip} - {a_msg}"))

    # ----- Render PTR summary -----
    ptr_issues_count = len(ptr_no) + len(ptr_multi) + len(ptr_err)
    ptr_status = 2 if ptr_issues_count > 0 else 0

    ptr_lines: List[str] = []
    ptr_lines += render_group("No PTR", ptr_no, max_cat)
    ptr_lines += render_group("Multiple PTR", ptr_multi, max_cat)
    ptr_lines += render_group("DNS errors", ptr_err, max_cat)

    header = f"PTR issues: {ptr_issues_count} (checked={checked}, ignored={ignored})"
    ptr_lines = [header] + ptr_lines
    ptr_lines, ptr_more = clamp_total(ptr_lines, max_lines)
    if ptr_more:
        ptr_lines.append(f"... +{ptr_more} more lines")
    print(mk_line(ptr_status, "DNS_PTR_CONFORMITY", sep.join(ptr_lines)))

    # ----- Render A summary -----
    a_issues_count = len(a_no) + len(a_multi) + len(a_mismatch) + len(a_err)
    a_status_sum = 1 if a_issues_count > 0 else 0

    a_lines: List[str] = []
    a_lines += render_group("No A", a_no, max_cat)
    a_lines += render_group("Multiple A", a_multi, max_cat)
    a_lines += render_group("Mismatch", a_mismatch, max_cat)
    a_lines += render_group("DNS errors", a_err, max_cat)

    header = f"A issues: {a_issues_count} (checked={checked}, ignored={ignored})"
    a_lines = [header] + a_lines
    a_lines, a_more = clamp_total(a_lines, max_lines)
    if a_more:
        a_lines.append(f"... +{a_more} more lines")
    print(mk_line(a_status_sum, "DNS_A_CONFORMITY", sep.join(a_lines)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
