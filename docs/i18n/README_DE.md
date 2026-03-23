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
  <a href="#so-funktionierts">So funktionierts</a> ·
  <a href="#was-codex-automatisch-erkennt">Was Codex automatisch erkennt</a> ·
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
              | Umgebungserkennung  |  <-- Phase 0: CPU/GPU/RAM/Toolchains erkennen
              +---------+-----------+
                        |
              +---------v-----------+
              | Sitzung fortsetzen? |  <-- auf fruehere Laufartefakte pruefen
              +---------+-----------+
                        |
              +---------v-----------+
              |   Kontext lesen     |  <-- Scope + Erkenntnisdatei lesen
              +---------+-----------+
                        |
              +---------v-----------+
              |Ausgangswert festlegen| <-- iteration #0
              +---------+-----------+
                        |
         +--------------v--------------+
         |                             |
         |  +----------------------+   |
         |  | Hypothese waehlen    |   |  <-- Erkenntnisse + Perspektiven heranziehen
         |  | (oder N parallel)    |   |      nach Umgebung filtern
         |  +---------+------------+   |
         |            |                |
         |  +---------v------------+   |
         |  |EINE Aenderung vornehmen| |
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
         |        verbessert?          |
         |       /         \           |
         |     yes          no         |
         |     /              \        |
         |  +-v------+   +----v-----+ |
         |  |  KEEP  |   | REVERT   | |
         |  |+lesson |   +----+-----+ |
         |  +--+-----+        |       |
         |      \            /         |
         |   +--v----------v---+      |
         |   |Ergebnis protokollieren| |
         |   +--------+--------+      |
         |            |               |
         |   +--------v--------+      |
         |   |  Health Check   |      |  <-- Speicher, git, Verifikationsgesundheit
         |   +--------+--------+      |
         |            |               |
         |     3+ Verwerfungen?       |
         |    /             \         |
         |  no              yes       |
         |  |          +----v-----+   |
         |  |          | REFINE / |   |  <-- Pivot-Protokoll-Eskalation
         |  |          | PIVOT    |   |
         |  |          +----+-----+   |
         |  |               |         |
         +--+------+--------+         |
         |         (wiederholen)      |
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

## So funktionierts

Sie sagen in einem Satz, was Sie wollen. Codex erledigt den Rest.

Es scannt Ihr Repository, schlaegt einen Plan vor, bestaetigt mit Ihnen, dann iteriert es autonom:

| Sie sagen | Was passiert |
|-----------|------------|
| "Testabdeckung erhoehen" | Scannt das Repo, schlaegt eine Metrik vor, iteriert bis zum Ziel oder Unterbrechung |
| "Die 12 fehlschlagenden Tests reparieren" | Erkennt Fehlschlaege, repariert einzeln bis null uebrig sind |
| "Warum gibt die API 503 zurueck?" | Sucht die Ursache mit falsifizierbaren Hypothesen und Beweisen |
| "Ist dieser Code sicher?" | Fuehrt ein STRIDE + OWASP-Audit durch, jeder Befund mit Code-Beleg |
| "Ab in die Produktion" | Prueft Bereitschaft, erstellt Checkliste, kontrollierte Freigabe |
| "Ich will optimieren, weiss aber nicht, was ich messen soll" | Analysiert das Repo, schlaegt Metriken vor, generiert einsatzbereite Konfiguration |

Im Hintergrund ordnet Codex Ihren Satz einem der 7 spezialisierten Modi zu
(loop, plan, debug, fix, security, ship, exec). Sie muessen nie einen Modus
waehlen -- beschreiben Sie einfach Ihr Ziel.

---

## Was Codex automatisch erkennt

Codex leitet alles aus Ihrem Satz und Ihrem Repository ab. Sie schreiben keine Konfiguration.

| Was benoetigt wird | Wie es ermittelt wird | Beispiel |
|-------------------|----------------------|---------|
| Ziel | Ihr Satz | "alle any-Typen eliminieren" |
| Scope | Scannt die Repository-Struktur | entdeckt automatisch src/**/*.ts |
| Metrik | Schlaegt basierend auf Ziel + Tooling vor | any-Anzahl (aktuell: 47) |
| Richtung | Leitet ab aus "verbessern" / "reduzieren" / "eliminieren" | senken |
| Verify-Befehl | Passt zum Repository-Tooling | grep-Zaehlung + tsc --noEmit |
| Guard (optional) | Schlaegt vor, wenn Regressionsrisiko besteht | npm test |

