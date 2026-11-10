# Lynk & Co MY2022 — blijvende afvinklijst beta.4

Deze lijst staat bewust in GitHub, zodat hij behouden blijft wanneer je later terugkomt. Open het bestand in GitHub, klik op het potlood (Edit), wijzig [ ] in [x] voor uitgevoerde stappen en klik Commit changes. Laat ongeteste stappen open.

## A. Eerst controleren — geen updates installeren
- [ ] Controleer welke integratiebron HACS momenteel gebruikt: onze mdcvansanten-fork of upstream b12e.
- [ ] Noteer Home Assistant Core, OS, HACS en Lynk & Co versienummers.
- [ ] Maak een volledige Home Assistant back-up en controleer dat hij beschikbaar is.
- [ ] Noteer de huidige entiteiten voor EV SOC, charging_status, climate en device_tracker.
- [ ] Controleer packages/lynkco_01_controls.yaml en de bestaande Lovelace-bediening; maak zo nodig een kopie.
- [ ] Controleer automations en scripts met hvac_mode: auto. Beta.4 gebruikt heat_cool.
- [ ] Update de upstream (b12e) integratie nog NIET rechtstreeks vanuit HACS.

## B. Klaarzetten — zonder de actieve installatie te wijzigen
- [x] Afzonderlijke testbranch aangemaakt vanuit volvo-functies-v0.6.3-beta3.
- [x] HA 2026.11 native klimaat-API en gerichte reauth-aanpassingen voorbereid.
- [x] Nieuwe check-first installer beschikbaar; companion blijft behouden.
- [ ] Clone/download de beta.4 branch zoals in LYNKCO_MY2022_BETA4.md.
- [ ] Voer uit: sh /config/lynkco-beta4-prep/install_beta4.sh --check
- [ ] Bekijk uitkomst HA core check, Python syntax, HACS/Hassfest en eventuele waarschuwingen.
- [ ] Controleer op dit moment of HA geheel stabiel draait.

## C. Gecontroleerde activering (alleen als B goed is)
- [ ] Voer uit: sh /config/lynkco-beta4-prep/install_beta4.sh --apply
- [ ] Noteer en controleer de nieuwe back-upmap /config/backups/lynkco-before-beta4-*.
- [ ] Voer uit: ha core restart
- [ ] Controleer of version 0.6.3-beta.4 actief is.
- [ ] Controleer dat dashboard, companion-package en EV-laadregelingen niet zijn gewijzigd.
- [ ] Controleer of alle eerder gebruikte entiteiten bestaan of een bewuste vervanging hebben.

## D. Testmatrix bediening en betrouwbare feedback
- [ ] Accu-SOC en laadstatus worden goed uitgelezen.
- [ ] Deur/raam-sensoren, locatie en klimaatstatus worden goed uitgelezen.
- [ ] Vergrendelen werkt; knop tijdelijk geblokkeerd tijdens teruglezing.
- [ ] Ontgrendelen werkt; knop tijdelijk geblokkeerd tijdens teruglezing.
- [ ] Knipperlichtsignaal werkt; geen onterechte statusclaim bij fire-and-forget.
- [ ] Claxon werkt; geen onterechte statusclaim bij fire-and-forget.
- [ ] Bij geen teruglezing binnen circa 30 seconden wordt knop vrijgegeven en fout getoond (circa 10s rood).
- [ ] Klimaat start en stopt; temperatuurinstelling wordt getest op 22 C.
- [ ] Timer maximaal 15–20 minuten en SOC-voorwaarden gecontroleerd (als reeds gebouwd; anders apart open).
- [ ] Raamventilatie test: precies een commando, 30 s wachten, backendcode noteren.
- [ ] Zonnedak test: precies een commando, 30 s wachten, backendcode noteren.

## E. Vaststellen of de fix goed is
- [ ] Bij 401 of 403 alleen geschoonde foutregels verzamelen; geen tokens, VIN of redirect URL delen.
- [ ] Reparaties/reauth hergebruikt de bestaande auto in HA, geen duplicaat (indien reauth werkelijk nodig is).
- [ ] Controleer stabiliteit na een HA-herstart en een tijdelijke netwerkstoring.
- [ ] Als problemen ontstaan: herstel de oorspronkelijke integration-directory uit beta.4 back-up.
- [ ] Met verzamelde logs bepalen of extra MY2022-legacy-aanpak voor ramen/zonnedak nodig is.
- [ ] Pas na het afvinken van de regressietests besluiten of de branch naar main mag.

## Versies en uitgangspunten
- Integratie uitgangspunt: 0.6.3-beta.3, MY2022.
- Nieuwe kandidaat: 0.6.3-beta.4.
- Companion/dashboard uitgangspunt: 0.7.0-beta.12; ongewijzigd.
- Upstream referentie: b12e release v2026.11.1, niet automatisch overnemen.

Gerelateerde instructie: LYNKCO_MY2022_BETA4.md in dezelfde branch.
