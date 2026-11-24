# MY2022 beta.6: aanmeldlink terug op omleidingsscherm

**Nog niet geïnstalleerd op Home Assistant.** Deze afzonderlijke branch verandert jouw actieve beta.5 niet.

## Oorzaak
Na een vereiste heraanmelding kan Home Assistant het eerste (lege) inlogscherm overslaan of niet meer tonen, waarna alleen het invulveld voor de `msauth://`-URL verschijnt. Daar wordt momenteel niet de bijpassende Lynk-inloglink getoond.

## Reparatie
Beta.6 toont de actuele `auth_url` **ook op het scherm Plak omleidings-URL**, inclusief na een foutmelding. De URL blijft gekoppeld aan dezelfde PKCE-verifier die bij de tokenuitwisseling wordt gebruikt. Dit is uitsluitend een weergave- en aanmeldflowfix: API, auto-opdrachten, sensoren, helpers, dashboard en EV-automatisering zijn ongemoeid gelaten.

De oorzaak waardoor beta.5 überhaupt herauthenticatie vroeg is nog niet vastgesteld.

## Alleen controleren
```sh
cd /config
git clone --depth 1 --single-branch --branch lynkco-my2022-v0.6.3-beta6-login-link https://github.com/mdcvansanten/ha_lynkco_2025.git lynkco-beta6-prep
sh /config/lynkco-beta6-prep/install_beta6.sh --check
```

`--check` verandert niets aan de actuele integratie. Het controleert dat de actieve versie beta.5 is, de Python-syntax, offline regressietests en HA Core-configuratie.

## Alleen na geslaagde controle en bewuste keuze
```sh
sh /config/lynkco-beta6-prep/install_beta6.sh --apply
ha core restart
```

`--apply` maakt een nieuwe integratieback-up onder `/config/backups/lynkco-before-beta6-...`; automatische herstart is uitgeschakeld. Laat daarna de bestaande reauth-flow lopen. Klik geen upstream update uit Marketplace aan en verwijder de huidige integratie niet.

### Afvinkpunten
- [ ] `--check` volledig afgerond zonder wijzigingen in HA (eindstatus `ha core check` nog verifiëren).
- [x] Beta.6 syntax geslaagd; actieve basis beta.5 herkend (terminaluitvoer 24 november 2026).
- [x] Alle 13 offline regressietests geslaagd op Home Assistant (terminaluitvoer 24 november 2026).
- [ ] `--apply` met afzonderlijke back-up uitgevoerd.
- [ ] HA herstart.
- [ ] *Plak omleidings-URL* toont nu bijpassende Lynk-aanmeldlink.
- [ ] Aangemeld via die link; **deel geen code of URL met tokens**.
- [ ] Sensoren, laden en dashboard opnieuw gecontroleerd.
- [ ] Oorzaak onverwachte herauth later via gefilterde logs onderzocht.

**Belangrijk:** Beta.6 lost alleen het ontbreken van de aanmeldlink op; het bewijs dat de originele token-refresh goed werkt in jouw account moet nog uit de praktijk komen.
