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
  <a href="#comment-ca-fonctionne">Modes</a> ·
  <a href="#ce-que-codex-decouvre-automatiquement">Configuration</a> ·
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
       - Mode d'execution : foreground ou background ?
       - Continuer jusqu'a zero, ou limiter a N iterations ?

       Choisissez un mode d'execution puis repondez "go" pour demarrer,
       ou dites-moi ce qu'il faut changer.

Vous:  Background, go. Laissez tourner toute la nuit.

Codex: Demarrage en background -- base de reference : 47.
       Le runtime detache itere deja.
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

Le schema ci-dessous montre d'abord le lancement interactif, puis le noyau de boucle partage. Avant d'entrer dans la boucle, Codex sonde l'environnement, verifie s'il existe une session recuperable, confirme la configuration et impose un choix explicite entre `foreground` et `background`.

```
              +----------------------+
              | Sonde d'environnement|  <-- detecter CPU/GPU/RAM/toolchains
              +----------+-----------+
                         |
              +----------v-----------+
              | Reprise de session ? |  <-- inspecter resultats/etat precedents
              +----------+-----------+
                         |
              +----------v-----------+
              | Lire le contexte     |  <-- scope + lecons + etat du repo
              +----------+-----------+
                         |
              +----------v-----------+
              | Confirmation wizard  |  <-- objectif/metrique/verify/guard
              | + choix du mode      |      + foreground ou background
              +----------+-----------+
                         |
               +---------+---------+
               |                   |
     +---------v--------+  +-------v---------+
     | Execution en     |  | Execution en    |
     | foreground       |  | background      |
     | session courante |  | manifest + ctl  |
     | sans runtime     |  | runtime detache |
     +---------+--------+  +-------+---------+
               |                   |
               +---------+---------+
                         |
              +----------v-----------+
              | Noyau de boucle      |
              | partage              |
              | baseline -> change   |
              | -> verify/guard ->   |
              | keep/discard/log     |
              +----------+-----------+
                         |
              +----------v-----------+
              | Resultat superviseur |  <-- continuer / stop / needs_human
              +----------------------+
```

Foreground et background partagent exactement le meme protocole experimental. La seule difference est l'endroit ou la boucle s'execute : dans la session Codex courante pour foreground, ou dans le controleur detache pour background. Les deux tournent jusqu'a interruption (sans limite) ou pendant exactement N iterations (bornees via `Iterations: N`).

**Pseudocode :**

```
PHASE 0: Sonder l'environnement, verifier s'il existe une session recuperable
PHASE 1: Lire le contexte + le fichier de lecons
PHASE 2: Confirmer la configuration + choisir foreground ou background

SI foreground :
  executer la boucle dans la session Codex courante
SINON background :
  ecrire autoresearch-launch.json et demarrer le runtime detache

BOUCLE PARTAGEE (infini ou N fois) :
  1. Examiner l'etat actuel + historique git + journal des resultats + lecons
  2. Choisir UNE hypothese (appliquer les perspectives, filtrer par environnement)
     -- ou N hypotheses si le mode parallele est actif
  3. Effectuer UN changement atomique
  4. git commit (avant verification)
  5. Lancer la verification mecanique + guard
  6. Ameliore -> conserver (extraire une lecon). Degrade -> strategie de rollback approuvee. Crash -> reparer ou ignorer.
  7. Journaliser le resultat
  8. Controle de sante (disque, git, sante de la verification)
  9. 3+ rejets consecutifs -> REFINE ; 5+ -> PIVOT ; 2 PIVOTs -> recherche web
  10. Repeter. Ne jamais s'arreter. Ne jamais demander.
```

---

## Comment ca fonctionne

Vous dites ce que vous voulez en une phrase. Codex fait le reste.

Il analyse votre depot, propose un plan, confirme avec vous, puis itere de maniere autonome :

