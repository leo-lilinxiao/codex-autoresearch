<p align="center">
  <img src="../../image/banner.png" width="700" alt="Codex Autoresearch">
</p>

<h2 align="center"><b>Zielen. Iterieren. Ankommen.</b></h2>

<p align="center">
  <i>Autonomes, zielgesteuertes Experimentieren für Codex.</i>
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

---

Die Idee: Sagen Sie Codex, was Sie verbessern möchten, und gehen Sie. Er ändert Ihren Code, überprüft das Ergebnis, behält oder verwirft, und wiederholt. Sie kommen zurück zu einem Experimentprotokoll und einer besseren Codebasis.

Inspiriert von [Karpathys autoresearch](https://github.com/karpathy/autoresearch), verallgemeinert über ML hinaus auf alles, was sich mechanisch verifizieren lässt: Testabdeckung, Typfehler, Latenz, Lint-Warnungen, Sicherheitsbefunde, Release-Bereitschaft — wenn ein Befehl feststellen kann, ob es besser wurde, kann die Schleife darauf iterieren.

## Schnellstart

```text
# In Codex installieren (empfohlen)
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

Starten Sie Codex neu, öffnen Sie Ihr Projekt und legen Sie los:

```
Du:    $codex-autoresearch
       Ich will alle `any`-Typen in meinem TypeScript-Code loswerden

Codex: Ich habe 47 `any`-Vorkommen in src/**/*.ts gefunden.
       Results-Verzeichnis: ./autoresearch-results/
       Metrik: `any`-Anzahl (aktuell: 47), Richtung: niedriger
       Verifikation: grep-Zählung + tsc --noEmit als guard
       Ausführungsmodus: foreground oder background?

Du:    Background, go. Lass es über Nacht laufen.

Codex: Starte Hintergrundlauf — Baseline: 47. Iteriere.
```

Jede Verbesserung baut auf. Jeder Fehlschlag wird zurückgesetzt. Alles wird protokolliert.

Manuelle Kopier-, Symlink- und User-Scope-Optionen stehen in [INSTALL.md](../INSTALL.md). Vollständiges Handbuch in [GUIDE.md](../GUIDE.md).

## So funktioniert es

```
Du sagst einen Satz  →  Codex scannt & bestätigt  →  Du sagst "go"
                                                         |
                                          +--------------+--------------+
                                          |                             |
                                     foreground                    background
                                   (aktuelle Sitzung)          (abgekoppelt, über Nacht)
                                          |                             |
                                          +--------------+--------------+
                                                         |
                                                         v
                                               +-------------------+
                                               |   Die Schleife    |
                                               |                   |
                                               |  eine Sache ändern|
                                               |  git commit       |
                                               |  verify ausführen |
                                               |  besser? behalten |
                                               |  schlechter? rev. |
                                               |  Ergebnis loggen  |
                                               |  wiederholen      |
                                               +-------------------+
```

Das war's. Sie wählen eines von beiden: Foreground behält die Schleife in Ihrer aktuellen Sitzung, Background übergibt sie an einen abgekoppelten Prozess, damit Sie schlafen können. Dieselbe Schleife, aber sie laufen nicht gleichzeitig.

## Was Sie sagen vs was passiert

| Was Sie sagen | Was passiert |
|---------------|-------------|
| „Verbessere meine Testabdeckung" | Iteriert bis zum Ziel oder Unterbrechung |
| „Behebe die 12 fehlschlagenden Tests" | Repariert einen nach dem anderen bis null übrig |
| „Warum gibt die API 503 zurück?" | Sucht die Ursache mit falsifizierbaren Hypothesen |
| „Ist dieser Code sicher?" | STRIDE + OWASP-Audit, jeder Befund mit Code-Beleg |
| „Ausliefern" | Prüft Bereitschaft, erstellt Checkliste, kontrolliert Release |
| „Ich will optimieren, weiß aber nicht was" | Analysiert das Repo, schlägt Metriken vor, generiert Konfiguration |

Im Hintergrund ordnet Codex Ihren Satz einem von 7 Modi zu (loop, plan, debug, fix, security, ship, exec). Sie müssen nie einen auswählen.

## Was Codex automatisch ermittelt

Sie schreiben keine Konfiguration. Codex leitet alles aus Ihrem Satz und Ihrem Repo ab:

| Was benötigt wird | Wie es ermittelt wird | Beispiel |
|-------------------|----------------------|----------|
| Ziel | Ihr Satz | „alle any-Typen loswerden" |
| Umfang | Scannt die Repo-Struktur | `src/**/*.ts` |
| Metrik | Schlägt basierend auf Ziel + Tooling vor | any-Anzahl (aktuell: 47) |
| Richtung | Leitet ab aus „verbessern" / „reduzieren" / „eliminieren" | niedriger |
| Verifikation | Ordnet dem Repo-Tooling zu | `grep`-Zählung + `tsc --noEmit` |
| Guard | Schlägt vor, wenn Regressionsrisiko besteht | `npm test` |

Vor dem Start zeigt Codex immer, was er gefunden hat, und bittet um Bestätigung. Dann wählen Sie foreground oder background und sagen „go".
Standardmäßig bleibt das Results-Verzeichnis im Startkontext: Wenn Sie Codex in einem Git-Repo gestartet haben, ist dessen Repo-Root der Standard-Workspace-Root; wenn Sie Codex außerhalb eines Git-Repos gestartet haben, ist das aktuelle Startverzeichnis der Standard-Workspace-Root. Codex sollte dies nicht stillschweigend auf ein übergeordnetes Verzeichnis ausweiten, es sei denn, Sie bestätigen ausdrücklich einen größeren Multi-Repo-Workspace. Die Bestätigungsübersicht sollte vor dem Start immer das gewählte Results-Verzeichnis anzeigen.

## Wenn es hakt

Statt blind zu wiederholen, eskaliert die Schleife:

| Auslöser | Aktion |
|----------|--------|
| 3 aufeinanderfolgende Fehlschläge | **REFINE** — innerhalb der aktuellen Strategie anpassen |
| 5 aufeinanderfolgende Fehlschläge | **PIVOT** — einen grundlegend anderen Ansatz versuchen |
| 2 PIVOTs ohne Fortschritt | **Websuche** — nach externen Lösungen suchen |
| 3 PIVOTs ohne Fortschritt | **Stopp** — meldet, dass menschliches Eingreifen nötig ist |

Ein einziger Erfolg setzt alle Zähler zurück.

## Ergebnisprotokoll

Jede Iteration wird in `autoresearch-results/results.tsv` aufgezeichnet:

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module
2          -        49      +8      discard   generic wrapper introduced new anys
3          d4e5f6g  38      -3      keep      type-narrow API response handlers
```

Fehlgeschlagene Experimente werden in git zurückgesetzt, bleiben aber im Protokoll. Das Protokoll ist die eigentliche Audit-Spur, während `autoresearch-results/state.json` der Resume-Snapshot ist.

## Weitere Funktionen

Details in [GUIDE.md](../GUIDE.md):

- **Laufübergreifendes Lernen** — Erkenntnisse aus vergangenen Läufen beeinflussen die zukünftige Hypothesengenerierung
- **Parallele Experimente** — bis zu 3 Hypothesen gleichzeitig über git worktrees testen
- **Sitzungswiederaufnahme** — unterbrochene Läufe setzen beim letzten konsistenten Zustand fort
- **CI/CD-Modus** (`exec`) — nicht-interaktiv, JSON-Ausgabe, für Automatisierungspipelines
- **Doppelte Prüfung** — getrenntes verify (hat es sich verbessert?) und guard (ist etwas kaputtgegangen?)
- **Session hooks** — automatisch installiert; halten Codex über Sitzungsgrenzen hinweg auf Kurs

## FAQ

**Es macht nur kleine Änderungen. Kann es größere Ideen ausprobieren?**
Standardmäßig bevorzugt die Schleife kleine, überprüfbare Schritte — das ist beabsichtigt. Aber sie kann auch größer denken: Beschreiben Sie eine umfangreichere Hypothese in Ihrem Prompt (z.B. „ersetze den Attention-Mechanismus durch Linear Attention und führe die vollständige Evaluation durch"), und sie wird das als ein einzelnes Experiment verifizieren. Am besten funktioniert es, wenn der Mensch die Forschungsrichtung vorgibt und der Agent die intensive Ausführung und Analyse übernimmt.

**Ist das eher für Engineering-Optimierung oder für Forschung?**
Am stärksten ist es, wenn Ziel und Metrik klar sind — Abdeckung erhöhen, Fehler reduzieren, Latenz senken. Wenn die Forschungsrichtung selbst noch unklar ist, nutzen Sie zuerst den `plan`-Modus zum Erkunden, dann wechseln Sie zu `loop`, sobald Sie wissen, was Sie messen wollen. Betrachten Sie es als Mensch-KI-Zusammenarbeit: Sie liefern das Urteil, der Agent liefert die Iterationsgeschwindigkeit.

**Wie stoppe ich es?** Foreground: Codex unterbrechen. Background: `$codex-autoresearch` und dann Stopp anfordern.

**Kann es nach einer Unterbrechung fortsetzen?** Ja. Es setzt automatisch von `autoresearch-results/state.json` fort.

**Wie nutze ich es in CI?** `Mode: exec` mit `codex exec`. Gesamte Konfiguration vorab, JSON-Ausgabe, Exit-Codes 0/1/2.

## Dokumentation

| Dok | Inhalt |
|-----|--------|
| [INSTALL.md](../INSTALL.md) | Alle Installationsmethoden, Skill-Erkennungspfade, Hooks-Einrichtung |
| [GUIDE.md](../GUIDE.md) | Vollständiges Handbuch: Modi, Konfigurationsfelder, Sicherheitsmodell, erweiterte Nutzung |
| [EXAMPLES.md](../EXAMPLES.md) | Rezepte nach Domäne: Abdeckung, Performance, Typen, Sicherheit usw. |

## Danksagungen

Aufgebaut auf Ideen von [Karpathys autoresearch](https://github.com/karpathy/autoresearch). Die Codex-Skills-Plattform stammt von [OpenAI](https://openai.com).

## Star History

<a href="https://www.star-history.com/?repos=leo-lilinxiao%2Fcodex-autoresearch&type=timeline&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
 </picture>
</a>

## Lizenz

MIT — siehe [LICENSE](../../LICENSE).
