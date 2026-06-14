# Zadání: acoustic-marten-deterrent

## Kontext a cíl
Implementuj akustický plašič kun pro Raspberry Pi. Zařízení přehrává nepravidelný,
nepříjemný SLYŠITELNÝ zvuk (ne ultrazvuk), aby se kuna v objektu nezdržovala.
V objektu nikdo není; majitel se k Pi připojuje vzdáleně přes Raspberry Pi Connect
a zařízení může kdykoli vypnout/zapnout.

## Co máš udělat (souhrn)
1. Pracuj v AKTUÁLNÍ složce `acoustic-marten-deterrent`.
2. Vytvoř kompletní funkční projekt podle požadavků níže.
3. Inicializuj git a založ NOVÉ VEŘEJNÉ GitHub repo `austy246/acoustic-marten-deterrent`,
   zacommituj a pushni (postup v sekci "Git / GitHub").

## Platforma a stack
- Cílová zařízení: **Raspberry Pi 3 i Raspberry Pi 4** (Raspberry Pi OS, Bookworm i Bullseye).
- Jazyk: **Python 3** (musí fungovat i na Python 3.9).
- Audio: knihovna `sounddevice` + `numpy`. Výstup přes ALSA na 3,5mm jack Pi,
  s možností zvolit jiné výstupní zařízení (USB zvukovka) v configu.
- Kód musí jít spustit i na běžném PC/notebooku (kvůli testování zvuku), nejen na Pi.

## Funkční požadavky

### Zvukový engine (jádro)
- Generuj zvuk procedurálně, neukládej audio soubory.
- Stavební prvky (náhodně se střídají): rostoucí/klesající chirp (sweep), trylek
  (rychlé střídání dvou tónů), pásmově omezená šumová salva, čistý tón ve středech.
- **Proti habituaci:** každý prvek má náhodnou frekvenci, délku i pořadí; mezi salvami
  jsou NÁHODNÉ pauzy (konfigurovatelné min/max, default nízký duty cycle).
- **Náhodné skoky hlasitosti** mezi salvami (efekt leknutí).
- Frekvenční obsah konfigurovatelný; default ~1–16 kHz. Shora ořezat na `freq_max`
  (default 16 kHz) — výš to akusticky nepřidá a jen hřeje cívku.

### Chování po spuštění (startup sekvence)
- Po startu zařízení **okamžitě začne plašit** — nečeká na žádný externí trigger.
- Na začátku přehraj krátkou **úvodní salvu na nastavení hlasitosti** (default ~5–10 s,
  konfigurovatelné `startup_test_s`): do logu/stdout napiš, že „začínám plašit" a že
  právě běží testovací tón pro nastavení hlasitosti (uživatel si během něj doladí
  `alsamixer` / `master_volume`).
- Po úvodní salvě přejdi do normálního provozu: v **náhodných intervalech** (dané
  `min_gap_s`/`max_gap_s`) spouštěj nepříjemné salvy, které kunu vystrnadí.
- Úvodní salvu lze vypnout configem (`startup_test_s = 0`) — pak se rovnou jede
  normální provoz s náhodnými pauzami.

### Ochrana reproduktoru (důležité)
- Drž digitální rezervu: špičky default ≤ −3 dBFS (konfigurovatelný `peak_ceiling`).
- Na začátku a konci každého prvku krátký fade in/out (default 5 ms), ať repro necvaká.
- Nízký duty cycle (dané pauzami) — cívka mezi salvami chladne.

### Ovládání běhu
- Runtime přepínač přes **stavový soubor** (default `/run/marten/state`, obsah `on`/`off`),
  aby šlo ztlumit bez restartu procesu (kontroluj ho v každé iteraci smyčky).
- Funguje i přes `systemctl start/stop`.
- Čistý shutdown na SIGTERM (zastav přehrávání).

### Bezpečnostní timeout
- Po `max_runtime_hours` (default 12) nepřetržitého běhu se plašič SÁM přepne do "off"
  a čeká na opětovné nahození (přes stavový soubor nebo restart služby).
- Pojistka pro případ, že vypadne internet a uživatel se k Pi nedostane přes Connect.

### Volitelný keepalive
- Konfigurovatelný (`keepalive = false` default): velmi tichý tón během pauz, aby
  neusínaly aktivní repro s funkcí auto-standby. U USB-napájených repro netřeba.

### CLI
- `--once` / `--test`: přehraj pár prvků a skonči (pro rychlý test).
- `--list-devices`: vypiš dostupná audio zařízení a skonči.
- `--config PATH`: cesta k configu.

