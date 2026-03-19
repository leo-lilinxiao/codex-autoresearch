<p align="center">
  <img src="../../image/banner.png" width="700" alt="Codex Autoresearch">
</p>

<h2 align="center"><b>Aim. Iterate. Arrive.</b></h2>

<p align="center">
  <i>Le moteur d'experimentation autonome pilote par objectifs pour Codex.</i>
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

<p align="center">
  <a href="#demarrage-rapide">Demarrage rapide</a> ·
  <a href="#ce-quil-fait">Ce qu'il fait</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#modes">Modes</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="#apprentissage-inter-executions">Apprentissage</a> ·
  <a href="#experiences-paralleles">Parallele</a> ·
  <a href="../GUIDE.md">Guide d'utilisation</a> ·
  <a href="../EXAMPLES.md">Recettes</a>
</p>

---

## Demarrage rapide

**1. Installation :**

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
cp -r codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

Ou utilisez le skill installer dans Codex :
```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

**2. Ouvrez Codex dans votre projet et dites ce que vous voulez :**

```text
$codex-autoresearch
Eliminer tous les types `any` dans mon code TypeScript
```

**3. Codex analyse, confirme, puis itere de maniere autonome :**

```
Codex: J'ai trouve 47 occurrences de `any` dans src/**/*.ts.

       Confirme :
       - Objectif : eliminer les types `any` dans src/**/*.ts
       - Metrique : nombre de `any` (actuel : 47), direction : diminuer
       - Verification : comptage grep + tsc --noEmit comme garde

       A confirmer :
       - Continuer jusqu'a zero, ou limiter a N iterations ?

       Repondez "go" pour demarrer, ou dites-moi ce qu'il faut changer.

Vous:  Go, laissez tourner toute la nuit.

Codex: Demarrage -- base de reference : 47. Iteration continue jusqu'a interruption.
```

Chaque amelioration s'accumule. Chaque echec est annule. Tout est journalise.

Voir [INSTALL.md](../INSTALL.md) pour plus d'options d'installation. Voir [GUIDE.md](../GUIDE.md) pour le guide complet.

---

## Ce qu'il fait

Un skill Codex qui execute une boucle modifier-verifier-decider sur votre base de code. Chaque iteration effectue un changement atomique, le verifie par rapport a une metrique mecanique, puis conserve ou ecarte le resultat. Les progres s'accumulent dans git ; les echecs sont automatiquement annules. Fonctionne avec n'importe quel langage, n'importe quel framework, n'importe quel objectif mesurable.

Inspire par les principes d'[autoresearch de Karpathy](https://github.com/karpathy/autoresearch), generalise au-dela du ML.

### Pourquoi ce projet existe

L'autoresearch de Karpathy a prouve qu'une boucle simple -- modifier, verifier, conserver ou ecarter, repeter -- peut faire progresser l'entrainement ML d'une base de reference vers de nouveaux sommets en une nuit. codex-autoresearch generalise cette boucle a tout ce qui, en ingenierie logicielle, possede un nombre. Couverture de tests, erreurs de types, latence, avertissements du linter -- s'il y a une metrique, l'iteration autonome est possible.

---

## Architecture

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

La boucle tourne jusqu'a interruption (sans limite) ou exactement N iterations (limitee via `Iterations: N`).

**Pseudocode :**

```
PHASE 0: Sonder l'environnement, verifier la reprise de session
PHASE 1: Lire le contexte + le fichier de lecons

LOOP (infini ou N fois) :
  1. Examiner l'etat actuel + historique git + journal des resultats + lecons
  2. Choisir UNE hypothese (appliquer les perspectives, filtrer par environnement)
     -- ou N hypotheses si le mode parallele est actif
  3. Effectuer UN changement atomique
  4. git commit (avant verification)
  5. Lancer la verification mecanique + guard
  6. Ameliore -> conserver (extraire une lecon). Degrade -> git reset. Crash -> reparer ou ignorer.
  7. Journaliser le resultat
  8. Controle de sante (disque, git, sante de la verification)
  9. 3+ rejets consecutifs -> REFINE ; 5+ -> PIVOT ; 2 PIVOTs -> recherche web
  10. Repeter. Ne jamais s'arreter. Ne jamais demander.
