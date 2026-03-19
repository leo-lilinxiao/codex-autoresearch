<p align="center">
  <img src="../../image/banner.png" width="700" alt="Codex Autoresearch">
</p>

<h2 align="center"><b>Aim. Iterate. Arrive.</b></h2>

<p align="center">
  <i>Die autonome zielgesteuerte Experimentier-Engine fuer Codex.</i>
</p>

<p align="center">
  <a href="https://developers.openai.com/codex/skills"><img src="https://img.shields.io/badge/Codex-Skill-blue?logo=openai&logoColor=white" alt="Codex Skill"></a>
  <a href="https://github.com/leo-lilinxiao/codex-autoresearch"><img src="https://img.shields.io/github/stars/leo-lilinxiao/codex-autoresearch?style=social" alt="GitHub Stars"></a>
  <a href="../../LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License"></a>
</p>

<p align="center">
  <a href="../../README.md">English</a> ·
  <a href="README_ZH.md">🇨🇳 中文</a> ·
  <a href="README_JA.md">🇯🇵 日本語</a> ·
  <a href="README_KO.md">🇰🇷 한국어</a> ·
  <a href="README_FR.md">🇫🇷 Français</a> ·
  <b>🇩🇪 Deutsch</b> ·
  <a href="README_ES.md">🇪🇸 Español</a> ·
  <a href="README_PT.md">🇧🇷 Português</a> ·
  <a href="README_RU.md">🇷🇺 Русский</a>
</p>

<p align="center">
  <a href="#schnellstart">Schnellstart</a> ·
  <a href="#was-es-tut">Was es tut</a> ·
  <a href="#architektur">Architektur</a> ·
  <a href="#modi">Modi</a> ·
  <a href="#konfiguration">Konfiguration</a> ·
  <a href="#laufuebergreifendes-lernen">Lernen</a> ·
  <a href="#parallele-experimente">Parallel</a> ·
  <a href="../GUIDE.md">Bedienungsanleitung</a> ·
  <a href="../EXAMPLES.md">Rezepte</a>
</p>

---

## Schnellstart

**1. Installation:**

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
cp -r codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

Oder verwenden Sie den Skill-Installer in Codex:
```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

**2. Oeffnen Sie Codex in Ihrem Projekt und sagen Sie, was Sie wollen:**

```text
$codex-autoresearch
Alle `any`-Typen in meinem TypeScript-Code eliminieren
```

**3. Codex analysiert, bestaetigt und iteriert dann autonom:**

```
Codex: 47 `any`-Vorkommen in src/**/*.ts gefunden.

       Bestaetigt:
       - Ziel: `any`-Typen in src/**/*.ts eliminieren
       - Metrik: Anzahl von `any` (aktuell: 47), Richtung: senken
       - Verifikation: grep-Zaehlung + tsc --noEmit als Schutz

       Zu bestaetigen:
       - Bis auf null laufen lassen, oder auf N Iterationen begrenzen?

       Antworten Sie "go" zum Starten, oder sagen Sie mir, was geaendert werden soll.

Du:    Go, lass es die ganze Nacht laufen.

