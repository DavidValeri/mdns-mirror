#!/bin/sh
set -e

nft -f /etc/mdns-mirror/firewall.nft
exec python -m mdns_mirror "$@"
