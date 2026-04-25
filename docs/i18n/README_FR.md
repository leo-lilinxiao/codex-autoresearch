<p align="center">
  <img src="../../image/banner.png" width="700" alt="Codex Autoresearch">
</p>

<h2 align="center"><b>Viser. Itérer. Aboutir.</b></h2>

<p align="center">
  <i>Expérimentation autonome orientée objectif pour Codex.</i>
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
  <b>🇫🇷 Français</b> ·
  <a href="README_DE.md">🇩🇪 Deutsch</a> ·
  <a href="README_ES.md">🇪🇸 Español</a> ·
  <a href="README_PT.md">🇧🇷 Português</a> ·
  <a href="README_RU.md">🇷🇺 Русский</a>
</p>

---

L'idée : dites à Codex ce que vous voulez améliorer, puis partez. Il modifie votre code, vérifie le résultat, conserve ou annule, et recommence. Vous revenez avec un journal d'expériences et un code amélioré.

Inspiré par [autoresearch de Karpathy](https://github.com/karpathy/autoresearch), généralisé au-delà du ML à tout ce qui se vérifie mécaniquement : couverture de tests, erreurs de types, latence, avertissements lint, failles de sécurité, état de préparation au déploiement — si une commande peut dire si ça s'est amélioré, la boucle peut itérer dessus.

## Démarrage rapide

```text
# Installation dans Codex (recommandée)
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

Redémarrez Codex, ouvrez votre projet et lancez-vous :

```
Vous:  $codex-autoresearch
       Je veux éliminer tous les types `any` dans mon code TypeScript

Codex: J'ai trouvé 47 occurrences de `any` dans src/**/*.ts.
       Répertoire Results : ./autoresearch-results/
       Métrique : nombre de `any` (actuel : 47), direction : diminuer
       Vérification : comptage grep + tsc --noEmit comme guard
       Mode d'exécution : foreground ou background ?

Vous:  Background, go. Laisse tourner toute la nuit.

Codex: Lancement en arrière-plan — référence : 47. Itération en cours.
```

Chaque amélioration s'accumule. Chaque échec est annulé. Tout est journalisé.

Options de copie manuelle, de symlink et d'installation utilisateur dans [INSTALL.md](../INSTALL.md). Manuel complet dans [GUIDE.md](../GUIDE.md).

## Comment ça fonctionne

```
Vous dites une phrase  →  Codex analyse et confirme  →  Vous dites "go"
                                                            |
                                             +--------------+--------------+
                                             |                             |
                                        foreground                    background
                                      (session en cours)           (détaché, toute la nuit)
                                             |                             |
                                             +--------------+--------------+
                                                            |
                                                            v
                                                  +-------------------+
                                                  |    La boucle      |
                                                  |                   |
                                                  |  modifier un élém.|
                                                  |  git commit       |
                                                  |  lancer verify    |
                                                  |  amélioré ? garder|
                                                  |  dégradé ? revert |
                                                  |  journaliser      |
                                                  |  recommencer      |
                                                  +-------------------+
```

C'est tout. Vous choisissez l'un ou l'autre : foreground garde la boucle dans votre session en cours, background la délègue à un processus détaché pour que vous puissiez dormir. Même boucle dans les deux cas, mais ils ne tournent pas en même temps.

## Ce que vous dites vs ce qui se passe

| Ce que vous dites | Ce qui se passe |
|-------------------|----------------|
| « Améliore ma couverture de tests » | Itère jusqu'à l'objectif ou interruption |
| « Corrige les 12 tests en échec » | Répare un par un jusqu'à zéro restant |
| « Pourquoi l'API renvoie 503 ? » | Traque la cause racine avec des hypothèses falsifiables |
| « Ce code est-il sûr ? » | Audit STRIDE + OWASP, chaque constat appuyé par du code |
| « Prêt à livrer » | Vérifie l'état de préparation, génère une checklist, contrôle la mise en production |
| « Je veux optimiser mais je ne sais pas quoi » | Analyse le dépôt, suggère des métriques, génère la configuration |

En coulisses, Codex associe votre phrase à l'un des 7 modes (loop, plan, debug, fix, security, ship, exec). Vous n'avez jamais besoin d'en choisir un.

## Ce que Codex déduit automatiquement

Pas besoin d'écrire de configuration. Codex infère tout à partir de votre phrase et de votre dépôt :

| Ce dont il a besoin | Comment il l'obtient | Exemple |
|---------------------|---------------------|---------|
| Objectif | Votre phrase | « éliminer tous les types any » |
| Périmètre | Analyse la structure du dépôt | `src/**/*.ts` |
| Métrique | Propose en fonction de l'objectif + outillage | nombre de any (actuel : 47) |
| Direction | Déduit de « améliorer » / « réduire » / « éliminer » | diminuer |
| Vérification | Associe à l'outillage du dépôt | comptage `grep` + `tsc --noEmit` |
| Guard | Suggère si un risque de régression existe | `npm test` |

Avant de commencer, Codex montre toujours ce qu'il a trouvé et demande confirmation. Ensuite vous choisissez foreground ou background et dites « go ».
Par défaut, le répertoire Results reste dans le contexte de lancement : si vous avez démarré Codex dans un dépôt git, la racine de ce dépôt est le workspace root par défaut ; si vous l'avez démarré hors d'un dépôt git, le répertoire de lancement courant est le workspace root par défaut. Codex ne doit pas l'élargir silencieusement à un répertoire parent sauf si vous confirmez explicitement un workspace multi-repo plus large. Le récapitulatif de confirmation doit toujours afficher le répertoire Results choisi avant le lancement.

## Quand ça bloque

Au lieu de réessayer aveuglément, la boucle escalade :

| Déclencheur | Action |
|-------------|--------|
| 3 échecs consécutifs | **REFINE** — ajuster dans la stratégie actuelle |
| 5 échecs consécutifs | **PIVOT** — essayer une approche fondamentalement différente |
| 2 PIVOT sans progrès | **Recherche web** — chercher des solutions externes |
| 3 PIVOT sans progrès | **Arrêt** — signaler qu'une intervention humaine est nécessaire |

Un seul succès réinitialise tous les compteurs.

## Journal des résultats

Chaque itération est enregistrée dans `autoresearch-results/results.tsv` :

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module
2          -        49      +8      discard   generic wrapper introduced new anys
3          d4e5f6g  38      -3      keep      type-narrow API response handlers
```

Les expériences échouées sont annulées dans git mais restent dans le journal. Le journal est la véritable piste d'audit, tandis que `autoresearch-results/state.json` est l'instantané de reprise.

## Fonctionnalités supplémentaires

Détails complets dans [GUIDE.md](../GUIDE.md) :

- **Apprentissage inter-exécutions** — les leçons des exécutions passées orientent la génération future d'hypothèses
- **Expériences parallèles** — teste jusqu'à 3 hypothèses simultanément via des git worktrees
- **Reprise de session** — les exécutions interrompues reprennent depuis le dernier état cohérent
- **Mode CI/CD** (`exec`) — non interactif, sortie JSON, pour les pipelines d'automatisation
- **Double vérification** — verify (y a-t-il amélioration ?) et guard (rien n'est cassé ?) séparés
- **Session hooks** — installés automatiquement ; maintiennent Codex sur la bonne voie entre les sessions

## FAQ

**Il ne fait que de petits changements. Peut-il tenter des idées plus ambitieuses ?**
Par défaut, la boucle privilégie des pas petits et vérifiables — c'est voulu. Mais elle peut voir plus grand : décrivez une hypothèse plus large dans votre prompt (par ex. « remplace le mécanisme d'attention par une attention linéaire et lance l'évaluation complète »), et elle la traitera comme une seule expérience à vérifier. L'usage optimal : l'humain fixe la direction de recherche, l'agent assure l'exécution et l'analyse intensives.

**C'est plutôt pour l'optimisation d'ingénierie ou pour la recherche ?**
C'est le plus efficace quand l'objectif et la métrique sont clairs — augmenter la couverture, réduire les erreurs, baisser la latence. Si la direction de recherche elle-même est incertaine, utilisez d'abord le mode `plan` pour explorer, puis passez à `loop` une fois que vous savez quoi mesurer. Voyez-le comme une collaboration humain-IA : vous apportez le jugement, l'agent apporte la vitesse d'itération.

**Comment l'arrêter ?** Foreground : interrompez Codex. Background : `$codex-autoresearch` puis demandez l'arrêt.

**Peut-il reprendre après une interruption ?** Oui. Il reprend automatiquement depuis `autoresearch-results/state.json`.

**Comment l'utiliser en CI ?** `Mode: exec` avec `codex exec`. Toute la configuration en amont, sortie JSON, codes de sortie 0/1/2.

## Documentation

| Doc | Contenu |
|-----|---------|
| [INSTALL.md](../INSTALL.md) | Toutes les méthodes d'installation, chemins de découverte des skills, configuration des hooks |
| [GUIDE.md](../GUIDE.md) | Manuel complet : modes, champs de configuration, modèle de sécurité, utilisation avancée |
| [EXAMPLES.md](../EXAMPLES.md) | Recettes par domaine : couverture, performance, types, sécurité, etc. |

## Remerciements

Construit sur les idées d'[autoresearch de Karpathy](https://github.com/karpathy/autoresearch). La plateforme Codex skills est développée par [OpenAI](https://openai.com).

## Star History

<a href="https://www.star-history.com/?repos=leo-lilinxiao%2Fcodex-autoresearch&type=timeline&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
 </picture>
</a>

## Licence

MIT — voir [LICENSE](../../LICENSE).
