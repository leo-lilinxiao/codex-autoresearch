<p align="center">
  <img src="../../image/banner.png" width="700" alt="Codex Autoresearch">
</p>

<h2 align="center"><b>Aim. Iterate. Arrive.</b></h2>

<p align="center">
  <i>Motor de experimentacion autonoma dirigida por objetivos para Codex.</i>
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
  <a href="README_DE.md">🇩🇪 Deutsch</a> ·
  <b>🇪🇸 Español</b> ·
  <a href="README_PT.md">🇧🇷 Português</a> ·
  <a href="README_RU.md">🇷🇺 Русский</a>
</p>

<p align="center">
  <a href="#inicio-rapido">Inicio rapido</a> ·
  <a href="#que-hace">Que hace</a> ·
  <a href="#arquitectura">Arquitectura</a> ·
  <a href="#como-funciona">Modos</a> ·
  <a href="#lo-que-codex-descubre-automaticamente">Configuracion</a> ·
  <a href="#aprendizaje-entre-ejecuciones">Aprendizaje</a> ·
  <a href="#experimentos-paralelos">Paralelo</a> ·
  <a href="../GUIDE.md">Guia de operacion</a> ·
  <a href="../EXAMPLES.md">Recetas</a>
</p>

---

## Inicio rapido

**1. Instalacion:**

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
cp -r codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

O usa el skill installer en Codex:
```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

**2. Abre Codex en tu proyecto y di lo que quieres hacer:**

```text
$codex-autoresearch
Quiero eliminar todos los tipos `any` de mi codigo TypeScript
```

**3. Codex escanea, confirma y luego itera de forma autonoma:**

```
Codex: Encontre 47 ocurrencias de `any` en src/**/*.ts.

       Confirmado:
       - Objetivo: eliminar los tipos `any` en src/**/*.ts
       - Metrica: cantidad de `any` (actual: 47), direccion: reducir
       - Verificacion: grep + tsc --noEmit como guardia

       Necesito confirmar:
       - Modo de ejecucion: foreground o background?
       - Ejecutar hasta eliminar todos, o limitar a N iteraciones?

       Elige un modo de ejecucion y luego responde "go" para empezar,
       o dime que cambiar.

Tu:    Background, go. Que corra toda la noche.

Codex: Iniciando ejecucion en background -- linea base: 47.
       El runtime desacoplado ya esta iterando.
```

Las mejoras se acumulan. Los fallos se revierten. Todo queda registrado.

Mas opciones de instalacion en [INSTALL.md](../INSTALL.md). Manual completo en [GUIDE.md](../GUIDE.md).

---

## Que hace

Un skill de Codex que ejecuta un bucle de "modificar-verificar-decidir" sobre tu codigo. Cada iteracion realiza un cambio atomico, lo verifica contra una metrica mecanica y conserva o descarta el resultado. El progreso se acumula en git; los fallos se revierten automaticamente. Funciona con cualquier lenguaje, cualquier framework, cualquier objetivo medible.

Inspirado en los principios de [autoresearch de Karpathy](https://github.com/karpathy/autoresearch), generalizado mas alla de ML.

### Por que existe

El autoresearch de Karpathy demostro que un bucle simple -- modificar, verificar, conservar o descartar, repetir -- puede llevar un entrenamiento de ML de la linea base a nuevos maximos durante la noche. codex-autoresearch generaliza ese bucle a todo en ingenieria de software que tenga un numero. Cobertura de tests, errores de tipos, latencia de rendimiento, advertencias de lint -- si hay una metrica, puede iterar de forma autonoma.

---

## Arquitectura

El diagrama siguiente muestra el lanzamiento interactivo y luego el nucleo de bucle compartido. Antes de entrar en el bucle, Codex sondea el entorno, comprueba si hay una sesion recuperable, confirma la configuracion y exige elegir `foreground` o `background`.

```
              +----------------------+
              | Sondeo de entorno    |  <-- detectar CPU/GPU/RAM/toolchains
              +----------+-----------+
                         |
              +----------v-----------+
              | Reanudar sesion?     |  <-- inspeccionar resultados/estado previos
              +----------+-----------+
                         |
              +----------v-----------+
              | Leer contexto        |  <-- scope + lecciones + estado del repo
              +----------+-----------+
                         |
              +----------v-----------+
              | Confirmacion wizard  |  <-- objetivo/metrica/verify/guard
              | + elegir modo        |      + foreground o background
              +----------+-----------+
                         |
               +---------+---------+
               |                   |
     +---------v--------+  +-------v---------+
     | Ejecucion en     |  | Ejecucion en    |
     | foreground       |  | background      |
     | sesion actual    |  | manifest + ctl  |
     | sin runtime files|  | runtime aparte  |
     +---------+--------+  +-------+---------+
               |                   |
               +---------+---------+
                         |
              +----------v-----------+
              | Nucleo de bucle      |
              | compartido           |
              | baseline -> cambio   |
              | -> verify/guard ->   |
              | keep/discard/log     |
              +----------+-----------+
                         |
              +----------v-----------+
              | Resultado supervisor |  <-- continuar / stop / needs_human
              +----------------------+
