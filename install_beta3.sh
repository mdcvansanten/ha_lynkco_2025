#!/bin/sh
set -eu

cd /config
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="/config/backups/lynkco-beta3-$STAMP"
SOURCE_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
COMPANION_ZIP="/tmp/lynkco_01_v0.7.0-beta.12.zip"
COMPANION_DIR="/tmp/lynkco_01_v0.7.0-beta.12-extracted"

printf '\n=== Lynk & Co 0.6.3-beta.3 installatie ===\n'
mkdir -p "$BACKUP_DIR"

if [ -d /config/custom_components/lynkco ]; then
  cp -a /config/custom_components/lynkco "$BACKUP_DIR/lynkco"
  echo "Backup integratie: $BACKUP_DIR/lynkco"
fi

if [ -f /config/packages/lynkco_01_controls.yaml ]; then
  cp -a /config/packages/lynkco_01_controls.yaml "$BACKUP_DIR/lynkco_01_controls.yaml"
  echo "Backup package: $BACKUP_DIR/lynkco_01_controls.yaml"
fi

printf '\n=== Python syntaxcontrole beta3 ===\n'
python3 -m compileall -q "$SOURCE_DIR/custom_components/lynkco"
echo "Python syntax OK"

printf '\n=== Integratie vervangen ===\n'
rm -rf /config/custom_components/lynkco
mkdir -p /config/custom_components
cp -a "$SOURCE_DIR/custom_components/lynkco" /config/custom_components/lynkco

grep '"version"' /config/custom_components/lynkco/manifest.json

printf '\n=== Companion v0.7.0-beta.12 uitpakken ===\n'
rm -f "$COMPANION_ZIP"
rm -rf "$COMPANION_DIR"
base64 -d "$SOURCE_DIR/companion/lynkco_01_v0.7.0-beta.12.zip.b64" > "$COMPANION_ZIP"
mkdir -p "$COMPANION_DIR"
python3 -m zipfile -e "$COMPANION_ZIP" "$COMPANION_DIR"

mkdir -p /config/packages
cp -a \
  "$COMPANION_DIR/lynkco_01_v0.7.0-beta.12/packages/lynkco_01_controls.yaml" \
  /config/packages/lynkco_01_controls.yaml

# Het actieve Lovelace-dashboard kan in storage mode niet veilig via een
# shellscript worden overschreven. Daarom zetten we de nieuwe volledige YAML
# klaar als referentiebestand; plak deze daarna in de Raw configuration editor.
cp -a \
  "$COMPANION_DIR/lynkco_01_v0.7.0-beta.12/dashboards/lynkco_01_dashboard.yaml" \
  /config/lynkco_01_dashboard_beta12.yaml

echo "Package geïnstalleerd: /config/packages/lynkco_01_controls.yaml"
echo "Dashboard klaar gezet: /config/lynkco_01_dashboard_beta12.yaml"

printf '\n=== Home Assistant configuratiecontrole ===\n'
ha core check

printf '\nConfiguratie is geldig. Home Assistant wordt herstart.\n'
ha core restart

printf '\nKlaar. Na de herstart:\n'
printf '1. Controleer dat Lynk & Co versie 0.6.3-beta.3 geladen is.\n'
printf '2. Vervang indien gewenst de Auto-dashboard YAML met /config/lynkco_01_dashboard_beta12.yaml.\n'
printf '3. Test ramen/zonnedak steeds één keer en wacht circa 30 seconden.\n'
printf '4. Bij mislukking: grep de log op "Lynk & Co command response" of "Lynk & Co API error".\n'
