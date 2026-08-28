Put the config files in /etc/check_mk/local_check_conf/
Put the python3 in /usr/lib/check_mk_agent/local/
chmod 755 /usr/lib/check_mk_agent/local/check_dns_replication.py
run python3 /usr/lib/check_mk_agent/local/check_dns_replication.py
