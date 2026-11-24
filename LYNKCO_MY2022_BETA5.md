# Lynk & Co 01 MY2022 — beta.5 sessiestabiliteit

**STATUS: TESTKANDIDAAT. Nog niet geïnstalleerd of getest op de Lynk & Co 01 MY2022.**

Deze branch is afzonderlijk vanaf beta.4 gemaakt en wijzigt geen bestanden op de Raspberry Pi. De bestaande `main`, beta.3 en beta.4 blijven beschikbaar.

## Wat beta.5 toevoegt bovenop beta.4
- Een `401` krijgt hoogstens één tokenvernieuwing en één herhaling van de betrokken aanvraag. Een gedeelde async-lock voorkomt gelijktijdige vernieuwingen van hetzelfde token.
- Bij een `403` wordt **alleen** een sessieclaim uitgevoerd wanneer exact dat endpoint eerder succesvol werkte; onbekende/experimentele MY2022-endpoints leiden niet tot claimen.
- Maximaal één sessieclaim per 60 seconden. `validate-session` antwoord `valid: false` betekent geen succesvolle claim.
- Als het claimen lukt, wordt dezelfde oorspronkelijke aanvraag eenmaal herhaald. Een aanhoudende `403` direct na een succesvolle claim verwijdert die endpoint uit de lijst van eerder werkende endpoints.
- Alle API-aanvragen, tokenvernieuwingen en sessievalidaties hebben nu een grens van 30 seconden.
- Definitieve tokenweigering (4xx behalve 429) leidt tot Home Assistant Reparaties; 429, 5xx, time-outs en netwerkstoringen gelden als tijdelijk.
- De coordinator vernieuwt niet meer bij willekeurige fouten opnieuw een token (voorkomt onnodig herauthenticatieverkeer).
- Opstart-/reconnectfouten bij tijdelijke tokenstoringen worden door Home Assistant opnieuw geprobeerd.

## Bewust ongewijzigd
- Speciale MY2022 commando-endpoints, succesvolle vergrendelen/ontgrendelen, lichtsignaal en claxon.
- Experimenten raamventilatie en zonnedak: nog niet werkend verklaard; geen speculatieve legacy fallback.
- 3/8/18/30 seconde targeted readback, companion 0.7.0-beta.12 en rode timeoutfeedback.
- Autarco, Home Assistant EMS, EV-laadregeling, entiteitnamen en bestaande dashboards/packages.
- Upstream model/feature gating en gegroepeerde deur- en raamsensoren.
- Lynk app emulator headers / firmware-specifieke waarden. Geen ongeteste migratie naar app header 2.67.0.

## Waarschuwing telefoonapp
Het opnieuw claimen van de sessie kan de officiële Lynk & Co-app op je telefoon uitloggen. De huidige cloud-API lijkt één actieve sessie toe te staan. Dit mechanisme herstelt Home Assistant, niet gelijktijdig gebruik van beide apps. Als je de officiële app wilt blijven gebruiken, moet dit gedrag bewust worden beoordeeld.

## Installatie vanaf de terminal (pas na de check)
1. De volledige HA back-up van 23 november 2026 is volgens de gebruiker lokaal en op OneDrive aanwezig. Bewaar de rollback-map van beta.4: `/config/backups/lynkco-before-beta4-20261123-171943`.
2. Clone de **aparte** beta.5 branch (één keer):

```sh
cd /config
git clone --depth 1 --single-branch --branch lynkco-my2022-v0.6.3-beta5-session https://github.com/mdcvansanten/ha_lynkco_2025.git lynkco-beta5-prep
sh /config/lynkco-beta5-prep/install_beta5.sh --check
```

3. `--check` controleert Python AST, actieve versie, offline unittests en `ha core check`. Er wordt niets aan de werkende integratie gewijzigd.
4. Als en alleen als alle controles geslaagd zijn, en je zelf wilt activeren:

```sh
sh /config/lynkco-beta5-prep/install_beta5.sh --apply
ha core restart
```

5. `--apply` maakt een nieuwe LynkCo-back-up onder `/config/backups/lynkco-before-beta5-...`, behoudt dashboard/packages en voert een tweede `ha core check` uit. Herstart gebeurt niet automatisch.

### Tests na de herstart
- [ ] Integratie 0.6.3-beta.5 beschikbaar en geen Reparaties-melding.
- [ ] SOC/laadstatus/GPS/klimaat en EV-dashboard werken zoals vóór de wijziging.
- [ ] Vergrendelen en ontgrendelen geven readback, knoppen blokkeren en komen weer vrij.
- [ ] Claxon/lichtsignaal geven geen fout (fire-and-forget wordt niet als bevestigde status voorgesteld).
- [ ] De bestaande 30s foutindicatie bij geen teruglezing werkt.
- [ ] Geen nieuw onbedoeld motorstart-/climate gedrag; alle voertuigvoorwaarden blijven gelden.
- [ ] Bij feitelijk aanwezige 401: refresh één keer, daarna weer normale sensoren (geen tokens in logs delen).
- [ ] Alleen wanneer de officiële app de sessie echt heeft overgenomen: na bekende 403 kan HA de sessie terugclaimen. Verwacht dat telefoonapp dan weer uitgelogd kan zijn.
- [ ] Een nieuwe/experimentele MY2022-endpoint met 403 triggert geen sessieclaim.
- [ ] Time-outs/429 leiden niet tot onterechte reparatie-reauth.
- [ ] Bij problemen: met HA gestopt `custom_components/lynkco` herstellen uit nieuw aangemaakte back-up; daarna HA starten.

## Beperkingen
De unit tests zijn offline mocks; ze testen geen echte Lynk backend of automotor. Deze code is daarom nog geen bewezen stabiele productieversie. Geen automatische installaties vanaf Marktplaats/upstream `b12e/ha_lynkco_2025` uitvoeren bovenop deze fork.