```

Foreground y background comparten exactamente el mismo protocolo experimental. La unica diferencia es donde se ejecuta el bucle: en la sesion actual de Codex para foreground, o en el controlador desacoplado para background. Ambos corren hasta ser interrumpidos (sin limite) o por exactamente N iteraciones (acotado con `Iterations: N`).

**Pseudocodigo:**

```
PHASE 0: Detectar entorno, comprobar si hay una sesion recuperable
PHASE 1: Leer contexto + archivo de lecciones
PHASE 2: Confirmar configuracion + elegir foreground o background

SI foreground:
  ejecutar el bucle en la sesion actual de Codex
SI NO background:
  escribir autoresearch-launch.json e iniciar el runtime desacoplado

BUCLE COMPARTIDO (para siempre o N veces):
  1. Revisar estado actual + historial git + registro de resultados + lecciones
  2. Elegir UNA hipotesis (aplicar perspectivas, filtrar por entorno)
     -- o N hipotesis si el modo paralelo esta activo
  3. Hacer UN cambio atomico
  4. git commit (antes de la verificacion)
  5. Ejecutar verificacion mecanica + guard
  6. Mejoro -> conservar (extraer leccion). Empeoro -> estrategia de rollback aprobada. Fallo -> reparar o saltar.
  7. Registrar el resultado
  8. Health check (disco, git, salud de verificacion)
  9. Si 3+ descartes -> REFINE; 5+ -> PIVOT; 2 PIVOTs -> busqueda web
  10. Repetir. Nunca parar. Nunca preguntar.
```

---

## Como funciona

Dices lo que quieres en una frase. Codex hace el resto.

Escanea tu repositorio, propone un plan, confirma contigo y luego itera de forma autonoma:

| Tu dices | Lo que sucede |
|---------|--------------|
| "Mejorar mi cobertura de tests" | Escanea el repo, propone metrica, itera hasta el objetivo o interrupcion |
| "Arreglar los 12 tests que fallan" | Detecta fallos, repara uno a uno hasta que queden cero |
| "Por que la API devuelve 503?" | Rastrea la causa raiz con hipotesis falsificables y evidencia |
| "Este codigo es seguro?" | Ejecuta auditoria STRIDE + OWASP, cada hallazgo respaldado por codigo |
| "Lanzar" | Verifica preparacion, genera checklist, lanzamiento con puertas |
| "Quiero optimizar pero no se que medir" | Analiza el repo, sugiere metricas, genera configuracion lista para usar |

Detras de escena, Codex mapea tu frase a uno de 7 modos especializados
(loop, plan, debug, fix, security, ship, exec). Nunca necesitas elegir un modo --
solo describe tu objetivo.

---

## Lo que Codex descubre automaticamente

Codex infiere todo a partir de tu frase y tu repositorio. Nunca escribes configuracion.

| Lo que necesita | Como lo obtiene | Ejemplo |
|----------------|----------------|---------|
| Objetivo | Tu frase | "eliminar todos los tipos any" |
| Alcance | Escanea la estructura del repo | descubre automaticamente src/**/*.ts |
| Metrica | Propone segun objetivo + herramientas | conteo de any (actual: 47) |
| Direccion | Infiere de "mejorar" / "reducir" / "eliminar" | reducir |
| Comando de verificacion | Identifica herramientas del repo | conteo grep + tsc --noEmit |
| Guardia (opcional) | Sugiere si existe riesgo de regresion | npm test |

Antes de empezar, Codex siempre te muestra lo que encontro y pide confirmacion.
Minimo una ronda de confirmacion, hasta cinco si es necesario. Luego eliges `foreground` o `background` y dices "go". En `foreground`, la iteracion sigue en la sesion actual; en `background`, se entrega al runtime desacoplado para que puedas irte.
Para ejecuciones realmente desatendidas, inicia Codex CLI con ajustes de aprobacion / sandbox que no interrumpan `git commit` ni `git revert`. En un repositorio desechable o de confianza, dar a Codex permisos mas amplios es la opcion mas simple.

### Verificacion de doble puerta

Dos comandos con funciones distintas:

- **Verify** = "La metrica objetivo mejoro?" (mide el progreso)
- **Guard** = "Se rompio algo mas?" (previene regresiones)

```text
Verify: pytest --cov=src --cov-report=term 2>&1 | grep TOTAL | awk '{print $NF}'   # subio la cobertura?
Guard: npx tsc --noEmit                                                              # los tipos siguen pasando?
```

Si verify pasa pero guard falla, el cambio se reajusta (hasta 2 intentos) y luego se revierte. Los archivos de Guard nunca se modifican.

---

## Detalles de los modos

### loop

Modo por defecto. Itera hacia un objetivo medible.

```
Tu:    Elimina todos los tipos `any` de mi codigo TypeScript

