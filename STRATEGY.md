Hier ist der Verkabelungsplan für das bestätigte ICS-43434-Mikrofon und den MAX98357A Verstärker am Raspberry Pi 5. Die frühere Bezeichnung SPH0645 war nicht korrekt.

Da sich beide Bauteile den Takt teilen, müssen Sie einige Kabel doppelt belegen (am besten auf einer kleinen Rasterplatine zusammenführen oder die Kabel direkt am Pi-Pin zusammenlöten).

---

## 📋 Der Pin-Belegungsplan

| Bauteil        | Pin auf dem Bauteil    | Verbindung zum Raspberry Pi 5 | Pin-Nummer (Physisch)  | Info                                         |
| -------------- | ---------------------- | ----------------------------- | ---------------------- | -------------------------------------------- |
| Beide          | GND                    | GND (Ground / Masse)          | Pin 6 (oder 9, 14, 20) | Stromkreis schließen                         |
| Mikrofon       | 3V                     | 3.3V Power                    | Pin 1 (oder 17)        | Strom für das Mikrofon                       |
| Verstärker     | Vin                    | 5V Power                      | Pin 2 (oder 4)         | 5V liefert mehr Lautstärke (3W)              |
|                |                        |                               |                        |                                              |
| Beide (Takt 1) | BCLK                   | GPIO 18 (PCM_CLK)             | Pin 12                 | Wichtig: Beide BCLKs an diesen einen Pin!    |
| Beide (Takt 2) | WS (Mikro) / LRC (Amp) | GPIO 19 (PCM_FS)              | Pin 35                 | Wichtig: Beide an diesen einen Pin!          |
|                |                        |                               |                        |                                              |
| Mikrofon       | DOUT                   | GPIO 20 (PCM_DIN)             | Pin 38                 | Audio-Eingang (Daten zum Pi)                 |
| Verstärker     | DIN                    | GPIO 21 (PCM_DOUT)            | Pin 40                 | Audio-Ausgang (Daten zum Lautsprecher)       |
|                |                        |                               |                        |                                              |
| Mikrofon       | SEL / LR               | GND                           | —                      | Beim ICS-43434: linker Kanal; nicht offen lassen |
| Verstärker     | GAIN                   | Freilassen                    | —                      | 9 dB Verstärkung |
| Verstärker     | SD / EN                | Abhängig vom Breakout-Board    | —                      | Low schaltet ab; offen nur mit geeignetem Pull-up auf dem Board |

## Verkabelungsdiagramm

Die Pin-Nummern beziehen sich auf die physischen Pins der 40-poligen GPIO-Leiste.

```text
Raspberry Pi 5                  Bauteil / Anschluss

Pin  1 · 3.3 V ──────────────── ICS-43434 · 3V
Pin  2 · 5 V   ──────────────── MAX98357A · VIN

Pin  6 · GND   ──────┬───────── ICS-43434 · GND
                     ├───────── ICS-43434 · SEL / LR
                     └───────── MAX98357A · GND

Pin 12 · GPIO18 ─────┬───────── ICS-43434 · BCLK
                     └───────── MAX98357A · BCLK

Pin 35 · GPIO19 ─────┬───────── ICS-43434 · LRCLK / WS
                     └───────── MAX98357A · LRC

Pin 38 · GPIO20 ◀────────────── ICS-43434 · DOUT
Pin 40 · GPIO21 ──────────────▶ MAX98357A · DIN

MAX98357A                      Lautsprecher (4 Ω / 5 W)

Speaker + ──────────────────── +
Speaker − ──────────────────── −
```

**SD / EN gehört nicht an Pin 40.** Die genaue SD-Beschaltung hängt vom
Verstärkerboard ab (siehe Tabelle). GAIN bleibt offen.

### Grafische Ansicht

![Verkabelung: Raspberry Pi 5 mit ICS-43434, MAX98357A und Lautsprecher](mermaid-diagram.png)

## Audio-Tests

Im Terminal auf dem Pi ausführen. Die folgenden Tests verwenden ALSA direkt und
48 kHz, zwei Kanäle, S32_LE. Das sind die Formate des Google-Voice-HAT-Treibers.
Dateien unter `/tmp` sind temporär. Vor jedem Test anhand der Gerätelisten prüfen,
ob die Voice-HAT-Karte weiterhin Karte 0 ist; gegebenenfalls `hw:0,0` anpassen.

### 1. Geräte erkennen

```bash
aplay -l
arecord -l
pinctrl get 18-21
```

Erwartet: Voice-HAT für Wiedergabe und Aufnahme; GPIO18 = I2S0_SCLK,
GPIO19 = I2S0_WS, GPIO20 = I2S0_SDI0, GPIO21 = I2S0_SDO0.
Eine registrierte Soundkarte beweist noch nicht, dass die Bauteile angeschlossen sind.

### 2. Lautsprecher: leiser Testton

440 Hz, zwei Sekunden, 1 % Spitzenamplitude auf beiden Kanälen:

```bash
python3 - <<'PY'
import math, struct, wave
with wave.open('/tmp/speaker-test.wav', 'wb') as w:
    w.setparams((2, 4, 48000, 0, 'NONE', 'not compressed'))
    w.writeframes(b''.join(
        struct.pack('<ii', *([int((2**31 - 1) * 0.01 *
            math.sin(2 * math.pi * 440 * i / 48000))] * 2))
        for i in range(96000)
    ))
PY
aplay -D hw:0,0 /tmp/speaker-test.wav
```

Erwartet: hörbarer leiser Ton. Erfolgreiches `aplay` allein bestätigt keine
Schallausgabe. Falls unklar, nach Prüfung der Verkabelung die Amplitude im
Generator von `0.01` auf `0.05` erhöhen und die Datei erneut erzeugen.

### 3. Mikrofon: zehn Sekunden aufnehmen

Sprechen, kurz pausieren, wieder sprechen. Bei SEL/LR an GND sollte beim
ICS-43434 der linke Kanal reagieren.

```bash
arecord -D hw:0,0 -r 48000 -f S32_LE -c 2 \
  -d 10 -V stereo /tmp/mic-test.wav
```

Digitale Messwerte prüfen; dies funktioniert auch ohne funktionierenden Lautsprecher:

```bash
python3 - <<'PY'
import array, math, sys, wave
with wave.open('/tmp/mic-test.wav', 'rb') as w:
    assert w.getsampwidth() == 4, 'S32_LE-Aufnahme erforderlich'
    channels = w.getnchannels()
    samples = array.array('i', w.readframes(w.getnframes()))
    if sys.byteorder != 'little':
        samples.byteswap()
for channel in range(channels):
    values = samples[channel::channels]
    peak = max(map(abs, values), default=0)
    rms = math.sqrt(sum(v*v for v in values) / max(1, len(values)))
    db = 20 * math.log10(rms / 2**31) if rms else float('-inf')
    print(f'Kanal {channel}: Peak={peak}, RMS={db:.1f} dBFS, '
          f'Nichtnull={sum(v != 0 for v in values)}')
PY
```

Nur Nullen auf beiden Kanälen bedeuten digitale Stille. Nichtnullwerte allein
beweisen noch kein brauchbares Audiosignal; die Reaktion auf Sprache prüfen.
Nach erfolgreichem Lautsprechertest kann die Aufnahme mit
`aplay -D hw:0,0 /tmp/mic-test.wav` abgehört werden.

### 4. Aufnahme und Wiedergabe gleichzeitig

Zuerst die Testtondatei aus Schritt 2 erzeugen. Keine Live-Rückkopplung:
Es wird nur der gespeicherte Ton abgespielt.

```bash
python3 - <<'PY'
import subprocess, time
rec = subprocess.Popen([
    'arecord', '-D', 'hw:0,0', '-r', '48000', '-f', 'S32_LE',
    '-c', '2', '-d', '4', '/tmp/mic-duplex-test.wav'
])
time.sleep(0.5)
play = subprocess.run(['aplay', '-D', 'hw:0,0', '/tmp/speaker-test.wav'])
print('Playback exit:', play.returncode, 'Recording exit:', rec.wait())
PY
```

Die Messung aus Schritt 3 mit `/tmp/mic-duplex-test.wav` wiederholen.
Erwartet: beide Prozesse erfolgreich; bei funktionierender Hardware ist der
Testton in der Aufnahme vorhanden. Dies prüft den gleichzeitigen Betrieb.

## Ursprünglicher Fehlerzustand vom 01.10.2026

- Nutzerbericht: kein Ton hörbar, Mikrofon-Test ohne erkennbare Funktion.
- Raspberry Pi 5, Kernel `6.12.47+rpt-rpi-2712`.
- Voice-HAT ist Karte 0 und stellt Aufnahme und Wiedergabe bereit.
- GPIO18–21 sind korrekt als I²S-Pins konfiguriert.
- Die vorhandene Testtondatei enthält ein korrektes, nicht stummes Signal.
- Die zehnsekündige Mikrofondatei enthält auf beiden Kanälen ausschließlich Nullen.
- Ein zusätzlicher gleichzeitiger Test wurde ausgeführt: beide Prozesse endeten
  mit Code 0, aber auch diese viersekündige Aufnahme enthält ausschließlich Nullen.
  Ob der Ton bei diesem zusätzlichen Lauf hörbar war, ist noch nicht bestätigt.
- Die geprüften Kernelmeldungen zeigen Start und Ende der Verstärkeransteuerung,
  keine zugehörigen Audiofehler. Das bestätigt keine elektrische Verbindung.
- Der Treiber schaltet GPIO16 für SD/MODE; die Meldung „Enabling audio amp“
  beweist deshalb nicht, dass SD am tatsächlichen Verstärker aktiv ist.
- `/boot/firmware/config.txt` enthält `dtoverlay=googlevoicehat-soundcard` und
  `dtoverlay=i2s-mems-microphone`. Für Letzteres fehlt die gleichnamige `.dtbo`.
  Die Boot-Konfiguration wurde bislang nicht geändert. Die fehlende Overlaydatei
  erklärt für sich allein nicht die Stille der bereits registrierten Voice-HAT-Karte.

