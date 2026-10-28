#!/bin/sh
set -eu
umask 077
if [ "$(id -u)" = "0" ]; then
    mkdir -p /data
    chown 10001:10001 /data
    exec setpriv --reuid=10001 --regid=10001 --init-groups env HOME=/home/app /qa/soak_start.sh
fi
if [ -n "${BROWSER_CA_CERT:-}" ]; then
    mkdir -p "$HOME/.pki/nssdb"
    if [ ! -f "$HOME/.pki/nssdb/cert9.db" ]; then certutil -N -d "sql:$HOME/.pki/nssdb" --empty-password; fi
    certutil -A -d "sql:$HOME/.pki/nssdb" -n qa-proxy -t "C,," -i "$BROWSER_CA_CERT" -f /dev/null
fi
exec python /qa/soak_server.py