Codex: Start -- Ausgangswert: 47. Iteration bis zur Unterbrechung.
```

Jede Verbesserung akkumuliert sich. Jeder Fehlschlag wird zurueckgesetzt. Alles wird protokolliert.

Siehe [INSTALL.md](../INSTALL.md) fuer weitere Installationsoptionen. Siehe [GUIDE.md](../GUIDE.md) fuer die vollstaendige Bedienungsanleitung.

---

## Was es tut

Ein Codex-Skill, der eine Aendern-Verifizieren-Entscheiden-Schleife auf Ihrer Codebasis ausfuehrt. Jede Iteration fuehrt eine atomare Aenderung durch, verifiziert sie anhand einer mechanischen Metrik und behaelt oder verwirft das Ergebnis. Fortschritte akkumulieren sich in git; Fehlschlaege werden automatisch zurueckgesetzt. Funktioniert mit jeder Sprache, jedem Framework, jedem messbaren Ziel.

Inspiriert von [Karpathys autoresearch](https://github.com/karpathy/autoresearch)-Prinzipien, verallgemeinert ueber ML hinaus.

### Warum dieses Projekt existiert

Karpathys autoresearch hat bewiesen, dass eine einfache Schleife -- aendern, verifizieren, behalten oder verwerfen, wiederholen -- ML-Training ueber Nacht von der Ausgangsbasis zu neuen Hoechstwerten bringen kann. codex-autoresearch verallgemeinert diese Schleife auf alles in der Softwareentwicklung, das eine Zahl hat. Testabdeckung, Typfehler, Latenz, Lint-Warnungen -- wenn es eine Metrik gibt, kann autonom iteriert werden.

---

## Architektur

```
              +---------------------+
              |  Environment Probe  |  <-- Phase 0: detect CPU/GPU/RAM/toolchains
              +---------+-----------+
                        |
              +---------v-----------+
              |  Session Resume?    |  <-- check for prior run artifacts
              +---------+-----------+
                        |
              +---------v-----------+
              |   Read Context      |  <-- read scope + lessons file
              +---------+-----------+
                        |
              +---------v-----------+
              | Establish Baseline  |  <-- iteration #0
              +---------+-----------+
                        |
         +--------------v--------------+
         |                             |
         |  +----------------------+   |
         |  | Choose Hypothesis    |   |  <-- consult lessons + perspectives
         |  | (or N for parallel)  |   |      filter by environment
         |  +---------+------------+   |
         |            |                |
         |  +---------v------------+   |
         |  | Make ONE Change      |   |
         |  +---------+------------+   |
         |            |                |
         |  +---------v------------+   |
         |  | git commit           |   |
         |  +---------+------------+   |
         |            |                |
         |  +---------v------------+   |
         |  | Run Verify + Guard   |   |
         |  +---------+------------+   |
         |            |                |
         |        improved?            |
         |       /         \           |
         |     yes          no         |
         |     /              \        |
         |  +-v------+   +----v-----+ |
         |  |  KEEP  |   | REVERT   | |
         |  |+lesson |   +----+-----+ |
         |  +--+-----+        |       |
         |      \            /         |
         |   +--v----------v---+      |
         |   |   Log Result    |      |
         |   +--------+--------+      |
         |            |               |
         |   +--------v--------+      |
         |   |  Health Check   |      |  <-- disk, git, verify health
         |   +--------+--------+      |
         |            |               |
         |     3+ discards?           |
         |    /             \         |
         |  no              yes       |
         |  |          +----v-----+   |
         |  |          | REFINE / |   |  <-- pivot-protocol escalation
         |  |          | PIVOT    |   |
         |  |          +----+-----+   |
         |  |               |         |
         +--+------+--------+         |
         |         (repeat)           |
         +----------------------------+
```

Die Schleife laeuft bis zur Unterbrechung (unbegrenzt) oder fuer genau N Iterationen (begrenzt durch `Iterations: N`).

**Pseudocode:**

```
PHASE 0: Umgebung pruefen, auf Sitzungswiederaufnahme pruefen
PHASE 1: Kontext + Erkenntnisdatei einlesen

LOOP (endlos oder N-mal):
  1. Aktuellen Zustand + git-Historie + Ergebnisprotokoll + Erkenntnisse ueberpruefen
  2. EINE Hypothese waehlen (Perspektiven anwenden, nach Umgebung filtern)
     -- oder N Hypothesen im parallelen Modus
  3. EINE atomare Aenderung durchfuehren
  4. git commit (vor der Verifikation)
  5. Mechanische Verifikation + Guard ausfuehren
  6. Verbessert -> behalten (Erkenntnis extrahieren). Verschlechtert -> git reset. Abgestuerzt -> reparieren oder ueberspringen.
  7. Ergebnis protokollieren
  8. Health Check (Speicherplatz, git, Verifikationsgesundheit)
  9. Bei 3+ Verwerfungen -> REFINE; 5+ -> PIVOT; 2 PIVOTs -> Websuche
  10. Wiederholen. Nie anhalten. Nie fragen.