Codex: Encontre 47 `any` en src/**/*.ts.

       Confirmado:
       - Objetivo: eliminar todos los tipos `any`
       - Metrica: cantidad de `any` (actual: 47), direccion: reducir
       - Verificacion: grep count, Guard: tsc --noEmit

       Necesito confirmar:
       - Modo de ejecucion: foreground o background?
       - Ejecutar hasta cero, o limitar a N iteraciones?

       Elige un modo de ejecucion y luego responde "go" para empezar.

Tu:    Background, go. Toda la noche.

Codex: Iniciando ejecucion en background. Primero la linea base, luego las iteraciones desacopladas.
```

### plan

Convierte un objetivo vago en una configuracion de bucle validada.

```
Tu:    Quiero que nuestra API sea mas rapida pero no se por donde empezar

Codex: Escanee el repositorio. La capa API esta en src/api/ con Express + Prisma.

       Necesito confirmar:
       - Que importa mas: latencia p95, throughput o arranque en frio?
       - Hacer benchmark de toda la API o de endpoints especificos?

       Dime tu prioridad.

Tu:    Latencia p95, el endpoint /search es el peor.
```

### debug

Caza de bugs basada en evidencia. Cada iteracion prueba una hipotesis falsificable.

```
Tu:    Nuestra API devuelve 503 aleatoriamente bajo carga, no se por que

Codex: Veo connection pooling en src/db/pool.ts, rate limiting en src/middleware/,
       y 3 handlers asincronos sin limites de error.

       Confirmado:
       - Sintoma: 503 intermitentes bajo carga concurrente
       - Alcance: src/api/, src/db/, src/middleware/

       Necesito confirmar:
       - Cuando empezo? Despues de un cambio especifico, o siempre?
       - Si encuentro la causa, tambien la reparo?

       Dame contexto.

Tu:    Empezo despues de la refactorizacion del connection pool la semana pasada. Primero encuentra la causa.
```

### fix

Repara errores iterativamente hasta que el conteo llegue a cero.

```
Tu:    pytest esta fallando, 12 tests rotos despues de la refactorizacion

Codex: Veo 12 fallos en tests/.

       Confirmado:
       - Objetivo: hacer que todos los tests de pytest pasen
       - Actual: 12 fallos

       Necesito confirmar:
       - Modo de ejecucion: foreground o background?
       - Tambien usar ruff como guardia para evitar introducir problemas de lint?
       - Reparar los 12, o enfocarse en un modulo primero?

       Elige un modo de ejecucion y luego responde "go" para empezar.

Tu:    Foreground, go. Repara todos y usa ruff como guardia.
```

### security

Auditoria de solo lectura STRIDE + OWASP + red team. Cada hallazgo requiere evidencia en codigo.

```
Tu:    Revisa nuestra API en busca de vulnerabilidades de inyeccion

