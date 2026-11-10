# Lynk & Co MY2022 — beta.4 (10 november 2026)

STATUS: TESTKANDIDAAT. Niet geïnstalleerd. Bestaande main en volvo-functies-v0.6.3-beta3 blijven ongewijzigd.

## Doel en wijzigingen
- Voor HA 2026.11: native temperatuur-API plus compatibiliteit met oudere Home Assistant.
- Klimaatmodus HEAT_COOL in plaats van AUTO. Controleer automations met hvac_mode: auto.
- Reauth vernieuwt het bestaande configuratie-item (geen tweede auto/duplicaat).
- Definitief geweigerd refresh-token (HTTP 4xx uitgezonderd 429) kan een Reparaties-melding starten.
- MY2022 diagnostics en de 3/8/18/30 seconden uitleeslogica blijven behouden.
- Individuele deur- en raamsensoren blijven behouden; geen automatische overstap op de gegroepeerde upstream-sensoren.
- De companion bediening v0.7.0-beta.12 blijft staan, inclusief tijdelijke blokkering en rode foutindicatie.

## Niet overgenomen uit upstream v2026.11.1
Modelafhankelijke uitschakeling van ongeteste functies, nieuwe gegroepeerde deur-/raamsensoren, nieuwe diagnostische dump en nieuw sessie-terugpakmechanisme. Dit vereist afzonderlijke verificatie op onze MY2022 en kan bestaande automatiseringen breken. Een 401 of 403 is niet gegarandeerd opgelost door deze beta.

## Op Home Assistant terminal: eerst alleen controleren
1. Maak via HA eerst een volledige back-up. Open daarna Terminal.
2. Gebruik de onderstaande commando's (als map al bestaat: git -C /config/lynkco-beta4-prep pull --ff-only).

    cd /config
    git clone --depth 1 --single-branch --branch lynkco-my2022-v0.6.3-beta4-prep https://github.com/mdcvansanten/ha_lynkco_2025.git lynkco-beta4-prep
    sh /config/lynkco-beta4-prep/install_beta4.sh --check

3. Lees de uitkomst, werk eerst het checkbox-overzicht op het gekoppelde GitHub-issue bij.
4. Als de check goed is en je bewust wilt testen:

    sh /config/lynkco-beta4-prep/install_beta4.sh --apply
    ha core restart

De installer past alleen /config/custom_components/lynkco aan, maakt een map in /config/backups, voert vooraf en achteraf ha core check uit, vervangt de companion/package/dashboard niet en herstart HA niet automatisch.

## Rollback
Bij problemen herstel de directory /config/custom_components/lynkco uit de back-up /config/backups/lynkco-before-beta4-YYYYMMDD-HHMMSS/lynkco. Herstart Home Assistant. Zet indien nodig ook het HA-back-upmoment terug. Deel geen tokens, VIN of ongeredigeerde logs.

## Bedienings- en veiligheidsregels
- MY2022 bewezen: vergrendelen, ontgrendelen, knipperlicht, claxon.
- MY2022 experimenteel: raamventilatie en zonnedak. Maximaal één commando, 30 seconden readback, niet spammen.
- Bediening moet niet opnieuw actief worden tijdens een nog onbevestigd commando.
- Als de auto geen statuswijziging meldt, wordt na timeout een fout getoond, niet een verzonnen succes.
- Climate nog zonder automatische motorstart. Soc, brandstof, parkstand, stekkerstatus en milieucondities moeten apart geborgd worden voor eventuele uitbreiding.
- Eerst een Core-update apart controleren, daarna de Lynk & Co-kandidaat testen; nooit tegelijk.

De kandidaat is nog niet op de echte auto getest. Volg de checkbox-checklist voordat je hem als werkend beschouwt.