```

---

## Modi

Sieben Modi, ein einheitliches Aufrufmuster: `$codex-autoresearch` gefolgt von einem Satz, der beschreibt, was Sie wollen. Codex erkennt den Modus automatisch und fuehrt Sie durch ein kurzes Gespraech zur Vervollstaendigung der Konfiguration.

| Modus | Einsatzzweck | Stoppt wenn |
|-------|--------------|-------------|
| `loop` | Sie haben ein messbares Optimierungsziel | Unterbrechung oder N Iterationen |
| `plan` | Sie haben ein Ziel, aber keine Konfiguration | Konfigurationsblock ist generiert |
| `debug` | Sie brauchen eine Ursachenanalyse mit Beweisen | Alle Hypothesen getestet oder N Iterationen |
| `fix` | Etwas ist kaputt und muss repariert werden | Fehlerzahl erreicht null |
| `security` | Sie brauchen ein strukturiertes Schwachstellen-Audit | Alle Angriffsflaechen abgedeckt oder N Iterationen |
| `ship` | Sie brauchen eine kontrollierte Release-Verifikation | Alle Pruefpunkte bestanden |
| `exec` | CI/CD-Pipeline, kein Mensch verfuegbar | N Iterationen (immer begrenzt), JSON-Ausgabe |

**Schnellauswahl:**

```
"Ich will X verbessern"             -->  loop  (oder plan, wenn die Metrik unklar ist)
"Etwas ist kaputt"                  -->  fix   (oder debug, wenn die Ursache unbekannt ist)
"Ist dieser Code sicher?"           -->  security
"Ab in die Produktion"              -->  ship
codex exec --skill ...              -->  exec  (CI/CD, kein Assistent)
```

---

## Konfiguration

### Pflichtfelder (Modus `loop`)

| Feld | Typ | Beispiel |
|------|-----|---------|
| `Goal` | Was erreicht werden soll | `Reduce type errors to zero` |
| `Scope` | Datei-Globs zum Aendern | `src/**/*.ts` |
| `Metric` | Welche Zahl verfolgt wird | `type error count` |
| `Direction` | `higher` oder `lower` | `lower` |
| `Verify` | Shell-Befehl, der die Metrik liefert | `tsc --noEmit 2>&1 \| wc -l` |

### Optionale Felder

| Feld | Standardwert | Zweck |
|------|-------------|-------|
| `Guard` | keiner | Sicherheitsbefehl, der immer bestehen muss (Regressionspraevention) |
| `Iterations` | unbegrenzt | Auf N Iterationen begrenzen |
| `Run tag` | auto | Bezeichnung fuer diesen Lauf |
| `Stop condition` | keiner | Benutzerdefinierte Regel fuer fruehen Abbruch |

Fehlende Pflichtfelder loesen einen interaktiven Assistenten aus, der Ihr Repository analysiert und immer erst Ihre Bestaetigung einholt, bevor er startet (bis zu 5 Runden). Sie muessen die Feldnamen nicht kennen.

### Doppelte Verifikation

Zwei Befehle dienen unterschiedlichen Zwecken:

- **Verify** = "Hat sich die Zielmetrik verbessert?" (misst den Fortschritt)
- **Guard** = "Ist etwas anderes kaputtgegangen?" (verhindert Regressionen)

```text
Verify: pytest --cov=src --cov-report=term 2>&1 | grep TOTAL | awk '{print $NF}'   # ist die Abdeckung gestiegen?
Guard: npx tsc --noEmit                                                              # bestehen die Typen noch?
```

Wenn Verify besteht, aber Guard fehlschlaegt, wird die Aenderung ueberarbeitet (bis zu 2 Versuche), dann zurueckgesetzt. Von Guard geschuetzte Dateien werden nie geaendert.

---

## Schnelle Entscheidungshilfe

| Sie wollen... | Modus | Schluesselkonfiguration |
|---------------|-------|------------------------|
| Eine Zahl ueber Nacht in eine Richtung treiben | `loop` | Goal + Metric + Verify |
| Herausfinden, welche Metrik verfolgt werden soll | `plan` | Nur ein Goal |
| Finden, warum etwas kaputt ist | `debug` | Scope + Symptom |
| Fehlgeschlagene Tests/Typen/Lint bestehen lassen | `fix` | Target-Befehl |
| Code auf Schwachstellen pruefen | `security` | Scope + Focus |
| Mit Zuversicht veroeffentlichen | `ship` | Sagen Sie "ab in die Produktion" oder "erst Probelauf" |
| In CI/CD ohne Interaktion ausfuehren | `exec` | Alle Felder im Voraus + Iterations |

---

## Details der Modi

### loop

Der Standardmodus. Iteriert auf ein messbares Ziel hin.

```
Du:    Alle `any`-Typen in meinem TypeScript-Code eliminieren