## Konfigurace
Jeden lidsky editovatelný config soubor (preferuj INI přes `configparser` ze stdlib,
ať to nemá závislosti navíc a funguje na všech verzích Pythonu). Klíče min.:
`audio_device`, `sample_rate` (default 44100), `master_volume` (0–1, default 0.7),
`peak_ceiling_dbfs` (default -3), `min_gap_s`, `max_gap_s`, `freq_min`, `freq_max`,
`fade_ms`, `max_runtime_hours`, `keepalive`, `keepalive_level_dbfs`, `state_file`,
`startup_test_s` (default ~5–10, délka úvodní salvy na nastavení hlasitosti; 0 = vypnout).
Přilož `config.example.ini` s komentáři.

## Struktura repa
```
acoustic-marten-deterrent/
├── src/marten_deterrent/        # balíček (engine, config, control, cli)
├── config.example.ini
├── install.sh                   # apt + venv + pip + systemd unit
├── systemd/acoustic-marten-deterrent.service
├── README.md
├── LICENSE                      # MIT
├── .gitignore                   # .venv, __pycache__, *.pyc
└── pyproject.toml               # nebo requirements.txt
```

## Instalace a nasazení
- `install.sh`: nainstaluje `libportaudio2` (apt), vytvoří venv `.venv`, do něj nainstaluje
  `numpy` a `sounddevice`. (POZOR na Bookworm PEP 668 — proto venv, ne systémový pip.)
- systemd unit `acoustic-marten-deterrent.service`:
  - `ExecStart` ukazuje na python z `.venv`.
  - běží pod hlavním uživatelem (musí být ve skupině `audio`), používá ALSA.
  - **Defaultně NEenablovat** (žádný auto-start po bootu) — bezpečnostní rozhodnutí,
    spouští se ručně. V README vysvětli `systemctl start` vs `enable`.

## Obsah README.md
- K čemu to je + upozornění, že je to humánní odpuzování (kunu to nezraní) a že
  TRVALÉ řešení je najít a utěsnit vstupní otvory a odstranit pachové značky.
- Hardware: Pi 3/4 + aktivní reproduktor. Pro malý prostor levný USB-napájený repro
  (např. Genius SP-Q160, vstup 3,5mm jack → kabel jack 3,5mm M–M z Pi). Pro velký
  prostor aktivní PA box (vstup 6,3mm jack/XLR → odpovídající kabel).
- Audio routing: vynutit výstup na jack (`raspi-config` nebo `amixer cset numid=3 1`),
  nastavit hlasitost (`alsamixer`) s rezervou pod clip.
- Instalace (install.sh), spuštění, test (`--once`, `--list-devices`).
- **Vzdálený přístup přes Raspberry Pi Connect:** `sudo apt install rpi-connect-lite`,
  `loginctl enable-linger $USER`, `rpi-connect on`, `rpi-connect signin`; pak na
  connect.raspberrypi.com → Remote shell. Odtud `systemctl start/stop` nebo
  `echo off > /run/marten/state`.
- Reference configu a bezpečnostní poznámky (timeout, sousedi/hlasitost).

## Git / GitHub
- Ověř, že je `gh` přihlášený (`gh auth status`); když ne, napiš uživateli, ať spustí `gh auth login`.
- `git init`, přidej soubory, smysluplný první commit.
- Založ veřejné repo a pushni:
  `gh repo create austy246/acoustic-marten-deterrent --public --source=. --remote=origin --push`
- Description repa: "Raspberry Pi acoustic deterrent that drives stone martens out of buildings with randomised, habituation-resistant sound."

## Akceptační kritéria (definition of done)
- [ ] `python -m marten_deterrent --list-devices` vypíše zařízení (na PC i Pi).
- [ ] `python -m marten_deterrent --once` přehraje několik různých prvků a skončí.
- [ ] Po spuštění zařízení okamžitě začne plašit: oznámí start, přehraje úvodní
      salvu na nastavení hlasitosti a pak jede v náhodných intervalech.
- [ ] Dlouhý běh respektuje stavový soubor i `max_runtime_hours`.
- [ ] Reaguje čistě na SIGTERM.
- [ ] `install.sh` proběhne na čistém Raspberry Pi OS bez chyb.
- [ ] README umožní cizímu člověku zařízení postavit a vzdáleně ovládat.
- [ ] Veřejné repo `austy246/acoustic-marten-deterrent` existuje a má pushnutý kód.

## Poznámky
- Žádný ultrazvuk — jen slyšitelné pásmo (Pi přes jack stejně >~22 kHz neumí).
- Drž kód modulární a otypovaný, ať jde snadno rozšířit (např. pozdější PIR čidlo na GPIO).