#!/bin/sh
# Run the full test suite inside the built runtime image.
#
# The tests run in a throwaway container from the image, with the repo mounted
# and the dev extra installed into that container. Nothing is written to the
# image, so the shipped image is unchanged. Pass an image name to test a
# different tag; the default is mdns-mirror:dev from scripts/build-image.sh.
# Arguments after the image name are passed to pytest.
set -e

cd "$(dirname "$0")/.."
image=${1:-mdns-mirror:dev}
[ $# -gt 0 ] && shift

docker run --rm \
  --cap-add NET_ADMIN --cap-add SYS_ADMIN --security-opt systempaths=unconfined \
  -v "$PWD":/app -w /app \
  --entrypoint sh "$image" -c "
  apt-get update -qq &&
  apt-get install -y -qq avahi-daemon &&
  pip install -q '.[dev]' &&
  ruff check src tests &&
  python -m pytest -q \"\$@\" &&
  python scripts/check_coverage.py
" sh "$@"
