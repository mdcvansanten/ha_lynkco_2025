#!/bin/sh
set -eu

REPO="mdcvansanten/ha_lynkco_2025"
REF="${1:-feature/legacy-01-support}"
HA_CONFIG="${HA_CONFIG:-/config}"
TARGET="$HA_CONFIG/custom_components/lynkco"
BACKUP_ROOT="$HA_CONFIG/lynkco_backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$BACKUP_ROOT/lynkco-$STAMP"
TMP="$(mktemp -d)"
ARCHIVE="$TMP/lynkco.tar.gz"
EXTRACT="$TMP/extract"

cleanup() {
  rm -rf "$TMP"
}
trap cleanup EXIT INT TERM

echo "Lynk & Co installer"
echo "Repository: $REPO"
echo "Ref:        $REF"
echo "HA config:  $HA_CONFIG"

mkdir -p "$EXTRACT" "$HA_CONFIG/custom_components" "$BACKUP_ROOT"

URL="https://github.com/$REPO/archive/refs/heads/$REF.tar.gz"
if echo "$REF" | grep -q '^v[0-9]'; then
  URL="https://github.com/$REPO/archive/refs/tags/$REF.tar.gz"
fi

echo "Downloading $URL"
if command -v curl >/dev/null 2>&1; then
  curl -fL --retry 3 --connect-timeout 15 "$URL" -o "$ARCHIVE"
elif command -v wget >/dev/null 2>&1; then
  wget -O "$ARCHIVE" "$URL"
else
  echo "ERROR: curl or wget is required." >&2
  exit 1
fi

tar -xzf "$ARCHIVE" -C "$EXTRACT"
SOURCE="$(find "$EXTRACT" -type d -path '*/custom_components/lynkco' -print -quit)"

if [ -z "$SOURCE" ] || [ ! -f "$SOURCE/manifest.json" ]; then
  echo "ERROR: custom_components/lynkco was not found in the downloaded archive." >&2
  exit 1
fi

if [ -d "$TARGET" ]; then
  echo "Backing up current integration to: $BACKUP"
  mv "$TARGET" "$BACKUP"
fi

mkdir -p "$TARGET"
cp -R "$SOURCE"/. "$TARGET"/

if [ ! -f "$TARGET/manifest.json" ]; then
  echo "ERROR: installation validation failed." >&2
  if [ -d "$BACKUP" ]; then
    rm -rf "$TARGET"
    mv "$BACKUP" "$TARGET"
    echo "Previous integration restored."
  fi
  exit 1
fi

VERSION="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$TARGET/manifest.json" | head -n 1)"
echo "Installed Lynk & Co version: ${VERSION:-unknown}"
echo "Source ref: $REF"
echo "Restart Home Assistant to load the new integration."
if [ -d "$BACKUP" ]; then
  echo "Rollback backup: $BACKUP"
fi
