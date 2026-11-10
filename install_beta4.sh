#!/bin/sh
# MY2022 beta4: only integration files; no automatic restart or dashboard changes.
set -eu
MODE="--check"
if [ "$#" -ge 1 ]; then MODE="$1"; fi
case "$MODE" in --check|--apply) ;; *) echo "Gebruik: sh install_beta4.sh [--check|--apply]"; exit 2 ;; esac
SRC_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SOURCE="$SRC_DIR/custom_components/lynkco"
TARGET=/config/custom_components/lynkco
[ -f "$SOURCE/manifest.json" ] || { echo "Broncode ontbreekt"; exit 1; }
[ -d /config ] || { echo "Niet in Home Assistant omgeving"; exit 1; }
command -v python3 >/dev/null || exit 1
command -v ha >/dev/null || { echo "Home Assistant CLI ontbreekt"; exit 1; }
echo "Lynk & Co MY2022 beta4 ($MODE)"
python3 - "$SOURCE" <<'PY'
import ast, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
version = json.loads((root / "manifest.json").read_text())["version"]
if version != "0.6.3-beta.4":
    raise SystemExit("Onverwachte versie: " + version)
for p in root.rglob("*.py"):
    ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
print("Versie", version, ": Python-syntax OK")
PY
if [ -f "$TARGET/manifest.json" ]; then
 echo "Huidig:"; grep '"version"' "$TARGET/manifest.json" || true
else
 echo "Bestaande integratie ontbreekt"
 [ "$MODE" = "--check" ] || exit 1
fi
for f in /config/packages/lynkco_01_controls.yaml /config/lynkco_01_dashboard_beta12.yaml; do
 [ ! -f "$f" ] || echo "Ongewijzigd te behouden: $f"
done
if [ -d /config/packages ]; then
 echo "Controle op HVAC auto (eventueel handmatig migreren):"
 grep -Rin -E 'hvac_mode[[:space:]]*:[[:space:]]*auto' /config/packages 2>/dev/null || true
fi
echo "Configuratiecheck vooraf:"
ha core check
if [ "$MODE" = "--check" ]; then
 echo "Alleen controle: actieve installatie ongewijzigd."
 exit 0
fi
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="/config/backups/lynkco-before-beta4-$STAMP"
STAGE="/config/custom_components/.lynkco-beta4-stage-$$"
PREVIOUS="/config/custom_components/.lynkco-previous-$$"
mkdir -p "$BACKUP" /config/custom_components
cp -a "$TARGET" "$BACKUP/lynkco"
[ ! -f /config/packages/lynkco_01_controls.yaml ] ||
 cp -a /config/packages/lynkco_01_controls.yaml "$BACKUP/lynkco_01_controls.yaml"
[ ! -f /config/lynkco_01_dashboard_beta12.yaml ] ||
 cp -a /config/lynkco_01_dashboard_beta12.yaml "$BACKUP/lynkco_01_dashboard_beta12.yaml"
cp -a "$SOURCE" "$STAGE"
mv "$TARGET" "$PREVIOUS"
mv "$STAGE" "$TARGET"
echo "Configuratiecheck na plaatsing:"
if ! ha core check; then
 echo "Configuratie ongeldig: vorige versie wordt hersteld."
 rm -rf "$TARGET"
 mv "$PREVIOUS" "$TARGET"
 ha core check || true
 exit 1
fi
rm -rf "$PREVIOUS"
echo "Beta4 geplaatst; Home Assistant is NIET herstart."
echo "Back-up op: $BACKUP"
echo "Na controle zelf uitvoeren: ha core restart"