Vor dem Start zeigt Codex Ihnen immer, was es gefunden hat, und bittet um Bestaetigung.
Mindestens eine Runde Bestaetigung, bis zu fuenf bei Bedarf. Danach waehlen Sie `foreground` oder `background` und sagen "go". In `foreground` laeuft die Iteration in der aktuellen Sitzung weiter; in `background` wird sie an den losgeloesten Runtime-Controller uebergeben, sodass Sie sich zuruecklehnen koennen.
Fuer wirklich unbeaufsichtigte Laeufe sollten Sie Codex CLI mit Freigabe-/Sandbox-Einstellungen starten, die `git commit` oder `git revert` nicht unterbrechen. In einem wegwerfbaren oder anderweitig vertrauenswuerdigen Repository ist es am einfachsten, Codex weitergehende Berechtigungen zu geben.

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
       - Laufmodus: foreground oder background?
       - Bis auf null laufen lassen, oder auf N Iterationen begrenzen?

       Waehlen Sie zuerst einen Laufmodus und antworten Sie dann mit "go".

Du:    Background, go. Die ganze Nacht.

Codex: Starte den background-Lauf. Zuerst die Ausgangsbasis, dann die losgeloesten Iterationen.
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
       - Laufmodus: foreground oder background?
       - Soll ich auch ruff als Schutz gegen Lint-Probleme verwenden?
       - Alles reparieren oder zuerst auf ein bestimmtes Modul konzentrieren?

       Waehlen Sie zuerst einen Laufmodus und antworten Sie dann mit "go".

Du:    Foreground, go. Alles reparieren, ja mit ruff als Schutz.
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

Jeder iterative Lauf ausser `exec` extrahiert strukturierte Erkenntnisse -- was funktioniert hat, was fehlgeschlagen ist und warum. Erkenntnisse werden in `autoresearch-lessons.md` gespeichert (nicht committet, wie das Ergebnisprotokoll) und zu Beginn zukuenftiger Laeufe herangezogen, um die Hypothesengenerierung in Richtung bewaehrter Strategien und weg von bekannten Sackgassen zu lenken. Der Modus `exec` kann vorhandene Erkenntnisse lesen, erstellt oder aktualisiert sie aber nicht.

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

Wenn Codex in einem interaktiven Modus einen zuvor unterbrochenen Lauf erkennt, kann es vom letzten konsistenten Zustand fortfahren, anstatt von vorne zu beginnen. Die primaere Wiederherstellungsquelle ist `autoresearch-state.json`, ein kompakter Zustandssnapshot, der bei jeder Iteration atomar aktualisiert wird. Im Modus `exec` liegt der Zustand nur in einer temporaeren Datei unter `/tmp/codex-autoresearch-exec/...` und muss vom `exec`-Workflow vor dem Beenden explizit entfernt werden. `foreground` setzt direkt mit `research-results.tsv` und `autoresearch-state.json` fort; `background` braucht fuer die direkte Wiederaufnahme weiterhin ein vorhandenes `autoresearch-launch.json`.

Wiederherstellungsprioritaet fuer interaktive Modi:

1. **JSON + TSV konsistent, Launch-Manifest vorhanden:** sofortige Wiederaufnahme, Assistent uebersprungen
2. **JSON gueltig, TSV inkonsistent:** Mini-Assistent (1 Runde Bestaetigung)
3. **JSON fehlt oder ist beschaedigt, TSV vorhanden:** Der Helper rekonstruiert den beibehaltenen Zustand zur Bestaetigung und faehrt dann mit einem neuen Launch-Manifest fort
4. **Keines vorhanden:** Neustart (vorherige persistente Run-Control-Artefakte werden archiviert)

Siehe `references/session-resume-protocol.md`.

---

## CI/CD-Modus (exec)

Nicht-interaktiver Modus fuer Automatisierungspipelines. Die gesamte Konfiguration wird im Voraus bereitgestellt -- kein Assistent, immer begrenzt, JSON-Ausgabe.

```yaml
# GitHub Actions Beispiel
- name: Autoresearch-Optimierung
  run: |
    codex exec --dangerously-bypass-approvals-and-sandbox <<'PROMPT'
    $codex-autoresearch
    Mode: exec
    Goal: Reduce type errors
    Scope: src/**/*.ts
    Metric: type error count
    Direction: lower
    Verify: tsc --noEmit 2>&1 | grep -c error
    Iterations: 20
    PROMPT
```

Exit-Codes: 0 = verbessert, 1 = keine Verbesserung, 2 = harte Blockade.

Bevor Sie `codex exec` in CI verwenden, konfigurieren Sie die Codex-CLI-Authentifizierung im Voraus. In kontrollierten Automatisierungsumgebungen sollten Sie `codex exec --dangerously-bypass-approvals-and-sandbox ...` bevorzugen, damit eigenstaendige `exec`-Laeufe dieselbe Standardrichtlinie `danger_full_access` wie die Managed Runtime verwenden. Fuer programmatische Laeufe ist API-Key-Authentifizierung die bevorzugte Option.

