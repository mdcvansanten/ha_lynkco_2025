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
- [x] Clone `lynkco-my2022-v0.6.3-beta5-session` in `/config/lynkco-beta5-prep` (afgeleid uit uitgevoerde check).
- [x] `sh /config/lynkco-beta5-prep/install_beta5.sh --check` uitgevoerd.
- [x] Python syntax en 10 offline mock-tests geslaagd in GitHub Actions.
- [x] 10/10 offline regressietests op Home Assistant geslaagd (gebruikersuitvoer).
- [x] `ha core check`: `Command completed successfully` (gebruikersuitvoer).
- [x] Hassfest-validatie geslaagd in GitHub Actions.
- [x] HACS-publicatiecheck faalt op GitHub-repositorytopics en uitgeschakelde Issues (geen code-testresultaat); bewust geen repo-instellingen aangepast.

## Installeren (alleen na groene controles)
- [x] `sh /config/lynkco-beta5-prep/install_beta5.sh --apply` uitgevoerd; beta.5 geplaatst, 10/10 regressietests geslaagd (gebruikersuitvoer).
- [x] Nieuwe backupmap: `/config/backups/lynkco-before-beta5-20261123-212900` (volgens uitvoer).
- [ ] Post-installatie `ha core check` nog afzonderlijk bevestigen: deze regel ontbreekt in de geplakte uitvoer.
- [x] Home Assistant na beta.5 installatie herstart (gebruiker bevestigd).
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

### Praktijkbevinding na herstart 24-11-2026
- [x] Home Assistant herstart na beta.5 installatie (gebruiker bevestigd).
- [x] Home Assistant toont Lynk & Co als 'Configureer opnieuw' en vraagt om `msauth://`-omleidings-URL (gebruikersscreenshot).
- [ ] Bestaande integratie opnieuw aanmelden met nieuwe redirect-code; GEEN codes of tokens in GitHub vastleggen.
- [ ] Na succesvolle heraanmelding vaststellen of en waarom de refresh tokens na herstart zijn afgewezen; eerst veilig gefilterde HA logs bekijken.
- [ ] Controleren of geïntegreerde entiteiten na heraanmelding terugkomen, voordat een voertuigcommando wordt gebruikt.
