#!/bin/sh
# Run the full test suite, including the network namespace tests.
#
# The namespace tests create veth pairs and run nft inside a Linux
# environment, so they run in a privileged container. Docker must be running.
set -e

cd "$(dirname "$0")/.."

docker run --rm --privileged -v "$PWD":/app -w /app python:3.13-slim bash -c "
  apt-get update -qq >/dev/null 2>&1 &&
  apt-get install -y -qq iproute2 nftables avahi-daemon >/dev/null 2>&1 &&
  pip install -q '.[dev]' &&
  ruff check src tests &&
  python -m pytest -q \"\$@\" &&
  python scripts/check_coverage.py
" bash "$@"
