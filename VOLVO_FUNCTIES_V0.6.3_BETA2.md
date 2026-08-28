# Volvo-functies / Lynk & Co 01 — v0.6.3-beta.2

Deze testversie bouwt voort op `main` 0.6.2 en de praktijktests met de Lynk & Co 01 MY2022.

## Polling

De 5-minutenpolling thuis uit 0.6.2 blijft behouden. Als de laatst bekende positie binnen `zone.home` ligt, worden de relevante live endpoints iedere 5 minuten vernieuwd:

- vehicle data;
- locatie;
- charge state / SOC;
- climate;
- deuren en ramen;
- fuel state voor PHEV.

Buiten huis blijft de normale snapshot-polling actief. Tijdens rijden en actieve climate blijven de snellere endpoint-specifieke polls actief.

## Praktijktest remote functies MY2022

### Bevestigd werkend

- lichtsignaal / `flash_lights`.

### Testfunctie — momenteel niet bevestigd

- deur vergrendelen / ontgrendelen;
- ramen ventileren / sluiten;
- zonnedak openen / sluiten.

Deze functies blijven alleen als gecontroleerde testfunctie beschikbaar. Een niet-veranderde status na het commando geldt niet als bewijs dat de functie werkt.

### Nog te testen

- claxon / `honk_horn`.

Home Assistant verstuurt bij claxon één remote commando. Er zit geen herhalingslus in de integratie.

## Security PIN

De huidige `lock_door`- en `unlock_door`-services hebben geen PIN-parameter. De 4-cijferige PIN in de integratiecode hoort uitsluitend bij het vergrendelen van het handschoenenkastje. Daarom mag een mislukte deur-, raam- of zonnedakopdracht niet meer als een ontbrekende Security PIN worden uitgelegd.

De bijbehorende dashboard/package-versie gebruikt voortaan de melding:

> Opdracht niet door voertuig/backend bevestigd. Controleer voertuigvoorwaarden en ondersteuning van deze functie op de Lynk & Co 01 MY2022.

## Teststrategie

1. Lichtsignaal gebruiken als bekende werkende referentie.
2. Deur ontgrendelen één keer gecontroleerd testen en de Home Assistant trace/log bewaren als de status niet verandert.
3. Daarna pas deur vergrendelen, ramen en zonnedak afzonderlijk testen.
4. Niet herhaaldelijk dezelfde mislukte remote opdracht versturen.
5. Een legacy fallback alleen toevoegen als uit de backendfout blijkt dat het huidige endpoint daadwerkelijk niet geschikt is voor MY2022.

## Dashboard/package

De begeleidende Auto-dashboardversie toont daarnaast de actualiteit van Lynk-data. Thuis wordt circa iedere 5 minuten nieuwe data verwacht; dit maakt zichtbaar of een bedieningsprobleem mogelijk alleen door verouderde status wordt veroorzaakt.

`main` blijft de stabiele 0.6.2-basis. Deze branch is uitsluitend voor gecontroleerde MY2022-tests.
