#!/bin/sh
set -e

conf=/etc/docker/daemon.json
mtu="${DOCKERD_MTU:-$(cat /sys/class/net/eth0/mtu 2>/dev/null || true)}"

set --
case "$mtu" in
    ''|off|*[!0-9]*) ;;
    *)
        grep -qs '"mtu"' "$conf" || set -- "$@" --mtu="$mtu"
        grep -qs '"default-network-opts"' "$conf" || set -- "$@" --default-network-opt=bridge=com.docker.network.driver.mtu="$mtu"
        ;;
esac

exec /usr/bin/dockerd "$@"