Wenn `Mode: exec` ueber die mit der Skill gebuendelten Helper-Skripte laeuft, benennen Sie alte Artefakte im Repo-Root nicht manuell um. `autoresearch_init_run.py --mode exec ...` archiviert die Standarddateien `research-results.tsv` und `autoresearch-state.json` selbststaendig als `research-results.prev.tsv` bzw. `autoresearch-state.prev.json`, bevor der neue Lauf initialisiert wird.

Siehe `references/exec-workflow.md`.

---

## Ergebnisprotokoll

Jede Iteration wird in zwei komplementaeren Formaten aufgezeichnet:

- **`research-results.tsv`** -- vollstaendiger Audit-Trail, mit einer Hauptzeile pro Iteration und optionalen parallelen Worker-Zeilen
- **`autoresearch-state.json`** -- kompakter Zustandssnapshot fuer schnelle Sitzungswiederaufnahme in interaktiven Modi

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module with strict types
2          -        49      +8      discard   generic wrapper introduced new anys
3          c3d4e5f  38      -3      keep      type-narrow API response handlers
```

Im Modus `exec` existiert der Zustandssnapshot nur unter `/tmp/codex-autoresearch-exec/...` und muss vom `exec`-Workflow vor dem Beenden explizit bereinigt werden. Aktualisieren Sie diese Artefakte ueber die gebuendelten Helper-Skripte unter `<skill-root>/scripts/...`, nicht ueber das `scripts/`-Verzeichnis des Ziel-Repos.

Beide Dateien werden nicht in git committed. Bei der Sitzungswiederaufnahme wird der JSON-Zustand gegen eine rekonstruierte TSV-Hauptiterationszusammenfassung kreuzvalidiert und nicht gegen die rohe Zeilenanzahl. Fortschrittsberichte werden alle 5 Iterationen ausgegeben. Begrenzte Laeufe geben am Ende eine Zusammenfassung von Baseline bis Bestwert aus.

Diese Zustandsartefakte werden zwar von den mit dem Skill gebuendelten Helper-Skripten unter `<skill-root>/scripts/...` verwaltet, aber die meisten Nutzer sollten beim einzigen menschlichen Einstiegspunkt bleiben: **`$codex-autoresearch`**. Hier bezeichnet `<skill-root>` das Verzeichnis mit der geladenen `SKILL.md`; bei der ueblichen repo-lokalen Installation ist das `.agents/skills/codex-autoresearch`.

Wenn Sie die Control-Plane skripten oder debuggen, verwenden repo-zentrierte Helper standardmaessig `--repo <repo>`. Bevorzugen Sie dann:

- `python3 <skill-root>/scripts/autoresearch_resume_check.py --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_launch_gate.py --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo <repo>`

`--results-path`, `--state-path`, `--launch-path` und `--runtime-path` bleiben als erweiterte Overrides verfuegbar. Dieselbe repo-first-Konvention gilt auch fuer direkte Aufrufe von `autoresearch_resume_prompt.py` und `autoresearch_supervisor_status.py`.

Fuer Menschen gibt es jetzt nur noch einen einzigen Haupteinstieg: **`$codex-autoresearch`**.

- Beim ersten interaktiven Lauf beschreiben Sie das Ziel natuerlich, beantworten die Rueckfragen, waehlen ausdruecklich `foreground` oder `background` und antworten dann mit `go`
- In `foreground` bleibt Codex in derselben Sitzung, iteriert live weiter und schreibt nur `research-results.tsv`, `autoresearch-state.json` und Lessons
- In `background` schreibt Codex automatisch `autoresearch-launch.json` und startet die entkoppelte Laufzeitsteuerung
- `foreground` und `background` teilen sich dasselbe Loop-Protokoll, dieselbe Metriksemantik und dieselben Repo-/Scope-Regeln, sind fuer denselben Repo-/Run-Kontext aber gegenseitig ausschliessend; lassen Sie nicht beide Modi gleichzeitig dieselben Primaer-Repo-Artefakte schreiben
- Wenn Sie denselben interaktiven Run spaeter im anderen Modus fortsetzen wollen, bleiben Sie beim selben `$codex-autoresearch`-Einstiegspunkt; vor dem Fortsetzen synchronisiert die Skill-Logik den gemeinsamen State intern auf den Zielmodus, und background `start` fuehrt denselben Schritt automatisch aus
- Einzelne Repositories bleiben der Standardfall; dann gilt der deklarierte Scope nur fuer das Primaer-Repository, das die Run-Control-Artefakte traegt
- Wenn das Experiment mehrere Repositories umfasst, kann das bestaetigte Launch-Manifest auch Companion-Repositories mit jeweils eigenem Scope enthalten. Die Runtime-Preflight-Pruefung deckt dann alle verwalteten Repositories ab, waehrend `research-results.tsv`, `autoresearch-state.json` und die Runtime-Control-Artefakte im Primaer-Repository verankert bleiben
- In diesem Modell bleibt die TSV-Spalte `commit` beim Commit des Primaer-Repositories; die Commit-Provenienz der Companion-Repositories steht stattdessen in `autoresearch-state.json`
- Jeder weitere verwaltete `background`-Laufzyklus startet eine nicht-interaktive `codex exec`-Sitzung und uebergibt den Runtime-Prompt ueber stdin
- `execution_policy` gilt nur fuer Pfade, die verschachtelte Codex-Sitzungen starten, also fuer `background` und `exec`; dieses Skill verwendet standardmaessig `danger_full_access`
- Spaetere Anfragen wie `status`, `stop` oder `resume` laufen weiterhin ueber dasselbe `$codex-autoresearch`; `status/stop` gelten nur fuer `background`
- `Mode: exec` bleibt der erweiterte Pfad fuer CI und voll spezifizierte Automatisierung

Direkte Steuerbefehle bleiben fuer Skripting oder das Debugging der Laufzeit verfuegbar:

- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo <repo>`


