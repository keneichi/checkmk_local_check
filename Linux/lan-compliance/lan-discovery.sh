#!/bin/bash
set -euo pipefail

CONF="/etc/check_mk/local_check_conf/lan-discovery.env"
BIN="/usr/local/lib/lan-discovery.py"

set -a
. "$CONF"
set +a

exec /usr/bin/python3 "$BIN"