Codex: Confirmado:
       - Alcance: src/api/ y src/middleware/ (14 archivos)
       - Enfoque: inyeccion SQL, XSS, sanitizacion de entrada

       Necesito confirmar:
       - Solo reporte, o tambien reparar hallazgos criticos?
       - Tambien cubrir autenticacion/control de acceso?

       Dime tu preferencia.

Tu:    Primero el reporte, y si cubre autenticacion tambien.
```

### ship

Verificacion de lanzamiento con puertas. Detecta automaticamente que estas lanzando (PR, despliegue, release).

```
Tu:    Lanzar

Codex: Detectado: PR a main con 3 commits.

       Confirmado:
       - Tipo: PR de codigo
       - Destino: rama main

       Necesito confirmar:
       - Primero un ensayo o directamente en vivo?
       - Monitoreo post-lanzamiento? (5 min / 15 min / omitir)

       Dime tu preferencia.

Tu:    Primero un ensayo.
```

Consulta [GUIDE.md](../GUIDE.md) para uso detallado y opciones avanzadas de cada modo.

---

## Combinacion de modos

Los modos pueden componerse secuencialmente:

```
plan  -->  loop              # primero generar configuracion, luego ejecutar
debug -->  fix               # primero encontrar bugs, luego repararlos
security + fix               # auditar y remediar en un solo paso
```

---

## Aprendizaje entre ejecuciones

Cada ejecucion iterativa salvo `exec` extrae lecciones estructuradas -- que funciono, que fallo y por que. Las lecciones se almacenan en `autoresearch-lessons.md` (sin commit, como el registro de resultados) y se consultan al inicio de ejecuciones futuras para sesgar la generacion de hipotesis hacia estrategias probadas y lejos de callejones sin salida conocidos. El modo `exec` puede leer las lecciones existentes, pero no las crea ni las actualiza.

- Lecciones positivas despues de cada iteracion conservada
- Lecciones estrategicas despues de cada decision PIVOT
- Lecciones de resumen al completar una ejecucion
- Capacidad: maximo 50 entradas, las mas antiguas se resumen con decaimiento temporal

Consulta `references/lessons-protocol.md` para mas detalles.

---

## Recuperacion inteligente de bloqueos

En lugar de reintentar ciegamente despues de fallos, el bucle usa un sistema de escalamiento graduado:

| Disparador | Accion |
|------------|--------|
| 3 descartes consecutivos | **REFINE** -- ajustar dentro de la estrategia actual |
| 5 descartes consecutivos | **PIVOT** -- abandonar la estrategia, probar un enfoque fundamentalmente diferente |
| 2 PIVOTs sin mejora | **Busqueda web** -- buscar soluciones externas |
| 3 PIVOTs sin mejora | **Bloqueo suave** -- advertir y continuar con cambios mas audaces |

Un solo conservar exitoso reinicia todos los contadores. Consulta `references/pivot-protocol.md`.

---

## Experimentos paralelos

Prueba multiples hipotesis simultaneamente usando workers subagente en worktrees git aislados:

```
Orquestador (agente principal)
  +-- Worker A (worktree-a) -> hipotesis 1
  +-- Worker B (worktree-b) -> hipotesis 2
  +-- Worker C (worktree-c) -> hipotesis 3
```

El orquestador elige el mejor resultado, lo fusiona y descarta el resto. Activa los experimentos paralelos durante el asistente diciendo "si". Si los worktrees no son compatibles, se ejecuta en serie.

Consulta `references/parallel-experiments-protocol.md`.

---

## Reanudacion de sesion

Si Codex detecta una ejecucion interactiva interrumpida, puede reanudar desde el ultimo estado consistente en lugar de empezar de cero. La fuente de recuperacion principal es `autoresearch-state.json`, una instantanea de estado compacta actualizada atomicamente en cada iteracion. En modo `exec`, el estado solo existe en un archivo temporal bajo `/tmp/codex-autoresearch-exec/...` y el flujo `exec` debe limpiarlo explicitamente antes de salir. `foreground` reanuda con `research-results.tsv` y `autoresearch-state.json`; `background` sigue requiriendo un `autoresearch-launch.json` para la reanudacion directa del controlador desacoplado.

Prioridad de recuperacion para modos interactivos:

1. **JSON + TSV consistentes y manifiesto de lanzamiento presente:** reanudacion inmediata, asistente omitido
2. **JSON valido, TSV inconsistente:** mini-asistente (1 ronda de confirmacion)
3. **JSON ausente o corrupto, TSV presente:** la utilidad reconstruye el estado retenido para confirmarlo y luego continua con un nuevo manifiesto de lanzamiento
4. **Ninguno presente:** inicio limpio (se archivan los artefactos persistentes del control de ejecucion anterior)

Ver `references/session-resume-protocol.md`.

---

## Modo CI/CD (exec)

Modo no interactivo para pipelines de automatizacion. Toda la configuracion se proporciona por adelantado -- sin asistente, siempre limitado, salida JSON.

```yaml
# Ejemplo de GitHub Actions
- name: Optimizacion con Autoresearch
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