---

## Sicherheitsmodell

| Bedenken | Behandlung |
|----------|------------|
| Unsauberer Arbeitsbaum | Die Laufzeit-Vorpruefung blockiert Start oder Relaunch, bis Aenderungen ausserhalb des vorgesehenen Bereichs bereinigt oder isoliert sind |
| Fehlgeschlagene Aenderung | Verwendet die vor dem Start genehmigte Rollback-Strategie: `git reset --hard HEAD~1` nur in einem isolierten Experiment-Branch/Worktree mit Genehmigung, sonst `git revert --no-edit HEAD`; das Ergebnisprotokoll bleibt der Audit-Trail |
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
| Kontextdrift (Langzeitlaufe) | Protokoll-Fingerprint-Check alle 10 Iterationen; nach Kompaktierungen haeufiger pruefen; bei Fehlschlag vom Datentrager neu lesen |

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
    validate_skill_structure.sh     # structure validator
    autoresearch_helpers.py         # gemeinsame Hilfsskripte fuer TSV / JSON / Laufzeit
    autoresearch_launch_gate.py     # entscheidet vor dem Start zwischen fresh / resumable / needs_human
    autoresearch_resume_prompt.py   # baut den vom Laufzeit-Controller verwendeten Prompt aus der gespeicherten Konfiguration
    autoresearch_runtime_ctl.py     # steuert launch / create-launch / start / status / stop des Laufzeit-Controllers
    autoresearch_commit_gate.py     # git / artifact / rollback gate
    autoresearch_decision.py        # structured keep / discard / crash policy helpers
    autoresearch_health_check.py    # executable health checks
    autoresearch_lessons.py         # structured lessons append / list helpers
    autoresearch_init_run.py        # initialize baseline log + state
    autoresearch_record_iteration.py # append one main iteration + update state
    autoresearch_resume_check.py    # decide full_resume / mini_wizard / fallback
    autoresearch_select_parallel_batch.py # log worker rows + batch winner
    autoresearch_exec_state.py      # resolve / cleanup exec scratch state
    autoresearch_supervisor_status.py # decide relaunch / stop / needs_human
    check_skill_invariants.py       # validate real skill-run artifacts
    run_skill_e2e.sh                # disposable Codex CLI smoke harness
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

**Lernt es ueber Laeufe hinweg?** Ja. Erkenntnisse werden nach jedem `keep`, nach jedem `pivot` und beim Abschluss der Laufzeit ohne aktuelle Erkenntnis extrahiert. Die Erkenntnisdatei bleibt ueber Sitzungen hinweg erhalten; `exec` liest nur vorhandene Erkenntnisse.

**Kann es nach einer Unterbrechung fortfahren?** Ja. `foreground` setzt mit `research-results.tsv` und `autoresearch-state.json` fort; `background` benoetigt zusaetzlich `autoresearch-launch.json`. Fehlt der bestaetigte Startzustand, beginne einen neuen `background`-Lauf ueber den normalen Startfluss.

**Kann es im Web suchen?** Ja, wenn es nach mehreren Strategiewechseln feststeckt. Websuche-Ergebnisse werden als Hypothesen behandelt und mechanisch verifiziert.

**Wie verwende ich es in CI?** Verwenden Sie `Mode: exec` oder `codex exec`. In kontrollierten Automatisierungsumgebungen sollten Sie `codex exec --dangerously-bypass-approvals-and-sandbox ...` verwenden, damit die Berechtigungen der Standard-Runtime entsprechen. Die gesamte Konfiguration wird im Voraus bereitgestellt, die Ausgabe ist JSON und Exit-Codes zeigen Erfolg/Misserfolg an.

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
