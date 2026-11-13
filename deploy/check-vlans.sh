#!/bin/sh
# Check that the VLAN interfaces the container needs exist on the VM.
#
# Run this on the VM before starting the container. It exits nonzero and
# names any interface that is missing.
#
# Usage: deploy/check-vlans.sh enp3s0.10 enp3s0.20 enp3s0.30

if [ "$#" -eq 0 ]; then
  echo "usage: $0 INTERFACE [INTERFACE ...]" >&2
  exit 2
fi

missing=""
for dev in "$@"; do
  if ! ip link show dev "$dev" >/dev/null 2>&1; then
    missing="$missing $dev"
  fi
done

if [ -n "$missing" ]; then
  echo "check-vlans: missing VLAN interfaces:$missing" >&2
  echo "Check /etc/netplan/01-mdns-mirror.yaml and run 'sudo netplan apply'." >&2
  exit 1
fi

echo "check-vlans: all VLAN interfaces present"
