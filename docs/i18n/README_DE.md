# Codex Autoresearch

[English](../../README.md) | **Deutsch**

Eine autonome, messbare Experimentierschleife für Codex.

Nenne Codex ein numerisches Ziel. Codex untersucht das Repository, bestätigt den Versuchsaufbau, ändert genau eine Sache, misst, behält Verbesserungen, macht Fehlschläge rückgängig und wiederholt dies bis zum Ziel.

Geeignet für fehlgeschlagene Tests, Coverage, Typfehler, Warnungen, Latenz, Binärgröße und reproduzierbare Sicherheitsbefunde.

## Schnellstart

In Codex installieren:

```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

Ein sauberes Git-Repository mit Full Access öffnen:

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

Dann aufrufen:

```text
$codex-autoresearch error_count aus `python3 scripts/score.py` auf 0 senken
```

Vor dem ersten Schreibzugriff bestätigt Codex Ziel, Bereich, Ausgangswert, Zielwert, Messbefehl, optionalen Guard und foreground/background.

Bereits getroffene Entscheidungen und erteilte Zustimmung gelten weiter. Nach dem Start laufen die Experimente ohne erneute Bestätigung jeder Iteration. Ein gestoppter Hintergrundlauf lässt sich mit „resume“ mit den bisherigen Einstellungen fortsetzen; eine neue Richtung ist optional.

## Schleife

```text
Evidenz prüfen -> eine Hypothese ändern -> Commit und Messung
                                             |
                                besser + Guard erfolgreich: behalten
                                sonst: git revert
                                             |
                                      protokollieren, wiederholen
```

Codex verantwortet Hypothesen und Codeänderungen. Das Kontrollskript verantwortet Git-Grenzen, Messung, Rollback und Zustand.

## Foreground und Background

| | Foreground | Background |
|---|---|---|
| Ausführung | Aktuelle Codex-Aufgabe | Separater Controller |
| Fortsetzung | Offizielles Codex Goal | Ein `codex exec` Worker pro Iteration |
| Geeignet für | Live beobachten und lenken | Lange oder nächtliche Läufe |
| Steuerung | Goal pausieren/fortsetzen | Status/stop/resume mit `$codex-autoresearch` |

Foreground wird durch das offizielle Goal fortgesetzt. Background erstellt kein Goal; der Controller setzt den Lauf fort. Die Installation ändert keine Codex-Einstellungen.

## Ergebnisse

Nicht eingecheckte Dateien liegen unter `autoresearch-results/`:

| Pfad | Zweck |
|---|---|
| `run.json` | Bestätigte, unveränderliche Konfiguration |
| `events.jsonl` | Nur angehängte Zustands- und Audit-Historie |
| `logs/` | Vollständige Mess-, Guard- und Worker-Ausgaben |
| `runtime.json` | Background-Prozesszustand |
| `runtime.log` | Controller-Lebenszyklus |

`events.jsonl` ist die einzige Zustandsquelle. Fehlende, beschädigte oder widersprüchliche Daten führen zu einem klaren Fehler und werden nicht erraten oder rekonstruiert.

## Verlauf und Bericht

```text
$codex-autoresearch show experiment history
$codex-autoresearch export experiment history as TSV
$codex-autoresearch generate an HTML report
```

Tabelle und HTML-Bericht werden aus validierten Ereignissen erzeugt. Der HTML-Schnappschuss liegt unter `autoresearch-results/report.html` und ist weder Laufzeitstatus noch Wiederherstellungsquelle.

## Garantien

- Neue Läufe benötigen einen sauberen, benannten Git-Branch.
- Ein Lauf verwaltet ein Repository, eine Metrik und einen Zielwert.
- Jedes Experiment wird committed; Fehlschläge werden mit `git revert` rückgängig gemacht.
- Änderungen außerhalb des Bereichs, Git-Drift, ungültige Metriken, Befehlsfehler, Timeouts und Rollback-Fehler stoppen mit Log-Pfad.
- `complete` wird nur gesetzt, wenn die behaltene Metrik den Zielwert erreicht.

## Voraussetzungen

- Aktuelle Codex CLI mit Skills und Goals
- Python 3.11+
- Git

Siehe [Installation](../INSTALL.md), [Benutzerhandbuch](../GUIDE.md) und [Beispiele](../EXAMPLES.md).

MIT-Lizenz. Inspiriert von [Karpathys autoresearch](https://github.com/karpathy/autoresearch).
