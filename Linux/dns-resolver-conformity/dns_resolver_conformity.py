#!/usr/bin/env python3

import os
import socket
import subprocess
import sys

CONF_FILE = "/etc/check_mk/local_check_conf/resolver_dns.conf"
RESOLV_CONF = "/etc/resolv.conf"
SERVICE_NAME = "DNS_Resolver_Conformity"


def read_conf():
    conf = {
        "allowed_dns": [],
        "allow_localhost": False,
    }
    try:
        with open(CONF_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k == "allowed_dns":
                    conf["allowed_dns"] = [x.strip() for x in v.split(",") if x.strip()]
                elif k == "allow_localhost":
                    conf["allow_localhost"] = v.lower() == "true"
    except Exception as e:
        crit(f"Unable to read config file: {e}")
    return conf


def read_resolvers():
    resolvers = []
    try:
        with open(RESOLV_CONF) as f:
            for line in f:
                line = line.strip()
                if line.startswith("nameserver"):
                    parts = line.split()
                    if len(parts) >= 2:
                        resolvers.append(parts[1])
    except Exception as e:
        crit(f"Unable to read resolv.conf: {e}")
    return resolvers


def is_localhost(ip):
    return ip in ("127.0.0.1", "::1", "127.0.0.53")


def local_dns_running():
    # systemd-resolved
    try:
        subprocess.check_output(
            ["systemctl", "is-active", "--quiet", "systemd-resolved"]
        )
        return True
    except subprocess.CalledProcessError:
        pass

    # port 53 check
    for proto in ("tcp", "udp"):
        try:
            subprocess.check_output(
                ["ss", "-l", f"-{proto[0]}", "sport", "=:53"],
                stderr=subprocess.DEVNULL,
            )
            return True
        except subprocess.CalledProcessError:
            pass

    return False


def ok(msg):
    print(f"0 {SERVICE_NAME} - {msg}")
    sys.exit(0)


def warn(msg):
    print(f"1 {SERVICE_NAME} - {msg}")
    sys.exit(0)


def crit(msg):
    print(f"2 {SERVICE_NAME} - {msg}")
    sys.exit(0)


def main():
    conf = read_conf()
    resolvers = read_resolvers()

    if not resolvers:
        crit("No DNS resolver configured")

    allowed = conf["allowed_dns"]

    # localhost handling
    if is_localhost(resolvers[0]):
        if not conf["allow_localhost"]:
            crit("Localhost DNS resolver is not allowed")
        if not local_dns_running():
            crit("nameserver is localhost but no local DNS service detected")
        ok("Local DNS resolver detected and running")

    # authorized resolvers present ?
    authorized_present = [r for r in resolvers if r in allowed]
    if not authorized_present:
        crit(
            f"No authorized DNS resolver found. Configured: {', '.join(resolvers)} | "
            f"Expected: {', '.join(allowed)}"
        )

    # first resolver check
    if resolvers[0] not in allowed:
        crit(
            f"Primary DNS resolver is not authorized ({resolvers[0]}). "
            f"Expected one of: {', '.join(allowed)}"
        )

    # extra resolvers
    extra = [r for r in resolvers if r not in allowed]
    if extra:
        warn(
            f"Unauthorized DNS resolvers detected: {', '.join(extra)} | "
            f"Authorized: {', '.join(allowed)}"
        )

    ok(f"DNS resolvers are compliant: {', '.join(resolvers)}")


if __name__ == "__main__":
    main()