Codigos de salida: 0 = mejoro, 1 = sin mejora, 2 = bloqueo duro.

Antes de usar `codex exec` en CI, configura por adelantado la autenticacion del CLI de Codex. En entornos de automatizacion controlados conviene usar `codex exec --dangerously-bypass-approvals-and-sandbox ...` para que las ejecuciones `exec` independientes coincidan con la politica predeterminada `danger_full_access` del runtime gestionado. Para ejecuciones programaticas, la autenticacion mediante API key es la opcion preferida.

Cuando `Mode: exec` se ejecuta mediante los helper scripts incluidos con la skill, no renombres manualmente los artefactos antiguos en la raiz del repo. `autoresearch_init_run.py --mode exec ...` ya archiva `research-results.tsv` y `autoresearch-state.json` con los nombres canonicos `research-results.prev.tsv` y `autoresearch-state.prev.json` antes de iniciar la nueva ejecucion.

Consulta `references/exec-workflow.md`.

---

## Registro de resultados

Cada iteracion se registra en dos formatos complementarios:

- **`research-results.tsv`** -- pista de auditoria completa, con una fila principal por iteracion y filas worker paralelas cuando haga falta
- **`autoresearch-state.json`** -- instantanea de estado compacta para reanudacion rapida de sesion en modos interactivos

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module with strict types
2          -        49      +8      discard   generic wrapper introduced new anys
3          c3d4e5f  38      -3      keep      type-narrow API response handlers
```

En modo `exec`, la instantanea de estado solo vive bajo `/tmp/codex-autoresearch-exec/...` y el flujo `exec` debe eliminarla explicitamente antes de salir. Actualiza estos artefactos mediante los helper scripts incluidos en `<skill-root>/scripts/...`, no desde el directorio `scripts/` del repo objetivo.

Ambos archivos no se commitean en git. Durante la reanudacion de sesion, el estado JSON se valida cruzadamente con un resumen reconstruido de las iteraciones principales TSV, no con el simple conteo de filas. Los resumenes de progreso se imprimen cada 5 iteraciones. Las ejecuciones acotadas imprimen un resumen final de linea base a mejor resultado.

Estos artefactos de estado se mantienen con helper scripts incluidos bajo `<skill-root>/scripts/...`, pero la mayoria de los usuarios deberia seguir usando el unico punto de entrada humano: **`$codex-autoresearch`**. Aqui `<skill-root>` significa el directorio que contiene el `SKILL.md` cargado; en la instalacion repo-local mas comun es `.agents/skills/codex-autoresearch`.

Si estas automatizando o depurando el control-plane, los helpers orientados al repo usan `--repo <repo>` por defecto. Prefiere:

- `python3 <skill-root>/scripts/autoresearch_resume_check.py --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_launch_gate.py --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo <repo>`

`--results-path`, `--state-path`, `--launch-path` y `--runtime-path` siguen disponibles como overrides avanzados. La misma convencion repo-first tambien aplica si invocas directamente `autoresearch_resume_prompt.py` o `autoresearch_supervisor_status.py`.

De cara al usuario humano, ahora solo hay un punto de entrada principal: **`$codex-autoresearch`**.

- En la primera ejecucion interactiva, describe el objetivo de forma natural, responde las preguntas de confirmacion, elige explicitamente `foreground` o `background` y luego contesta `go`
- En `foreground`, Codex se queda en la sesion actual, sigue iterando en primer plano y solo escribe `research-results.tsv`, `autoresearch-state.json` y lessons
- En `background`, Codex escribe `autoresearch-launch.json` y arranca automaticamente el controlador de ejecucion desacoplado
- `foreground` y `background` comparten el mismo protocolo de loop, la misma semantica de metricas y las mismas reglas de repo/scope, pero son mutuamente excluyentes para un mismo repo/run; no ejecutes ambos modos a la vez sobre los mismos artefactos del repo primario
- Si despues quieres continuar ese mismo run interactivo en el otro modo, sigue usando la misma entrada `$codex-autoresearch`; antes de continuar, la skill sincroniza internamente el estado compartido con el modo elegido, y background `start` hace automaticamente el mismo paso
- Las ejecuciones de un solo repositorio siguen siendo la opcion por defecto; en ese caso el scope declarado solo se aplica al repositorio primario que guarda los artefactos de control
- Si el experimento abarca varios repositorios, el manifiesto de lanzamiento confirmado tambien puede declarar repositorios companion, cada uno con su propio scope. El preflight del runtime revisa todos los repositorios gestionados, mientras que `research-results.tsv`, `autoresearch-state.json` y los artefactos de control siguen anclados en el repositorio primario
- En ese modelo, la columna `commit` del TSV sigue registrando solo el commit del repositorio primario; la procedencia de commits por repositorio para los companion repos queda en `autoresearch-state.json`
- Cada ciclo gestionado en `background` lanza una sesion no interactiva de `codex exec` y pasa el prompt del runtime por stdin
- `execution_policy` solo aplica a los caminos que arrancan sesiones Codex anidadas, es decir, `background` y `exec`; este skill usa `danger_full_access` por defecto
- Las solicitudes posteriores de `status`, `stop` o `resume` siguen pasando por el mismo `$codex-autoresearch`; `status/stop` solo aplican a `background`
- `Mode: exec` sigue siendo la via avanzada para CI o automatizacion totalmente especificada

Los comandos directos de control siguen disponibles para scripting o depuracion de la ejecucion:

- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo <repo>`


