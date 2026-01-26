#!/usr/bin/env python3
import subprocess
import os

def get_upgrades():
    try:
        r = subprocess.run(
            ["apt-get", "-s", "upgrade"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
        )
        return r.stdout.splitlines()
    except Exception:
        return []

def parse_upgrades(lines):
    secu, normal = [], []
    for line in lines:
        # Exemple: "Inst openssl [1.1.1f-1ubuntu2.22] (1.1.1f-1ubuntu2.23 Ubuntu:20.04/focal-updates,focal-security [amd64])"
        if line.startswith("Inst "):
            if "security" in line:
                secu.append(line)
            else:
                normal.append(line)
    return secu, normal

def reboot_required():
    # Debian/Ubuntu
    reboot_file = "/var/run/reboot-required"
    pkgs_file = "/var/run/reboot-required.pkgs"
    if os.path.isfile(reboot_file):
        pkgs = []
        if os.path.isfile(pkgs_file):
            try:
                with open(pkgs_file, "r") as f:
                    pkgs = [l.strip() for l in f if l.strip()]
            except Exception:
                pass
        return True, pkgs
    # (optionnel) RHEL-like : needs-restarting -r (si dispo)
    try:
        r = subprocess.run(["needs-restarting", "-r"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 1:
            return True, []
    except FileNotFoundError:
        pass
    return False, []

if __name__ == "__main__":
    lines = get_upgrades()
    secu, normal = parse_upgrades(lines)

    # 1) Sécurité -> CRITICAL si présent
    if secu:
        print(f"2 Updates_Security - {len(secu)} maj(s) de sécurité dispo")
    else:
        print("0 Updates_Security - Aucune maj de sécurité")

    # 2) Normales -> WARNING si présent
    if normal:
        print(f"1 Updates_Normal - {len(normal)} maj(s) normales dispo")
    else:
        print("0 Updates_Normal - Aucune maj normale")

    # 3) Reboot requis -> WARNING si oui
    need_reboot, pkgs = reboot_required()
    if need_reboot:
        if pkgs:
            print(f"1 Updates_Reboot - Reboot requis ({len(pkgs)} paquet(s): {', '.join(pkgs[:8])}{'…' if len(pkgs)>8 else ''})")
        else:
            print("1 Updates_Reboot - Reboot requis")
    else:
        print("0 Updates_Reboot - Aucun reboot requis")
