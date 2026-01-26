#!/usr/bin/env bash
set -euo pipefail

WG_BIN="${WG_BIN:-wg}"
CONF="/etc/check_mk/local_check_conf/wireguard_peers.conf"

WARN_DEFAULT="${WARN_DEFAULT:-180}"   # 3 min
CRIT_DEFAULT="${CRIT_DEFAULT:-600}"   # 10 min

now="$(date +%s)"

"$WG_BIN" show all dump 2>/dev/null | awk \
  -v now="$now" \
  -v conf="$CONF" \
  -v warn_def="$WARN_DEFAULT" \
  -v crit_def="$CRIT_DEFAULT" '
BEGIN {
  FS="\t";

  # optional mapping pubkey -> name/warn/crit/ping
  while ((getline line < conf) > 0) {
    if (line ~ /^[[:space:]]*#/ || line ~ /^[[:space:]]*$/) continue;
    n = split(line, a, /[[:space:]]+/);
    pub  = a[1];
    name = a[2];
    warn = a[3];
    crit = a[4];
    ping = a[5];

    if (name == "") name = substr(pub, 1, 10);
    if (warn == "") warn = warn_def;
    if (crit == "") crit = crit_def;

    NAME[pub] = name;
    WARN[pub] = warn;
    CRIT[pub] = crit;
    PING[pub] = ping;
  }
  close(conf);
}

# interface line: 5 fields
NF==5 { next }

# peer line
NF>=9 {
  iface    = $1;
  pub      = $2;
  endpoint = $4;
  allowed  = $5;
  hs       = $6;
  rx       = $7;
  tx       = $8;

  name = (pub in NAME) ? NAME[pub] : substr(pub, 1, 10);
  warn = (pub in WARN) ? WARN[pub] : warn_def;
  crit = (pub in CRIT) ? CRIT[pub] : crit_def;
  ping = (pub in PING) ? PING[pub] : "";

  svc = "WireGuard_" iface "_peer_" name;  # évite espaces/accents, plus safe

  if (hs == 0) {
    status = 2;
    msg = "no_handshake endpoint=" endpoint " allowed=" allowed;
    perf = "age=-1;;;; rx=" rx "B;;;0 tx=" tx "B;;;0";
    printf("%d %s %s %s\n", status, svc, perf, msg);
    next;
  }

  age = now - hs;

  status = 0;
  state  = "OK";
  if (age >= crit) { status = 2; state = "CRIT"; }
  else if (age >= warn) { status = 1; state = "WARN"; }

  msg = state " last_handshake=" age "s endpoint=" endpoint " allowed=" allowed;

  # optional ping (1 ping, 1s timeout)
  if (ping != "") {
    cmd = "ping -c1 -W1 " ping " >/dev/null 2>&1";
    rc = system(cmd);
    if (rc != 0) {
      if (status < 2) status = 1;
      msg = msg " ping=FAIL(" ping ")";
    } else {
      msg = msg " ping=OK(" ping ")";
    }
  }

  perf = "age=" age "s;" warn ";" crit ";0 rx=" rx "B;;;0 tx=" tx "B;;;0";

  # FORMAT LOCAL CHECKMK: <state> <service> <perfdata|-> <text>
  printf("%d %s %s %s\n", status, svc, perf, msg);
}
'