Codex: 47 `any` in src/**/*.ts gefunden.

       Bestaetigt:
       - Ziel: alle `any`-Typen eliminieren
       - Metrik: Anzahl von `any` (aktuell: 47), Richtung: senken
       - Verifikation: grep-Zaehlung, Schutz: tsc --noEmit

       Zu bestaetigen:
       - Bis auf null laufen lassen, oder auf N Iterationen begrenzen?

       Antworten Sie "go" zum Starten.

Du:    Go, die ganze Nacht.
```

### plan

Wandelt ein vages Ziel in eine validierte Schleifenkonfiguration um.

```
Du:    Ich will unsere API schneller machen, weiss aber nicht, wo ich anfangen soll

Codex: Ich habe das Repository analysiert. Die API-Schicht liegt in src/api/ mit Express + Prisma.

       Zu bestaetigen:
       - Was ist wichtiger: p95-Latenz, Durchsatz oder Kaltstart?
       - Die gesamte API testen oder bestimmte Endpunkte?

       Antworten Sie mit Ihrer Prioritaet.

Du:    p95-Latenz, der /search-Endpunkt ist am langsamsten.
```

### debug

Beweisbasierte Fehlersuche. Jede Iteration testet eine falsifizierbare Hypothese.

```
Du:    Unsere API liefert unter Last zufaellig 503-Fehler, keine Ahnung warum

Codex: Ich sehe Connection-Pooling in src/db/pool.ts, Rate-Limiting in src/middleware/
       und 3 asynchrone Handler ohne Fehlerbehandlung.

       Bestaetigt:
       - Symptom: intermittierende 503-Fehler unter gleichzeitiger Last
       - Bereich: src/api/, src/db/, src/middleware/

       Zu bestaetigen:
       - Wann hat das angefangen? Nach einer bestimmten Aenderung, oder schon immer?
       - Wenn ich die Ursache finde, soll ich sie auch beheben?

       Antworten Sie mit dem Kontext.

Du:    Seit der Connection-Pool-Refaktorierung letzte Woche. Erst die Ursache finden.
```

### fix

Repariert Fehler iterativ, bis der Zaehler null erreicht.

```
Du:    pytest schlaegt fehl, 12 Tests kaputt nach der Refaktorierung

Codex: Ich sehe 12 Fehlschlaege in tests/.

       Bestaetigt:
       - Ziel: alle pytest-Tests bestehen lassen
       - Aktuell: 12 Fehlschlaege

       Zu bestaetigen:
       - Soll ich auch ruff als Schutz gegen Lint-Probleme verwenden?
       - Alles reparieren oder zuerst auf ein bestimmtes Modul konzentrieren?

       Antworten Sie "go" zum Starten.

Du:    Alles reparieren, ja mit ruff als Schutz. Go.
```

### security

Reines Lese-Audit nach STRIDE + OWASP + Red-Team. Jeder Befund erfordert Code-Beweise.

```
Du:    Unsere API auf Injection-Schwachstellen pruefen

Codex: Bestaetigt:
       - Bereich: src/api/ und src/middleware/ (14 Dateien)
       - Fokus: SQL-Injection, XSS, Eingabevalidierung

       Zu bestaetigen:
       - Nur Bericht, oder auch kritische Befunde beheben?
       - Soll ich auch Authentifizierung/Zugriffskontrolle abdecken?

       Antworten Sie mit Ihrer Praeferenz.