---

## Modelo de seguridad

| Preocupacion | Como se maneja |
|--------------|----------------|
| Directorio de trabajo sucio | La verificacion previa del runtime bloquea el arranque o el relanzamiento hasta limpiar o aislar los cambios fuera del alcance definido |
| Cambio fallido | Usa la estrategia de rollback aprobada antes del arranque: `git reset --hard HEAD~1` solo en una rama/worktree experimental aislada y aprobada; en caso contrario usa `git revert --no-edit HEAD`; el registro de resultados sigue siendo la pista de auditoria |
| Fallo de Guard | Hasta 2 intentos de reajuste, luego revierte |
| Error de sintaxis | Reparacion inmediata, no cuenta como iteracion |
| Crash en tiempo de ejecucion | Hasta 3 intentos de reparacion, luego salta |
| Agotamiento de recursos | Revierte, intenta una variante mas pequena |
| Proceso colgado | Termina tras timeout, revierte |
| Atascado (3+ descartes) | Estrategia REFINE; 5+ descartes -> PIVOT a nuevo enfoque; escalamiento a busqueda web si es necesario |
| Ambiguedad durante el bucle | Aplica mejores practicas de forma autonoma; nunca se detiene a preguntar al usuario |
| Efectos secundarios externos | El modo `ship` requiere confirmacion explicita durante el asistente de pre-lanzamiento |
| Limites del entorno | Se detectan al inicio; las hipotesis inviables se filtran automaticamente |
| Sesion interrumpida | Reanudacion desde el ultimo estado consistente en la siguiente invocacion |
| Deriva del contexto (ejecuciones largas) | Verificacion de huella del protocolo cada 10 iteraciones; aumentar la frecuencia tras compaction; releer desde disco en caso de fallo |

---

## Estructura del proyecto