```

---

## Modes

Sept modes, un seul schema d'invocation : `$codex-autoresearch` suivi d'une phrase decrivant ce que vous voulez. Codex detecte automatiquement le mode et vous guide dans une courte conversation pour completer la configuration.

| Mode | Cas d'utilisation | Condition d'arret |
|------|-------------------|-------------------|
| `loop` | Vous avez un objectif mesurable a optimiser | Interruption ou N iterations |
| `plan` | Vous avez un objectif mais pas la configuration | Bloc de configuration genere |
| `debug` | Vous avez besoin d'une analyse de cause racine avec preuves | Toutes les hypotheses testees ou N iterations |
| `fix` | Quelque chose est casse et doit etre repare | Le nombre d'erreurs atteint zero |
| `security` | Vous avez besoin d'un audit de vulnerabilites structure | Toutes les surfaces d'attaque couvertes ou N iterations |
| `ship` | Vous avez besoin d'une verification de mise en production | Tous les points de controle passes |
| `exec` | Pipeline CI/CD, aucun humain disponible | N iterations (toujours borne), sortie JSON |

**Selection rapide :**

```
"Je veux ameliorer X"           -->  loop  (ou plan si la metrique est incertaine)
"Quelque chose est casse"       -->  fix   (ou debug si la cause est inconnue)
"Ce code est-il securise ?"     -->  security
"On met en production"          -->  ship
codex exec --skill ...          -->  exec  (CI/CD, pas d'assistant)
```

---

## Configuration

### Champs obligatoires (mode `loop`)

| Champ | Type | Exemple |
|-------|------|---------|
| `Goal` | Objectif a atteindre | `Reduce type errors to zero` |
| `Scope` | Globs de fichiers modifiables | `src/**/*.ts` |
| `Metric` | Nombre a suivre | `type error count` |
| `Direction` | `higher` ou `lower` | `lower` |
| `Verify` | Commande shell produisant la metrique | `tsc --noEmit 2>&1 \| wc -l` |

### Champs optionnels

| Champ | Valeur par defaut | Objectif |
|-------|-------------------|----------|
| `Guard` | aucun | Commande de securite qui doit toujours passer (prevention de regression) |
| `Iterations` | illimite | Limiter a N iterations |
| `Run tag` | auto | Etiquette pour cette execution |
| `Stop condition` | aucun | Regle d'arret anticipe personnalisee |

En l'absence de champs obligatoires, un assistant interactif analyse votre depot et vous demande toujours confirmation avant de demarrer (jusqu'a 5 echanges). Vous n'avez jamais besoin de connaitre les noms des champs.

### Verification a double porte

Deux commandes servent des objectifs differents :

- **Verify** = "La metrique cible s'est-elle amelioree ?" (mesure le progres)
- **Guard** = "Rien d'autre n'a casse ?" (empeche les regressions)

```text
Verify: pytest --cov=src --cov-report=term 2>&1 | grep TOTAL | awk '{print $NF}'   # la couverture a-t-elle augmente ?
Guard: npx tsc --noEmit                                                              # les types passent-ils toujours ?
```

Si verify passe mais guard echoue, le changement est retravaille (jusqu'a 2 tentatives), puis annule. Les fichiers proteges par Guard ne sont jamais modifies.

---

## Guide de decision rapide

| Vous voulez... | Mode | Configuration cle |
|----------------|------|-------------------|
| Pousser un nombre dans une direction toute la nuit | `loop` | Goal + Metric + Verify |
| Determiner quelle metrique suivre | `plan` | Juste un Goal |
| Trouver pourquoi quelque chose est casse | `debug` | Scope + Symptom |
| Faire passer les tests/types/lint en echec | `fix` | Commande Target |
| Auditer le code pour les vulnerabilites | `security` | Scope + Focus |
| Publier en toute confiance | `ship` | Dites "on publie" ou "simulation d'abord" |
| Executer en CI/CD sans interaction | `exec` | Tous les champs en amont + Iterations |

---

## Details des modes

### loop

Le mode par defaut. Itere vers un objectif mesurable.

```
Vous:  Eliminer tous les types `any` dans mon code TypeScript

Codex: 47 `any` trouves dans src/**/*.ts.

       Confirme :
       - Objectif : eliminer tous les types `any`
       - Metrique : nombre de `any` (actuel : 47), direction : diminuer
       - Verification : comptage grep, Garde : tsc --noEmit

       A confirmer :
       - Continuer jusqu'a zero, ou limiter a N iterations ?

       Repondez "go" pour demarrer.

Vous:  Go, toute la nuit.
```

### plan

Convertit un objectif vague en une configuration de boucle validee.

```
Vous:  Je veux rendre notre API plus rapide mais je ne sais pas par ou commencer

Codex: J'ai analyse le depot. La couche API est dans src/api/ avec Express + Prisma.

       A confirmer :
       - Qu'est-ce qui compte le plus : latence p95, debit ou demarrage a froid ?
       - Tester toute l'API ou des endpoints specifiques ?

       Repondez avec votre priorite.

Vous:  Latence p95, l'endpoint /search est le plus lent.
```

### debug

Chasse aux bugs basee sur les preuves. Chaque iteration teste une hypothese falsifiable.

```
Vous:  Notre API renvoie des 503 aleatoirement sous charge, aucune idee pourquoi

Codex: Je vois un pool de connexions dans src/db/pool.ts, un limiteur de debit
       dans src/middleware/, et 3 gestionnaires async sans gestion d'erreurs.

       Confirme :
       - Symptome : 503 intermittents sous charge concurrente
       - Perimetre : src/api/, src/db/, src/middleware/

       A confirmer :
       - Quand cela a-t-il commence ? Apres un changement specifique, ou depuis toujours ?
       - Si je trouve la cause, dois-je aussi la corriger ?

       Repondez avec le contexte.

Vous:  Ca a commence apres la refactorisation du pool de connexions la semaine derniere. Trouvez d'abord la cause.
```

### fix

Repare les erreurs de maniere iterative jusqu'a ce que le compteur atteigne zero.

```
Vous:  pytest echoue, 12 tests casses apres la refactorisation

Codex: Je vois 12 echecs dans tests/.

       Confirme :
       - Objectif : faire passer tous les tests pytest
       - Actuel : 12 echecs

       A confirmer :
       - Dois-je aussi utiliser ruff comme garde contre les problemes de lint ?
       - Tout reparer ou se concentrer d'abord sur un module specifique ?

       Repondez "go" pour demarrer.

Vous:  Tout reparer, oui avec ruff en garde. Go.
```

### security

Audit en lecture seule STRIDE + OWASP + red team. Chaque constatation necessite une preuve dans le code.

```
Vous:  Verifier notre API pour les vulnerabilites d'injection

Codex: Confirme :
       - Perimetre : src/api/ et src/middleware/ (14 fichiers)
       - Focus : injection SQL, XSS, validation des entrees

       A confirmer :
       - Rapport uniquement, ou aussi corriger les problemes critiques ?
       - Dois-je aussi couvrir l'authentification/le controle d'acces ?

       Repondez avec votre preference.

Vous:  D'abord le rapport, et oui couvrir aussi l'authentification.
```

### ship

Verification de mise en production avec portes de controle. Detection automatique de ce que vous publiez (PR, deploiement, release).

```
Vous:  On met en production

Codex: Detecte : PR vers main avec 3 commits.

       Confirme :
       - Type : PR de code
       - Cible : branche main

       A confirmer :
       - Simulation d'abord, ou publication directe ?
       - Surveillance post-deploiement ? (5 min / 15 min / aucune)

       Repondez avec votre preference.

Vous:  Simulation d'abord.
```

Voir [GUIDE.md](../GUIDE.md) pour l'utilisation detaillee et les options avancees de chaque mode.

---

## Enchainement de modes

Les modes peuvent etre composes sequentiellement :

```
plan  -->  loop              # elaborer la configuration, puis executer
debug -->  fix               # trouver les bugs, puis les reparer
security + fix               # auditer et corriger en une seule passe
```

---

## Apprentissage inter-executions

Chaque execution extrait des lecons structurees -- ce qui a fonctionne, ce qui a echoue, et pourquoi. Les lecons sont conservees dans `autoresearch-lessons.md` (non commite, comme le journal des resultats) et consultees au demarrage des executions futures pour orienter la generation d'hypotheses vers les strategies eprouvees et eviter les impasses connues.

- Lecons positives apres chaque iteration conservee
- Lecons strategiques apres chaque decision PIVOT
- Lecons de synthese a la fin de l'execution
- Capacite : 50 entrees maximum, les anciennes entrees sont resumees avec decroissance temporelle

Voir `references/lessons-protocol.md` pour les details.

---

## Recuperation intelligente en cas de blocage

Au lieu de reessayer aveuglement apres des echecs, la boucle utilise un systeme d'escalade graduee :

| Declencheur | Action |
|-------------|--------|
| 3 rejets consecutifs | **REFINE** -- ajuster dans le cadre de la strategie actuelle |
| 5 rejets consecutifs | **PIVOT** -- abandonner la strategie, essayer une approche fondamentalement differente |
| 2 PIVOTs sans amelioration | **Recherche web** -- chercher des solutions externes |
| 3 PIVOTs sans amelioration | **Bloqueur souple** -- avertir et continuer avec des changements plus audacieux |

Un seul resultat conserve reinitialise tous les compteurs. Voir `references/pivot-protocol.md`.

---

## Experiences paralleles

Testez plusieurs hypotheses simultanement en utilisant des agents secondaires dans des worktrees git isoles :

```
Orchestrateur (agent principal)
  +-- Agent A (worktree-a) -> hypothese 1
  +-- Agent B (worktree-b) -> hypothese 2
  +-- Agent C (worktree-c) -> hypothese 3
```

L'orchestrateur choisit le meilleur resultat, le fusionne et ecarte le reste. Activez cette fonctionnalite pendant l'assistant en repondant "oui" aux experiences paralleles. Si les worktrees ne sont pas pris en charge, le systeme bascule en mode sequentiel.

Voir `references/parallel-experiments-protocol.md`.

---

## Reprise de session

Si Codex detecte une execution precedente interrompue (journal des resultats, fichier de lecons, commits d'experience), il peut reprendre a partir du dernier etat coherent au lieu de repartir de zero :

- **Etat coherent :** reprise immediate, assistant ignore
- **Partiellement coherent :** mini-assistant (1 echange) pour reconfirmer
- **Incoherent ou objectif different :** nouveau depart (ancien journal renomme)

Voir `references/session-resume-protocol.md`.

---

## Mode CI/CD (exec)

Mode non interactif pour les pipelines d'automatisation. Toute la configuration est fournie en amont -- pas d'assistant, toujours borne, sortie JSON.

```yaml
# Exemple GitHub Actions
- name: Autoresearch optimization
  run: codex exec --skill codex-autoresearch
         --goal "Reduce type errors" --scope "src/**/*.ts"
         --metric "type error count" --direction lower
         --verify "tsc --noEmit 2>&1 | grep -c error"
         --iterations 20
```

Codes de sortie : 0 = ameliore, 1 = pas d'amelioration, 2 = bloqueur critique.

Voir `references/exec-workflow.md`.

---

## Journal des resultats

Chaque iteration est enregistree au format TSV (`research-results.tsv`) :

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module with strict types
2          -        49      +8      discard   generic wrapper introduced new anys
3          c3d4e5f  38      -3      keep      type-narrow API response handlers
```

Un resume de progression est affiche toutes les 5 iterations. Les executions limitees affichent un resume final de la base de reference au meilleur resultat.

---

## Modele de securite

| Preoccupation | Traitement |
|---------------|------------|
| Arbre de travail sale | La boucle refuse de demarrer ; suggere le mode `plan` ou une branche propre |
| Changement echoue | `git reset --hard HEAD~1` garde l'historique propre ; le journal des resultats est la trace d'audit |
| Echec du Guard | Jusqu'a 2 tentatives de correction, puis annulation |
| Erreur de syntaxe | Correction automatique immediate, ne compte pas comme iteration |
| Crash a l'execution | Jusqu'a 3 tentatives de correction, puis passage au suivant |
| Epuisement des ressources | Annulation, essai d'une variante plus petite |
| Processus bloque | Arret apres timeout, annulation |
| Blocage (3+ rejets consecutifs) | REFINE pour ajuster la strategie, 5+ rejets -> PIVOT vers nouvelle approche, escalade vers recherche web si necessaire |
| Incertitude en cours de boucle | Application autonome des meilleures pratiques ; ne jamais interrompre pour demander a l'utilisateur |
| Effets de bord externes | Le mode `ship` exige une confirmation explicite pendant l'assistant de pre-lancement |
| Limites de l'environnement | Detection au demarrage ; les hypotheses irrealisables sont filtrees automatiquement |
| Session interrompue | Reprise a partir du dernier etat coherent lors de la prochaine invocation |

---

## Structure du projet

```
codex-autoresearch/
  SKILL.md                          # point d'entree du skill (charge par Codex)
  README.md                         # documentation en anglais
  CONTRIBUTING.md                   # guide de contribution
  LICENSE                           # MIT
  agents/
    openai.yaml                     # metadonnees UI Codex
  image/
    banner.png                      # banniere du projet
  docs/
    INSTALL.md                      # guide d'installation
    GUIDE.md                        # guide d'utilisation
    EXAMPLES.md                     # recettes par domaine
    i18n/
      README_ZH.md                  # chinois
      README_JA.md                  # japonais
      README_KO.md                  # coreen
      README_FR.md                  # ce fichier
      README_DE.md                  # allemand
      README_ES.md                  # espagnol
      README_PT.md                  # portugais
      README_RU.md                  # russe
  scripts/
    validate_skill_structure.sh     # script de validation de structure
  references/
    core-principles.md              # principes universels
    autonomous-loop-protocol.md     # specification du protocole de boucle
    plan-workflow.md                # specification du mode plan
    debug-workflow.md               # specification du mode debug
    fix-workflow.md                 # specification du mode fix
    security-workflow.md            # specification du mode security
    ship-workflow.md                # specification du mode ship
    exec-workflow.md                # specification du mode CI/CD non interactif
    interaction-wizard.md           # contrat de configuration interactive
    structured-output-spec.md       # specification du format de sortie
    modes.md                        # index des modes
    results-logging.md              # specification du format TSV
    lessons-protocol.md             # apprentissage inter-executions
    pivot-protocol.md               # recuperation intelligente (PIVOT/REFINE)
    web-search-protocol.md          # recherche web en cas de blocage
    environment-awareness.md        # detection materiel/ressources
    parallel-experiments-protocol.md # tests paralleles par sous-agents
    session-resume-protocol.md      # reprise des executions interrompues
    health-check-protocol.md        # auto-surveillance
    hypothesis-perspectives.md      # raisonnement multi-perspectives sur les hypotheses
```

---

## FAQ

**Comment choisir une metrique ?** Utilisez `Mode: plan`. Il analyse votre base de code et en suggere une.

**Compatible avec tous les langages ?** Oui. Le protocole est agnostique du langage. Seule la commande de verification est specifique au domaine.

**Comment l'arreter ?** Interrompez Codex, ou definissez `Iterations: N`. L'etat git est toujours coherent car les commits ont lieu avant la verification.

**Le mode security modifie-t-il mon code ?** Non. Analyse en lecture seule. Dites a Codex de "corriger aussi les problemes critiques" lors de la configuration pour activer la remediation.

**Combien d'iterations ?** Cela depend de la tache. 5 pour les corrections ciblees, 10-20 pour l'exploration, illimite pour les executions de nuit.

**Apprend-il d'une execution a l'autre ?** Oui. Les lecons sont extraites apres chaque execution et consultees au demarrage de la suivante. Le fichier de lecons persiste entre les sessions.

**Peut-il reprendre apres une interruption ?** Oui. Lors de l'invocation suivante, il detecte l'execution precedente et reprend a partir du dernier etat coherent.

**Peut-il effectuer des recherches web ?** Oui, lorsqu'il est bloque apres plusieurs pivots strategiques. Les resultats de recherche web sont traites comme des hypotheses et verifies mecaniquement.

**Comment l'utiliser en CI ?** Utilisez `Mode: exec` ou `codex exec`. Toute la configuration est fournie en amont, la sortie est en JSON, et les codes de sortie indiquent le succes ou l'echec.

**Peut-il tester plusieurs idees en meme temps ?** Oui. Activez les experiences paralleles lors de la configuration. Il utilise les worktrees git pour tester jusqu'a 3 hypotheses simultanement.

---

## Remerciements

Ce projet s'appuie sur les idees d'[autoresearch de Karpathy](https://github.com/karpathy/autoresearch). La plateforme Codex skills est fournie par [OpenAI](https://openai.com).

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

## Licence

MIT -- voir [LICENSE](../../LICENSE).
