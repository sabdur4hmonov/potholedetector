#!/usr/bin/env bash
# Downloads the OpenStreetMap extract for Uzbekistan and builds the OSRM car profile
# (multi-level Dijkstra, so live traffic can later be applied with osrm-customize).
# Re-run weekly to pick up map edits. Needs Docker and ~4 GB RAM.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p osrm-data
curl -fL -o osrm-data/uzbekistan-latest.osm.pbf \
  https://download.geofabrik.de/asia/uzbekistan-latest.osm.pbf
IMAGE=ghcr.io/project-osrm/osrm-backend:v5.27.1
docker run --rm -t -v "$PWD/osrm-data:/data" $IMAGE osrm-extract -p /opt/car.lua /data/uzbekistan-latest.osm.pbf
docker run --rm -t -v "$PWD/osrm-data:/data" $IMAGE osrm-partition /data/uzbekistan-latest.osrm
docker run --rm -t -v "$PWD/osrm-data:/data" $IMAGE osrm-customize /data/uzbekistan-latest.osrm
echo "OSRM data ready in osrm-data/"