```
codex-autoresearch/
  SKILL.md                          # punto de entrada del skill (cargado por Codex)
  README.md                         # documentacion en ingles
  CONTRIBUTING.md                   # guia de contribucion
  LICENSE                           # MIT
  agents/
    openai.yaml                     # metadatos de Codex UI
  image/
    banner.png                      # banner del proyecto
  docs/
    INSTALL.md                      # guia de instalacion
    GUIDE.md                        # manual de operacion
    EXAMPLES.md                     # recetas por dominio
    i18n/
      README_ZH.md                  # chino
      README_JA.md                  # japones
      README_KO.md                  # coreano
      README_FR.md                  # frances
      README_DE.md                  # aleman
      README_ES.md                  # este archivo
      README_PT.md                  # portugues
      README_RU.md                  # ruso
  scripts/
    validate_skill_structure.sh     # structure validator
    autoresearch_helpers.py         # utilidades compartidas para TSV / JSON / runtime
    autoresearch_launch_gate.py     # decide fresh / resumable / needs_human antes del inicio
    autoresearch_resume_prompt.py   # construye el prompt gestionado por runtime desde la configuracion guardada
    autoresearch_runtime_ctl.py     # controla launch / create-launch / start / status / stop del runtime
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
    core-principles.md              # principios universales
    autonomous-loop-protocol.md     # especificacion del protocolo de bucle
    plan-workflow.md                # especificacion del modo plan
    debug-workflow.md               # especificacion del modo debug
    fix-workflow.md                 # especificacion del modo fix
    security-workflow.md            # especificacion del modo security
    ship-workflow.md                # especificacion del modo ship
    exec-workflow.md                # especificacion del modo CI/CD no interactivo
    interaction-wizard.md           # contrato de configuracion interactiva
    structured-output-spec.md       # especificacion de formato de salida
    modes.md                        # indice de modos
    results-logging.md              # especificacion de formato TSV
    lessons-protocol.md             # aprendizaje entre ejecuciones
    pivot-protocol.md               # recuperacion inteligente de bloqueos (PIVOT/REFINE)
    web-search-protocol.md          # busqueda web cuando esta atascado
    environment-awareness.md        # deteccion de hardware/recursos
    parallel-experiments-protocol.md # pruebas paralelas con subagentes
    session-resume-protocol.md      # reanudar ejecuciones interrumpidas
    health-check-protocol.md        # automonitoreo
    hypothesis-perspectives.md      # razonamiento de hipotesis multi-perspectiva
```

---

## FAQ

**Como elijo una metrica?** Usa `Mode: plan`. Analiza tu codigo y sugiere una.

**Funciona con cualquier lenguaje?** Si. El protocolo es agnostico al lenguaje. Solo el comando de verificacion es especifico del dominio.

**Como lo detengo?** Interrumpe Codex, o configura `Iterations: N`. El estado de git siempre es consistente porque los commits ocurren antes de la verificacion.

**El modo security modifica mi codigo?** No. Analisis de solo lectura. Dile a Codex "tambien repara los hallazgos criticos" durante la configuracion para optar por la remediacion.

**Cuantas iteraciones?** Depende de la tarea. 5 para correcciones dirigidas, 10-20 para exploracion, ilimitadas para ejecuciones nocturnas.

**Aprende entre ejecuciones?** Si. Las lecciones se extraen despues de cada `keep`, despues de cada `pivot` y al terminar la ejecucion gestionada cuando no existe una leccion reciente. El archivo de lecciones persiste entre sesiones; `exec` solo lee las lecciones existentes.

**Puede reanudar despues de una interrupcion?** Si. `foreground` reanuda con `research-results.tsv` y `autoresearch-state.json`; `background` necesita ademas `autoresearch-launch.json`. Si falta el estado de lanzamiento confirmado, inicia una nueva ejecucion `background` mediante el flujo normal de lanzamiento.

**Puede buscar en la web?** Si, cuando esta atascado despues de multiples cambios de estrategia. Los resultados de la busqueda web se tratan como hipotesis y se verifican mecanicamente.

**Como lo uso en CI?** Usa `Mode: exec` o `codex exec`. En entornos de automatizacion controlados conviene usar `codex exec --dangerously-bypass-approvals-and-sandbox ...` para igualar la politica predeterminada del runtime. Toda la configuracion se proporciona por adelantado, la salida es JSON y los codigos de salida indican exito/fallo.

**Puede probar multiples ideas a la vez?** Si. Activa los experimentos paralelos durante la configuracion. Usa worktrees de git para probar hasta 3 hipotesis simultaneamente.

---

## Agradecimientos

Este proyecto se basa en las ideas de [autoresearch de Karpathy](https://github.com/karpathy/autoresearch). La plataforma de skills de Codex es de [OpenAI](https://openai.com).

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

## Licencia

MIT -- ver [LICENSE](../../LICENSE).