| Vous dites | Ce qui se passe |
|-----------|----------------|
| "Ameliorer ma couverture de tests" | Analyse le depot, propose une metrique, itere jusqu'a l'objectif ou interruption |
| "Reparer les 12 tests en echec" | Detecte les echecs, repare un par un jusqu'a zero |
| "Pourquoi l'API renvoie des 503 ?" | Traque la cause avec des hypotheses falsifiables et des preuves |
| "Ce code est-il securise ?" | Execute un audit STRIDE + OWASP, chaque constat etaye par du code |
| "On met en production" | Verifie la preparation, genere une checklist, controle le lancement |
| "Je veux optimiser mais je ne sais pas quoi mesurer" | Analyse le depot, suggere des metriques, genere une configuration prete a l'emploi |

En coulisses, Codex mappe votre phrase a l'un des 7 modes specialises
(loop, plan, debug, fix, security, ship, exec). Vous n'avez jamais besoin
de choisir un mode -- decrivez simplement votre objectif.

---

## Ce que Codex decouvre automatiquement

Codex infere tout a partir de votre phrase et de votre depot. Vous n'ecrivez jamais de configuration.

| Ce dont il a besoin | Comment il l'obtient | Exemple |
|--------------------|---------------------|---------|
| Objectif | Votre phrase | "eliminer tous les types any" |
| Portee | Analyse la structure du depot | decouvre automatiquement src/**/*.ts |
| Metrique | Propose en fonction de l'objectif + outillage | nombre de any (actuel : 47) |
| Direction | Infere de "ameliorer" / "reduire" / "eliminer" | diminuer |
| Commande de verification | Identifie l'outillage du depot | comptage grep + tsc --noEmit |
| Garde (optionnel) | Suggere si un risque de regression existe | npm test |

Avant de demarrer, Codex vous montre toujours ce qu'il a trouve et demande confirmation.
Un minimum d'un echange, jusqu'a cinq si necessaire. Ensuite vous choisissez `foreground` ou `background` puis vous dites "go". En `foreground`, l'iteration reste dans la session actuelle ; en `background`, elle est confiee au runtime detache pour que vous puissiez partir.
Pour un vrai fonctionnement sans surveillance, lancez Codex CLI avec des reglages d'approbation / sandbox qui n'interrompront pas `git commit` ou `git revert`. Dans un depot jetable ou autrement fiable, donner plus de permissions a Codex est l'option la plus simple.

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
       - Mode d'execution : foreground ou background ?
       - Continuer jusqu'a zero, ou limiter a N iterations ?

       Choisissez un mode d'execution puis repondez "go" pour demarrer.

Vous:  Background, go. Toute la nuit.

Codex: Demarrage en background. D'abord la base de reference, puis les iterations detachees.
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
       - Mode d'execution : foreground ou background ?
       - Dois-je aussi utiliser ruff comme garde contre les problemes de lint ?
       - Tout reparer ou se concentrer d'abord sur un module specifique ?

       Choisissez un mode d'execution puis repondez "go" pour demarrer.

Vous:  Foreground, go. Tout reparer, oui avec ruff en garde.
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

Chaque execution iterative sauf `exec` extrait des lecons structurees -- ce qui a fonctionne, ce qui a echoue, et pourquoi. Les lecons sont conservees dans `autoresearch-lessons.md` (non commite, comme le journal des resultats) et consultees au demarrage des executions futures pour orienter la generation d'hypotheses vers les strategies eprouvees et eviter les impasses connues. Le mode `exec` peut lire les lecons existantes, mais ne les cree ni ne les met a jour.

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

Si Codex detecte une execution interactive precedemment interrompue, il peut reprendre depuis le dernier etat coherent au lieu de recommencer. La source de recuperation principale est `autoresearch-state.json`, un instantane d'etat compact mis a jour atomiquement a chaque iteration. En mode `exec`, l'etat n'existe que dans un fichier temporaire sous `/tmp/codex-autoresearch-exec/...` et le workflow `exec` doit le nettoyer explicitement avant la sortie. `foreground` reprend directement via `research-results.tsv` et `autoresearch-state.json`; `background` exige toujours un `autoresearch-launch.json` deja present.

Priorite de recuperation en mode interactif :

