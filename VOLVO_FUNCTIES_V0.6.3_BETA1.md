# Volvo-functies / Lynk & Co 01 — v0.6.3-beta.1

Deze ontwikkeltak is bedoeld voor het vervolg in de chat **Volvofuncties vergelijken**.

## Basis die al aanwezig is

- Gebouwd op `main` met integratieversie 0.6.2.
- Als de laatst bekende positie van de auto binnen `zone.home` ligt, worden de relevante live endpoints iedere 5 minuten gepolld:
  - vehicle data
  - locatie
  - charge state / SOC
  - climate
  - deuren/ramen
  - fuel state bij PHEV
- Buiten huis blijft de normale snapshot-polling actief.
- Rijden en actieve climate behouden hun snellere polling.

## Praktijktest remote functies

Bevestigd werkend:
- lichtsignaal / flash lights

Nog niet bevestigd / werkt momenteel niet op de 2022 Lynk & Co 01:
- deur vergrendelen / ontgrendelen
- ramen ventilatiestand
- zonnedak openen / sluiten

Nog niet getest:
- claxon

De Home Assistant-integratie verstuurt bij `honk_horn` één remote commando; er zit geen herhalingslus in HA. Het voertuig/backend kan zelf bepalen hoe lang of hoe vaak het geluid klinkt.

## Security PIN

De deur-lock/unlock-service in de huidige integratie heeft geen PIN-parameter. De 4-cijferige PIN in de code is uitsluitend gekoppeld aan het handschoenenkastje. Een melding bij ramen/zonnedak met `Controleer Security PIN` komt uit de Home Assistant package-tekst en bewijst dus niet dat de PIN ontbreekt of niet is opgeslagen.

Bij de volgende revisie van `lynkco_01_controls.yaml` moet die misleidende tekst worden vervangen door bijvoorbeeld:

> Opdracht niet door voertuig/backend bevestigd. Controleer voertuigvoorwaarden en ondersteuning van deze functie op de Lynk & Co 01 MY2022.

## Volgende ontwikkelstap

1. Deur unlock één keer opnieuw testen en de exacte HA-trace / backendfout bewaren.
2. Daarna bepalen of het huidige remote-command endpoint door de oudere 01 wordt geweigerd.
3. Indien nodig gericht een legacy fallback voor lock/unlock onderzoeken; niet blind alle oude endpoints terugplaatsen.
4. Ramen en zonnedak pas als werkend aanbieden als de backend/opdracht op deze auto aantoonbaar wordt bevestigd.
5. Generieke Security-PIN foutteksten verwijderen uit het bedieningspackage.

Deze branch is bewust een testtak; `main` blijft de stabiele 0.6.2-basis met 5-minuten polling thuis.
