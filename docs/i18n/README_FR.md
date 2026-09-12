# Codex Autoresearch

[English](../../README.md) | **Français**

Une boucle d'expérimentation autonome et mesurable pour Codex.

Donnez un objectif numérique à Codex. Il inspecte le dépôt, confirme le protocole, modifie une chose, vérifie, conserve les améliorations, annule les échecs et recommence jusqu'à atteindre la cible.

Convient aux tests en échec, à la couverture, aux erreurs de type, aux avertissements, à la latence, à la taille des binaires et aux résultats de sécurité reproductibles.

## Démarrage rapide

Installez depuis Codex :

```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

Ouvrez de préférence un dépôt Git propre avec Full Access :

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

Puis lancez :

```text
$codex-autoresearch réduire error_count de `python3 scripts/score.py` à 0
```

Avant toute écriture, Codex confirme l'objectif, le périmètre, la mesure initiale, la cible, la commande, le guard facultatif et le mode foreground/background.

Codex conserve vos choix et autorisations déjà donnés. Une fois lancé, il poursuit les expériences sans demander de confirmation à chaque itération. Pour reprendre une exécution en arrière-plan arrêtée, demandez simplement « reprendre » ; une nouvelle direction est facultative.

## Boucle

```text
examiner -> modifier une hypothèse -> commit et mesure
                                      |
                         amélioration + guard OK : conserver
                         sinon : git revert
                                      |
                                journaliser, répéter
```

Codex choisit les hypothèses et modifie le code. Le script de contrôle possède les limites Git, la mesure, le rollback et l'état.

## Foreground et Background

| | Foreground | Background |
|---|---|---|
| Exécution | Tâche Codex actuelle | Controller détaché |
| Continuité | Goal Codex officiel | Un worker `codex exec` par itération |
| Usage | Observation et pilotage | Exécutions longues ou nocturnes |
| Contrôle | Pause/reprise du Goal | Status/stop/resume via `$codex-autoresearch` |

Foreground continue grâce au Goal officiel. Background n'utilise pas de Goal ; le controller assure la continuité. L'installation ne modifie aucun réglage Codex.

## Résultats

Les fichiers non commités se trouvent dans `autoresearch-results/` :

| Chemin | Rôle |
|---|---|
| `run.json` | Configuration confirmée et immuable |
| `events.jsonl` | Historique d'état en ajout seul |
| `logs/` | Sorties complètes des mesures, guards et workers |
| `runtime.json` | État du processus background |
| `runtime.log` | Cycle de vie du controller |

`events.jsonl` est l'unique source d'état. Un fichier manquant, corrompu ou contradictoire provoque une erreur explicite ; aucune reconstruction approximative n'est tentée.

## Historique et rapport

```text
$codex-autoresearch show experiment history
$codex-autoresearch export experiment history as TSV
$codex-autoresearch generate an HTML report
```

Le tableau et le rapport HTML sont générés à partir des événements validés. L'instantané HTML est écrit dans `autoresearch-results/report.html` et ne participe ni à l'état ni à la reprise.

## Garanties

- Une nouvelle exécution exige une branche Git nommée et propre.
- Une exécution gère un dépôt, une mesure et une cible.
- Chaque expérience est commitée ; un échec est annulé avec `git revert`.
- Les modifications hors périmètre, dérives Git, mesures invalides, échecs de commande, timeouts et rollbacks impossibles arrêtent l'exécution avec un chemin de log.
- Le statut devient `complete` uniquement lorsque la mesure conservée atteint la cible.

## Prérequis

- Version actuelle de Codex CLI avec Skills et Goals
- Python 3.11+
- Git

Voir [Installation](../INSTALL.md), [Guide utilisateur](../GUIDE.md) et [Exemples](../EXAMPLES.md).

Licence MIT. Inspiré par [autoresearch de Karpathy](https://github.com/karpathy/autoresearch).
