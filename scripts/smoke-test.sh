#!/bin/sh
# Smoke-test a built mdns-mirror image.
#
# Checks that the image starts with a valid rules file and keeps running with
# its firewall loaded, that it exits non-zero on an invalid rules file, and
# that the packaged files are in place. The image must be given as an argument.
set -eu

image=${1:?usage: scripts/smoke-test.sh IMAGE}
tag=$$
work=$(mktemp -d)
net_a="mdns-smoke-a-$tag"
net_b="mdns-smoke-b-$tag"
container="mdns-smoke-$tag"

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  docker network rm "$net_a" "$net_b" >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT

fail() {
  echo "smoke test failed: $1" >&2
  exit 1
}

cat >"$work/valid.yaml" <<'EOF'
rules:
  - action: allow
    source: eth0
    output: eth1
    kind: advertisement
EOF

printf 'rules: [unclosed\n' >"$work/invalid.yaml"

echo "Checking packaged files"
docker run --rm --entrypoint sh "$image" \
  -c 'command -v nft >/dev/null && test -x /usr/local/bin/entrypoint.sh && test -f /etc/mdns-mirror/firewall.nft' \
  || fail "nft, the entrypoint, or the firewall rules are missing from the image"

echo "Checking startup with a valid rules file"
docker network create "$net_a" >/dev/null
docker network create "$net_b" >/dev/null
docker create --name "$container" --cap-add NET_ADMIN --network "$net_a" \
  -v "$work/valid.yaml:/etc/mdns-mirror/rules.yaml:ro" \
  "$image" --rules /etc/mdns-mirror/rules.yaml eth0 eth1 >/dev/null
docker network connect "$net_b" "$container"
docker start "$container" >/dev/null
sleep 5
[ "$(docker inspect -f '{{.State.Running}}' "$container")" = "true" ] \
  || fail "container with a valid rules file stopped; logs: $(docker logs "$container" 2>&1 | tail -5)"
docker exec "$container" nft list table inet mdns_lockdown >/dev/null 2>&1 \
  || fail "firewall rules are not loaded"
docker rm -f "$container" >/dev/null

echo "Checking startup with an invalid rules file"
if docker run --rm --cap-add NET_ADMIN \
  -v "$work/invalid.yaml:/etc/mdns-mirror/rules.yaml:ro" \
  "$image" --rules /etc/mdns-mirror/rules.yaml eth0 eth1 >/dev/null 2>&1; then
  fail "container with an invalid rules file exited zero"
fi

echo "Smoke test passed for $image"