Du:    Erst den Bericht, und ja, Authentifizierung auch abdecken.
```

### ship

Kontrollierte Release-Verifikation. Erkennt automatisch, was Sie veroeffentlichen (PR, Deployment, Release).

```
Du:    Ab in die Produktion

Codex: Erkannt: PR nach main mit 3 Commits.

       Bestaetigt:
       - Typ: Code-PR
       - Ziel: main-Branch

       Zu bestaetigen:
       - Erst Probelauf, oder direkt live?
       - Ueberwachung nach Veroeffentlichung? (5 Min / 15 Min / keine)

       Antworten Sie mit Ihrer Praeferenz.

Du:    Erst Probelauf.
```

Siehe [GUIDE.md](../GUIDE.md) fuer detaillierte Nutzung und erweiterte Optionen jedes Modus.

---

## Verkettung von Modi

Modi koennen sequenziell kombiniert werden:

```
plan  -->  loop              # Konfiguration erarbeiten, dann ausfuehren
debug -->  fix               # Bugs finden, dann reparieren
security + fix               # Audit und Behebung in einem Durchgang
```

---

## Laufuebergreifendes Lernen

Jeder Lauf extrahiert strukturierte Erkenntnisse -- was funktioniert hat, was fehlgeschlagen ist und warum. Erkenntnisse werden in `autoresearch-lessons.md` gespeichert (nicht committet, wie das Ergebnisprotokoll) und zu Beginn zukuenftiger Laeufe herangezogen, um die Hypothesengenerierung in Richtung bewaehrter Strategien und weg von bekannten Sackgassen zu lenken.

- Positive Erkenntnisse nach jeder beibehaltenen Iteration
- Strategische Erkenntnisse nach jeder PIVOT-Entscheidung
- Zusammenfassende Erkenntnisse beim Abschluss eines Laufs
- Kapazitaet: maximal 50 Eintraege, aeltere Eintraege werden mit zeitlichem Verfall zusammengefasst

Siehe `references/lessons-protocol.md` fuer Details.

---

## Intelligente Feststeck-Erholung

Anstatt nach Fehlschlaegen blind erneut zu versuchen, verwendet die Schleife ein abgestuftes Eskalationssystem:

| Ausloeser | Aktion |
|-----------|--------|
| 3 aufeinanderfolgende Verwerfungen | **REFINE** -- Anpassung innerhalb der aktuellen Strategie |
| 5 aufeinanderfolgende Verwerfungen | **PIVOT** -- Strategie aufgeben, grundlegend anderen Ansatz versuchen |
| 2 PIVOTs ohne Verbesserung | **Websuche** -- nach externen Loesungen suchen |
| 3 PIVOTs ohne Verbesserung | **Weiche Blockade** -- warnen und mit mutigeren Aenderungen fortfahren |

Ein einzelnes erfolgreiches Behalten setzt alle Zaehler zurueck. Siehe `references/pivot-protocol.md`.

---

## Parallele Experimente

Testen Sie mehrere Hypothesen gleichzeitig mit Subagent-Workern in isolierten git-Worktrees:

```
Orchestrator (Haupt-Agent)
  +-- Worker A (worktree-a) -> Hypothese 1
  +-- Worker B (worktree-b) -> Hypothese 2
  +-- Worker C (worktree-c) -> Hypothese 3
