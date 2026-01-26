#!/bin/bash
set -euo pipefail

CONF="/etc/check_mk/local_check_conf/scanopy_shadowit.env"
BIN="/usr/local/lib/scanopy/scanopy_shadowit.py"

set -a
. "$CONF"
set +a

exec /usr/bin/python3 "$BIN"
