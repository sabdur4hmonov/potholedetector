#!/usr/bin/env bash
# Rebuild the nationwide NH/NE tiles from a reviewed, SHA-256-pinned India extract.
#
# SEC-015: the downloaded source is authenticated only by SHA-256. MD5 is never computed
# or accepted, and there is no weaker fallback. The committed tiles were built from the
# 2026-08-20 extract below; its MD5 remains only a historical provenance label in the
# source receipt and manifests. Geofabrik no longer publishes that dated file (HTTP 404
# on 2026-09-14) and its SHA-256 was never recorded, so SOURCE_SHA256 is deliberately
# empty: this script refuses to download or build until a maintainer reviews an extract
# and pins its SHA-256 (updating SOURCE_URL and the build-tool/runtime receipt pins too).
set -euo pipefail

SOURCE_URL=https://download.geofabrik.de/asia/india-260820.osm.pbf
SOURCE_SHA256=

require_sha256_pin() {
  [[ "$1" =~ ^[0-9a-f]{64}$ ]] || {
    echo "source SHA-256 pin is missing or malformed; review an extract and pin its lowercase SHA-256" >&2
    return 1
  }
}

sha256_of() {
  if command -v sha256sum >/dev/null; then
    sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null; then
    shasum -a 256 "$1" | cut -d' ' -f1
  else
    echo "sha256sum or shasum is required" >&2
    return 1
  fi
}

verify_source_digest() {
  local file=$1 expected=$2 actual
  require_sha256_pin "$expected" || return 1
  [ -f "$file" ] || { echo "source file is missing: $file" >&2; return 1; }
  actual=$(sha256_of "$file") || return 1
  [ "$actual" = "$expected" ] || {
    echo "source SHA-256 mismatch: $actual" >&2
    return 1
  }
}

main() {
  cd "$(dirname "$0")/.."
  # Fail before any network transfer: an unpinned source must never be downloaded or parsed.
  require_sha256_pin "$SOURCE_SHA256"

  command -v curl >/dev/null || { echo "curl is required" >&2; exit 1; }
  command -v osmium >/dev/null || { echo "osmium-tool is required" >&2; exit 1; }

  WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/pothole-national-highways.XXXXXX")
  trap 'rm -rf "$WORK_DIR"' EXIT
  PBF=$WORK_DIR/india.osm.pbf
  FILTERED=$WORK_DIR/national-highways.osm.pbf
  GEOJSONSEQ=$WORK_DIR/national-highways.geojsonseq

  curl --fail --location --retry 3 --output "$PBF" "$SOURCE_URL"
  verify_source_digest "$PBF" "$SOURCE_SHA256"

  osmium tags-filter "$PBF" 'w/ref=NH*' 'w/ref=NE*' 'w/network=IN:NH' \
    --overwrite --output "$FILTERED"
  osmium export "$FILTERED" --geometry-types=linestring \
    --output-format=geojsonseq --overwrite --output "$GEOJSONSEQ"
  python3 tools/build-national-highways.py --source "$GEOJSONSEQ"
}

# Sourcing exposes the verification functions to tests without downloading anything.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