```

Der Orchestrator waehlt das beste Ergebnis aus, fuehrt es zusammen und verwirft den Rest. Aktivieren Sie parallele Experimente waehrend des Assistenten, indem Sie "ja" sagen. Faellt auf seriell zurueck, wenn Worktrees nicht unterstuetzt werden.

Siehe `references/parallel-experiments-protocol.md`.

---

## Sitzungswiederaufnahme

Wenn Codex einen zuvor unterbrochenen Lauf erkennt (Ergebnisprotokoll, Erkenntnisdatei, Experiment-Commits), kann er vom letzten konsistenten Zustand fortfahren, anstatt von vorne zu beginnen:

- **Konsistenter Zustand:** sofortige Wiederaufnahme, Assistent wird uebersprungen
- **Teilweise konsistent:** Mini-Assistent (1 Runde) zur erneuten Bestaetigung
- **Inkonsistent oder anderes Ziel:** Neustart (altes Protokoll wird umbenannt)

Siehe `references/session-resume-protocol.md`.

---

## CI/CD-Modus (exec)

Nicht-interaktiver Modus fuer Automatisierungspipelines. Die gesamte Konfiguration wird im Voraus bereitgestellt -- kein Assistent, immer begrenzt, JSON-Ausgabe.

```yaml
# GitHub Actions Beispiel
- name: Autoresearch-Optimierung
  run: codex exec --skill codex-autoresearch
         --goal "Reduce type errors" --scope "src/**/*.ts"
         --metric "type error count" --direction lower
         --verify "tsc --noEmit 2>&1 | grep -c error"
         --iterations 20
```

Exit-Codes: 0 = verbessert, 1 = keine Verbesserung, 2 = harte Blockade.

Siehe `references/exec-workflow.md`.

---

## Ergebnisprotokoll

Jede Iteration wird im TSV-Format aufgezeichnet (`research-results.tsv`):

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module with strict types
2          -        49      +8      discard   generic wrapper introduced new anys
3          c3d4e5f  38      -3      keep      type-narrow API response handlers
```

Alle 5 Iterationen wird eine Fortschrittszusammenfassung ausgegeben. Begrenzte Laeufe geben eine abschliessende Zusammenfassung vom Ausgangswert zum besten Ergebnis aus.

---

## Sicherheitsmodell

| Bedenken | Behandlung |
|----------|------------|
| Unsauberer Arbeitsbaum | Die Schleife verweigert den Start; schlaegt den Modus `plan` oder einen sauberen Branch vor |
| Fehlgeschlagene Aenderung | `git reset --hard HEAD~1` haelt die Historie sauber; das Ergebnisprotokoll ist der Audit-Trail |
| Guard-Fehlschlag | Bis zu 2 Ueberarbeitungsversuche, dann Zuruecksetzen |
| Syntaxfehler | Sofortige automatische Korrektur, zaehlt nicht als Iteration |
| Laufzeit-Absturz | Bis zu 3 Reparaturversuche, dann ueberspringen |
| Ressourcenerschoepfung | Zuruecksetzen, kleinere Variante versuchen |
| Haengender Prozess | Nach Timeout beenden, zuruecksetzen |
| Festgefahren (3+ Verwerfungen) | REFINE-Strategie; 5+ Verwerfungen -> PIVOT zu neuem Ansatz; bei Bedarf Eskalation zur Websuche |
| Unsicherheit waehrend der Schleife | Best Practices autonom anwenden; niemals unterbrechen, um den Benutzer zu fragen |
| Externe Seiteneffekte | Der Modus `ship` erfordert explizite Bestaetigung waehrend des Pre-Launch-Assistenten |
| Umgebungslimits | Werden beim Start ermittelt; undurchfuehrbare Hypothesen werden automatisch gefiltert |
| Unterbrochene Sitzung | Wiederaufnahme vom letzten konsistenten Zustand bei naechstem Aufruf |

---

## Projektstruktur