## Ergebnis: Ein- und Ausgabe funktionieren

### Update nach Korrektur der Verstärkerverdrahtung

- Nutzer bestätigt: Mikrofon ist ICS-43434, Stiftleiste verlötet.
- SD war laut Nutzer vermutlich an physischem Pin 40 angeschlossen. Nach Hinweis
  auf Pin 40 → DIN wurde die Verdrahtung korrigiert; die genaue aktuelle SD-Beschaltung
  ist noch nicht bestätigt.
- Wiederholung des gleichzeitigen Tests: Aufnahme und Wiedergabe endeten mit Code 0.
- `/tmp/mic-rewired-test.wav`: linker Kanal 191178 von 192000 Samples ungleich null,
  Minimum −142068736, Maximum 66616832; rechter Kanal ausschließlich null.
- Nutzer bestätigt anschließend: Lautsprecher-Testton hörbar.
- Nutzer bestätigt außerdem: Sprachaufnahme und anschließende Wiedergabe funktionieren.
  Damit ist der grundlegende Audiopfad vom Mikrofon über den Pi zum Lautsprecher geprüft.
- Funktionierende Einstellungen: Karte 0, Gerät 0, 48000 Hz, S32_LE, zwei Kanäle;
  Mikrofon liefert den linken Kanal. Gleichzeitiges Öffnen von Aufnahme und
  Wiedergabe wurde ebenfalls ohne ALSA-Fehler getestet.
- Für die Behebung wurde die Verkabelung korrigiert; Software- oder Bootänderungen
  waren während dieser Fehlersuche nicht erforderlich.

Bestätigter Sprachtest (während der fünf Sekunden sprechen):

```bash
arecord -D hw:0,0 -r 48000 -f S32_LE -c 2 -d 5 /tmp/voice-test.wav
aplay -D hw:0,0 /tmp/voice-test.wav
```

### Referenz bei erneutem Ausfall

Die folgenden Schritte sind nur bei einem erneuten Fehler nötig.

1. Genaue Verstärkerplatine und deren SD-Beschaltung prüfen. Prüfen, ob die
   Stiftleisten verlötet sind: lose Stifte in Platinenlöchern sind kein zuverlässiger Kontakt.
2. Pi herunterfahren und Strom trennen, bevor Kabel geändert werden. Physische
   Pin-Nummern nicht mit GPIO-Nummern verwechseln. Gemeinsame Masse und die
   beiden Verzweigungen von Pin 12 und Pin 35 zuerst auf Durchgang prüfen.
3. Anschließend im eingeschalteten Zustand die Versorgung direkt an den Boards
   gegen deren GND messen: Mikrofon etwa 3,3 V, Verstärker etwa 5 V.
   Keine 5 V an Mikrofonversorgung oder Pi-GPIOs anlegen.
4. SEL/LR am Mikrofon fest an GND legen. SD/EN am Verstärker prüfen:
   Low bedeutet Abschaltung. Ob offen korrekt ist, hängt vom Pull-up des Boards ab.
   Lautsprecher ausschließlich zwischen Speaker+ und Speaker− anschließen,
   keinen der beiden Lautsprecheranschlüsse mit GND verbinden.
5. Falls Versorgung und Kontakte stimmen, während eines laufenden Audiotests
   mit Oszilloskop/Logikanalysator direkt an beiden Boards messen:
   LRCLK etwa 48 kHz, BCLK bei 64 Takten pro Stereo-Frame etwa 3,072 MHz.
   Ein statischer `pinctrl`-Pegel oder Multimeterwert beweist keinen korrekten Takt.
6. Sind Takte vorhanden: Daten auf GPIO21 → Amp-DIN beim Ton und Mikrofon-DOUT
   → GPIO20 bei Aufnahme prüfen. Fehlende Takte lenken die Suche zum Pi/Controller;
   Takte am Pi, aber nicht am Board, zur Verdrahtung. Takte und Versorgung am
   Mikrofon, aber keine Daten, lenken die Suche auf Mikrofon, SEL und dessen Kontakte.
7. Bei Bedarf jeweils ein Modul vollständig abklemmen (nur stromlos) und einzeln
   testen, um eine Belastung oder einen Kurzschluss des gemeinsamen Takts einzugrenzen.

Quellen:

- [Raspberry-Pi-Voice-HAT-Treiber: Formate und SD-Steuerung](https://github.com/raspberrypi/linux/blob/rpi-6.12.y/sound/soc/bcm/googlevoicehat-codec.c)
- [Voice-HAT-Overlay: I²S-Taktgeber und GPIO16](https://github.com/raspberrypi/linux/blob/rpi-6.12.y/arch/arm/boot/dts/overlays/googlevoicehat-soundcard-overlay.dts)
- [ICS-43434-Datenblatt: Kanalwahl und I²S-Takt](https://invensense.tdk.com/wp-content/uploads/2016/02/DS-000069-ICS-43434-v1.2.pdf)
- [Adafruit MAX98357A: SD/MODE, Pull-up und Lautsprecheranschlüsse](https://learn.adafruit.com/adafruit-max98357-i2s-class-d-mono-amp/pinouts)
