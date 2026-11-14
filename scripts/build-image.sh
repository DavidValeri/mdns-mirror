#!/bin/sh
# Build the runtime image locally and smoke-test it.
#
# The image is tagged mdns-mirror:dev for the host architecture. Extra
# arguments are passed to docker build, for example --platform.
set -e

cd "$(dirname "$0")/.."

docker build -t mdns-mirror:dev "$@" .
sh scripts/smoke-test.sh mdns-mirror:dev
