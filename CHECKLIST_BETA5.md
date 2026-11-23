# Lynk & Co MY2022 beta.5 — blijvende afvinklijst

Deze lijst is opgeslagen in de eigen GitHub-repository. Alleen vakjes afvinken nadat de stap is uitgevoerd.

## Voorbereiding
- [x] Beta.4 geplaatst met twee geslaagde configuratiechecks en rollback-back-up `20261123-171943` (gebruikersuitvoer).
- [x] Volledige HA-back-up lokaal en in OneDrive bevestigd door gebruiker.
- [x] Aparte beta.5 branch voorbereid, zonder huidige werkende installatie te wijzigen.
- [x] Sessieterugname voor bekende 403, lock voor refresh, foutclassificatie en time-outs geprogrammeerd.
- [x] Bestaande MY2022-commando's, package, dashboard en readback ongewijzigd gelaten.
- [x] Offline regressietests opgenomen in branch en 10/10 geslaagd in GitHub Actions.
- [x] Overgenomen Python 3.13 importfout met `callable | None` hersteld in beta.5.
- [ ] Bevestig dat Home Assistant na beta.4 installatie normaal functioneert; noteer Core/OS-versie.
- [ ] Controleer of upstream Marketplace automatische updates niet over de fork heen installeren.

## Eerst controleren
- [ ] Clone `lynkco-my2022-v0.6.3-beta5-session` in `/config/lynkco-beta5-prep`.
- [ ] Voer `sh /config/lynkco-beta5-prep/install_beta5.sh --check` uit.
- [x] Python syntax en 10 offline mock-tests geslaagd in GitHub Actions.
- [ ] Zelfde 10 tests op Home Assistant met `--check` geslaagd.
- [ ] Home Assistant-configuratiecheck geslaagd.
- [x] Hassfest-validatie geslaagd in GitHub Actions.
- [x] HACS-publicatiecheck faalt op GitHub-repositorytopics en uitgeschakelde Issues (geen code-testresultaat); bewust geen repo-instellingen aangepast.

## Installeren (alleen na groene controles)
- [ ] Voer `sh /config/lynkco-beta5-prep/install_beta5.sh --apply` uit.
- [ ] Nieuwe backupmap in `/config/backups/lynkco-before-beta5-...` genoteerd.
- [ ] `ha core restart` uitgevoerd.
- [ ] Nieuwe versie `0.6.3-beta.5` actief; geen onbekende entiteiten verdwenen.

## Functionele test / veiligheid
- [ ] Accu-SOC, laden, EV-aansturing en locatie worden normaal bijgewerkt.
- [ ] Auto op slot en open: knopblokkering en terugleesstatus zoals eerder.
- [ ] Claxon/lichtsignaal en klimaat sturen hetzelfde als voorheen.
- [ ] 30 seconden readbacktimeout met rode foutindicatie blijft werken.
- [ ] 401-problemen verbeteren zonder herhaald handmatig aanmelden.
- [ ] Bekende 403-sessieovername: maximaal één reclaim per minuut, geen eindeloze verzoeken.
- [ ] 403 voor onbekende raam/zonnedakopdracht claimt niet onnodig sessie.
- [ ] 429, 5xx, DNS/timeout veroorzaken geen onjuiste Reparaties-aanmelding.
- [ ] Bestaande 2022 raam/zonnedakfuncties apart analyseren; niet als bevestigd werkend markeren.
- [ ] Na praktijkcontrole beslissen of beta.5 geschikt is om verder te gebruiken.

Documentatie: `LYNKCO_MY2022_BETA5.md`. Rollback: nieuwe beta.5-back-up terugplaatsen vóór herstart.