1. **JSON + TSV coherents, manifeste de lancement present :** reprise immediate, assistant saute
2. **JSON valide, TSV incoherent :** mini-assistant (1 tour de confirmation)
3. **JSON absent ou corrompu, TSV present :** l'utilitaire reconstruit l'etat retenu pour confirmation puis continue avec un nouveau manifeste de lancement
4. **Aucun des deux :** nouveau depart (les artefacts persistants precedents du controle d'execution sont archives)

Voir `references/session-resume-protocol.md`.

---

## Mode CI/CD (exec)

Mode non interactif pour les pipelines d'automatisation. Toute la configuration est fournie en amont -- pas d'assistant, toujours borne, sortie JSON.

```yaml
# Exemple GitHub Actions
- name: Autoresearch optimization
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

Codes de sortie : 0 = ameliore, 1 = pas d'amelioration, 2 = bloqueur critique.

Avant d'utiliser `codex exec` en CI, configurez a l'avance l'authentification du CLI Codex. Dans un environnement d'automatisation controle, privilegiez `codex exec --dangerously-bypass-approvals-and-sandbox ...` afin que les executions `exec` autonomes suivent la politique par defaut `danger_full_access` de la runtime geree. Pour les executions programmatiques, l'authentification par API key est l'option a privilegier.

Lorsque `Mode: exec` passe par les helpers livres avec la skill, ne renommez pas manuellement les anciens artefacts a la racine du repo. `autoresearch_init_run.py --mode exec ...` archive deja `research-results.tsv` et `autoresearch-state.json` sous les noms canoniques `research-results.prev.tsv` et `autoresearch-state.prev.json` avant d'initialiser une nouvelle execution.

Voir `references/exec-workflow.md`.

---

## Journal des resultats

Chaque iteration est enregistree dans deux formats complementaires :

- **`research-results.tsv`** -- piste d'audit complete, avec une ligne principale par iteration et, si besoin, des lignes worker paralleles
- **`autoresearch-state.json`** -- instantane d'etat compact pour une reprise de session rapide en mode interactif

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module with strict types
2          -        49      +8      discard   generic wrapper introduced new anys
3          c3d4e5f  38      -3      keep      type-narrow API response handlers
```

En mode `exec`, l'instantane d'etat n'existe que dans `/tmp/codex-autoresearch-exec/...` et le workflow `exec` doit le supprimer explicitement avant la sortie. Mettez a jour ces artefacts via les helper scripts integres sous `<skill-root>/scripts/...`, et non via le repertoire `scripts/` du depot cible.

Les deux fichiers ne sont pas commites dans git. Lors de la reprise de session, l'etat JSON est croise avec un resume reconstruit des iterations principales TSV, et non avec le simple nombre de lignes. Les resumes de progression sont affiches toutes les 5 iterations. Les executions bornees affichent un resume final de la base au meilleur resultat.

Ces artefacts d'etat sont bien geres par les helper scripts fournis sous `<skill-root>/scripts/...`, mais la plupart des utilisateurs devraient rester sur l'unique point d'entree humain : **`$codex-autoresearch`**. Ici, `<skill-root>` designe le repertoire contenant le `SKILL.md` charge ; dans l'installation repo-locale courante, c'est `.agents/skills/codex-autoresearch`.

Si vous automatisez ou deboguez la control-plane, les helpers centres sur le repo utilisent `--repo <repo>` par defaut. Preferez alors :

- `python3 <skill-root>/scripts/autoresearch_resume_check.py --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_launch_gate.py --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo <repo>`

`--results-path`, `--state-path`, `--launch-path` et `--runtime-path` restent disponibles comme overrides avances. La meme convention repo-first s'applique aussi aux appels directs de `autoresearch_resume_prompt.py` et `autoresearch_supervisor_status.py`.

Pour les utilisateurs humains, il n'y a maintenant plus qu'un seul point d'entree principal : **`$codex-autoresearch`**.

- Lors du premier lancement interactif, decrivez naturellement l'objectif, repondez aux questions de confirmation, choisissez explicitement `foreground` ou `background`, puis repondez `go`
- En `foreground`, Codex reste dans la session courante, continue la boucle en direct et n'ecrit que `research-results.tsv`, `autoresearch-state.json` et les lessons
- En `background`, Codex ecrit `autoresearch-launch.json` et demarre automatiquement le controleur d'execution detache
- `foreground` et `background` partagent le meme protocole de boucle, la meme semantique de metrique et les memes regles de repo/scope, mais ils sont mutuellement exclusifs pour un meme repo/run ; n'utilisez pas les deux modes en meme temps sur les memes artefacts du depot primaire
- Si vous voulez ensuite reprendre ce meme run interactif dans l'autre mode, restez sur la meme entree `$codex-autoresearch` ; avant la reprise, la skill synchronise en interne l'etat partage vers le mode cible, et background `start` effectue automatiquement la meme synchronisation
- Les executions sur un seul depot restent le cas par defaut ; dans ce cas, le scope declare ne s'applique qu'au depot primaire qui porte les artefacts de controle
- Si l'experience couvre plusieurs depots, le manifeste de lancement confirme peut aussi declarer des depots companions avec un scope distinct pour chacun. Le preflight du runtime couvre alors tous les depots geres, tandis que `research-results.tsv`, `autoresearch-state.json` et les artefacts de controle restent ancres dans le depot primaire
- Dans ce modele, la colonne `commit` du TSV continue de suivre uniquement le commit du depot primaire ; la provenance des commits des depots companions est conservee dans `autoresearch-state.json`
- Chaque cycle gere en `background` lance ensuite une session `codex exec` non interactive, avec le prompt runtime transmis via stdin
- `execution_policy` ne s'applique qu'aux chemins qui lancent des sessions Codex imbriquees, donc `background` et `exec` ; ce skill utilise `danger_full_access` par defaut
- Les demandes ulterieures comme `status`, `stop` ou `resume` passent toujours par le meme `$codex-autoresearch` ; `status/stop` ne valent que pour `background`
- `Mode: exec` reste la voie avancee pour le CI ou l'automatisation entierement specifiee

Les commandes directes de pilotage restent disponibles pour le scripting ou le debug de l'execution :

- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo <repo>`


---

## Modele de securite

| Preoccupation | Traitement |
|---------------|------------|
| Arbre de travail sale | Le preflight runtime bloque le lancement ou le relancement tant que les changements hors perimetre ne sont pas nettoyes ou isoles |
| Changement echoue | Utilise la strategie de rollback approuvee avant le lancement : `git reset --hard HEAD~1` seulement dans une branche/worktree d'experience isolee et approuvee, sinon `git revert --no-edit HEAD` ; le journal des resultats reste la trace d'audit |
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
| Derive du contexte (longues executions) | Verification d'empreinte du protocole toutes les 10 iterations ; verification plus frequente apres compaction ; relecture depuis le disque en cas d'echec |

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
    validate_skill_structure.sh     # structure validator
    autoresearch_helpers.py         # utilitaires partages pour TSV / JSON / runtime
    autoresearch_launch_gate.py     # decide fresh / resumable / needs_human avant le lancement
    autoresearch_resume_prompt.py   # construit le prompt pilote par le runtime a partir de la configuration enregistree
    autoresearch_runtime_ctl.py     # pilote launch / create-launch / start / status / stop du runtime
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

**Apprend-il d'une execution a l'autre ?** Oui. Les lecons sont extraites apres chaque `keep`, apres chaque `pivot` et a la fin de l'execution geree lorsqu'aucune lecon recente n'existe. Le fichier de lecons persiste entre les sessions ; `exec` ne fait que lire les lecons existantes.

**Peut-il reprendre apres une interruption ?** Oui. `foreground` reprend avec `research-results.tsv` et `autoresearch-state.json` ; `background` demande en plus `autoresearch-launch.json`. Si l'etat de lancement confirme manque, relance un nouveau run `background` via le flux normal de lancement.

**Peut-il effectuer des recherches web ?** Oui, lorsqu'il est bloque apres plusieurs pivots strategiques. Les resultats de recherche web sont traites comme des hypotheses et verifies mecaniquement.

**Comment l'utiliser en CI ?** Utilisez `Mode: exec` ou `codex exec`. Dans un environnement d'automatisation controle, preferez `codex exec --dangerously-bypass-approvals-and-sandbox ...` afin d'aligner les permissions sur la runtime par defaut. Toute la configuration est fournie en amont, la sortie est en JSON, et les codes de sortie indiquent le succes ou l'echec.

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