```
codex-autoresearch/
  SKILL.md                          # Skill-Einstiegspunkt (von Codex geladen)
  README.md                         # englische Dokumentation
  CONTRIBUTING.md                   # Beitragsrichtlinien
  LICENSE                           # MIT
  agents/
    openai.yaml                     # Codex-UI-Metadaten
  image/
    banner.png                      # Projekt-Banner
  docs/
    INSTALL.md                      # Installationsanleitung
    GUIDE.md                        # Bedienungsanleitung
    EXAMPLES.md                     # Rezepte nach Bereich
    i18n/
      README_ZH.md                  # Chinesisch
      README_JA.md                  # Japanisch
      README_KO.md                  # Koreanisch
      README_FR.md                  # Franzoesisch
      README_DE.md                  # diese Datei
      README_ES.md                  # Spanisch
      README_PT.md                  # Portugiesisch
      README_RU.md                  # Russisch
  scripts/
    validate_skill_structure.sh     # Strukturvalidierungsskript
  references/
    core-principles.md              # universelle Prinzipien
    autonomous-loop-protocol.md     # Schleifen-Protokollspezifikation
    plan-workflow.md                # Spezifikation Modus plan
    debug-workflow.md               # Spezifikation Modus debug
    fix-workflow.md                 # Spezifikation Modus fix
    security-workflow.md            # Spezifikation Modus security
    ship-workflow.md                # Spezifikation Modus ship
    exec-workflow.md                # Spezifikation CI/CD nicht-interaktiver Modus
    interaction-wizard.md           # Vertrag fuer interaktive Einrichtung
    structured-output-spec.md       # Ausgabeformatspezifikation
    modes.md                        # Modus-Index
    results-logging.md              # TSV-Formatspezifikation
    lessons-protocol.md             # laufuebergreifendes Lernen
    pivot-protocol.md               # intelligente Feststeck-Erholung (PIVOT/REFINE)
    web-search-protocol.md          # Websuche bei Blockade
    environment-awareness.md        # Hardware-/Ressourcenerkennung
    parallel-experiments-protocol.md # Subagent-Paralleltests
    session-resume-protocol.md      # unterbrochene Laeufe fortsetzen
    health-check-protocol.md        # Selbstueberwachung
    hypothesis-perspectives.md      # Hypothesenbetrachtung aus mehreren Perspektiven
```

---

## FAQ

**Wie waehle ich eine Metrik?** Verwenden Sie `Mode: plan`. Er analysiert Ihre Codebasis und schlaegt eine vor.

**Funktioniert mit jeder Sprache?** Ja. Das Protokoll ist sprachunabhaengig. Nur der Verify-Befehl ist domaenenspezifisch.

**Wie stoppe ich es?** Unterbrechen Sie Codex, oder setzen Sie `Iterations: N`. Der git-Zustand ist immer konsistent, da Commits vor der Verifikation stattfinden.

**Aendert der security-Modus meinen Code?** Nein. Reine Leseanalyse. Sagen Sie Codex waehrend der Einrichtung "auch kritische Befunde beheben", um die Behebung zu aktivieren.

**Wie viele Iterationen?** Haengt von der Aufgabe ab. 5 fuer gezielte Korrekturen, 10-20 fuer Exploration, unbegrenzt fuer Nachtlaeufe.

**Lernt es ueber Laeufe hinweg?** Ja. Nach jedem Lauf werden Erkenntnisse extrahiert und zu Beginn des naechsten Laufs herangezogen. Die Erkenntnisdatei bleibt ueber Sitzungen hinweg erhalten.

**Kann es nach einer Unterbrechung fortfahren?** Ja. Beim naechsten Aufruf erkennt es den vorherigen Lauf und setzt vom letzten konsistenten Zustand fort.

**Kann es im Web suchen?** Ja, wenn es nach mehreren Strategiewechseln feststeckt. Websuche-Ergebnisse werden als Hypothesen behandelt und mechanisch verifiziert.

**Wie verwende ich es in CI?** Verwenden Sie `Mode: exec` oder `codex exec`. Die gesamte Konfiguration wird im Voraus bereitgestellt, die Ausgabe ist JSON und Exit-Codes zeigen Erfolg/Misserfolg an.

**Kann es mehrere Ideen gleichzeitig testen?** Ja. Aktivieren Sie parallele Experimente waehrend der Einrichtung. Es verwendet git-Worktrees, um bis zu 3 Hypothesen gleichzeitig zu testen.

---

## Danksagung

Dieses Projekt basiert auf Ideen von [Karpathys autoresearch](https://github.com/karpathy/autoresearch). Die Codex-Skills-Plattform wird von [OpenAI](https://openai.com) bereitgestellt.

---

## Star History

<a href="https://www.star-history.com/?repos=leo-lilinxiao%2Fcodex-autoresearch&type=timeline&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
 </picture>
</a>

---

## Lizenz

MIT -- siehe [LICENSE](../../LICENSE).
