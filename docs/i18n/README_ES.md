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
  <a href="#modos">Modos</a> ·
  <a href="#configuracion">Configuracion</a> ·
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
       - Ejecutar hasta eliminar todos, o limitar a N iteraciones?

       Responde "go" para empezar, o dime que cambiar.

Tu:    go, que corra toda la noche.

Codex: Iniciando -- linea base: 47. Iterando hasta que interrumpas.
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

El bucle se ejecuta hasta ser interrumpido (sin limite) o exactamente N iteraciones (limitado mediante `Iterations: N`).

**Pseudocodigo:**

```
PHASE 0: Detectar entorno, verificar reanudacion de sesion
PHASE 1: Leer contexto + archivo de lecciones

LOOP (para siempre o N veces):
  1. Revisar estado actual + historial git + registro de resultados + lecciones
  2. Elegir UNA hipotesis (aplicar perspectivas, filtrar por entorno)
     -- o N hipotesis si el modo paralelo esta activo
  3. Hacer UN cambio atomico
  4. git commit (antes de la verificacion)
  5. Ejecutar verificacion mecanica + guard
  6. Mejoro -> conservar (extraer leccion). Empeoro -> git reset. Fallo -> reparar o saltar.
  7. Registrar el resultado
  8. Health check (disco, git, salud de verificacion)
  9. Si 3+ descartes -> REFINE; 5+ -> PIVOT; 2 PIVOTs -> busqueda web
  10. Repetir. Nunca parar. Nunca preguntar.
```

---

## Modos

Siete modos, un unico patron de invocacion: `$codex-autoresearch` seguido de una frase describiendo lo que quieres. Codex detecta automaticamente el modo y te guia a traves de una breve conversacion para completar la configuracion.

| Modo | Cuando usarlo | Se detiene cuando |
|------|---------------|-------------------|
| `loop` | Tienes un objetivo medible para optimizar | Interrupcion o N iteraciones |
| `plan` | Tienes un objetivo pero no la configuracion | Se genera el bloque de configuracion |
| `debug` | Necesitas analisis de causa raiz con evidencia | Todas las hipotesis probadas o N iteraciones |
| `fix` | Algo esta roto y necesita reparacion | El conteo de errores llega a cero |
| `security` | Necesitas una auditoria estructurada de vulnerabilidades | Todas las superficies de ataque cubiertas o N iteraciones |
| `ship` | Necesitas verificacion de lanzamiento con puertas | Todos los puntos de la lista aprobados |
| `exec` | Pipeline CI/CD, sin humano disponible | N iteraciones (siempre limitado), salida JSON |

**Seleccion rapida:**

```
"Quiero mejorar X"              -->  loop (o plan si no estas seguro de la metrica)
"Algo esta roto"                -->  fix  (o debug si la causa es desconocida)
"Este codigo es seguro?"        -->  security
"Listo para lanzar"             -->  ship
codex exec --skill ...          -->  exec (CI/CD, sin asistente)
```

---

## Configuracion

### Campos obligatorios (modo `loop`)

| Campo | Tipo | Ejemplo |
|-------|------|---------|
| `Goal` | Objetivo a alcanzar | `Reduce type errors to zero` |
| `Scope` | Globs de archivos a modificar | `src/**/*.ts` |
| `Metric` | Numero a rastrear | `type error count` |
| `Direction` | `higher` o `lower` | `lower` |
| `Verify` | Comando que produce la metrica | `tsc --noEmit 2>&1 \| wc -l` |

### Campos opcionales

| Campo | Valor por defecto | Proposito |
|-------|-------------------|-----------|
| `Guard` | ninguno | Comando de seguridad que siempre debe pasar (prevencion de regresiones) |
| `Iterations` | ilimitado | Limitar a N iteraciones |
| `Run tag` | automatico | Etiqueta para esta ejecucion |
| `Stop condition` | ninguno | Regla personalizada de parada anticipada |

Cuando faltan campos obligatorios, un asistente interactivo escanea tu repositorio y siempre confirma contigo antes de iniciar (hasta 5 rondas). No necesitas conocer los nombres de los campos.

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

## Guia de decision rapida

| Quieres... | Modo | Configuracion clave |
|------------|------|---------------------|
| Empujar un numero en una direccion toda la noche | `loop` | Goal + Metric + Verify |
| Averiguar que metrica rastrear | `plan` | Solo un Goal |
| Encontrar por que algo esta roto | `debug` | Scope + Symptom |
| Hacer que tests/tipos/lint pasen | `fix` | Comando Target |
| Auditar codigo en busca de vulnerabilidades | `security` | Scope + Focus |
| Lanzar con confianza | `ship` | Di "lanzar" o "primero un ensayo" |
| Ejecutar en CI/CD sin interaccion | `exec` | Todos los campos por adelantado + Iterations |

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
       - Ejecutar hasta cero, o limitar a N iteraciones?

       Responde "go" para empezar.

Tu:    go, toda la noche.
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
       - Tambien usar ruff como guardia para evitar introducir problemas de lint?
       - Reparar los 12, o enfocarse en un modulo primero?

       Responde "go" para empezar.

Tu:    Repara todos, si usa ruff como guardia. Go.
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

Cada ejecucion extrae lecciones estructuradas -- que funciono, que fallo y por que. Las lecciones se almacenan en `autoresearch-lessons.md` (sin commit, como el registro de resultados) y se consultan al inicio de ejecuciones futuras para sesgar la generacion de hipotesis hacia estrategias probadas y lejos de callejones sin salida conocidos.

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

Si Codex detecta una ejecucion anterior interrumpida (registro de resultados, archivo de lecciones, commits de experimentos), puede reanudar desde el ultimo estado consistente en lugar de empezar de cero:

- **Estado consistente:** reanudacion inmediata, se omite el asistente
- **Parcialmente consistente:** mini-asistente (1 ronda) para reconfirmar
- **Inconsistente u objetivo diferente:** inicio limpio (el registro anterior se renombra)

Consulta `references/session-resume-protocol.md`.

---

## Modo CI/CD (exec)

Modo no interactivo para pipelines de automatizacion. Toda la configuracion se proporciona por adelantado -- sin asistente, siempre limitado, salida JSON.

```yaml
# Ejemplo de GitHub Actions
- name: Optimizacion con Autoresearch
  run: codex exec --skill codex-autoresearch
         --goal "Reduce type errors" --scope "src/**/*.ts"
         --metric "type error count" --direction lower
         --verify "tsc --noEmit 2>&1 | grep -c error"
         --iterations 20
```

Codigos de salida: 0 = mejoro, 1 = sin mejora, 2 = bloqueo duro.

Consulta `references/exec-workflow.md`.

---

## Registro de resultados

Cada iteracion se registra en formato TSV (`research-results.tsv`):

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module with strict types
2          -        49      +8      discard   generic wrapper introduced new anys
3          c3d4e5f  38      -3      keep      type-narrow API response handlers
```

Se imprime un resumen de progreso cada 5 iteraciones. Las ejecuciones limitadas imprimen un resumen final de linea base a mejor valor.

---

## Modelo de seguridad

| Preocupacion | Como se maneja |
|--------------|----------------|
| Directorio de trabajo sucio | El bucle se niega a iniciar; sugiere modo `plan` o rama limpia |
| Cambio fallido | `git reset --hard HEAD~1` mantiene el historial limpio; el registro de resultados es la pista de auditoria |
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
    validate_skill_structure.sh     # script de validacion de estructura
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

**Aprende entre ejecuciones?** Si. Las lecciones se extraen despues de cada ejecucion y se consultan al inicio de la siguiente. El archivo de lecciones persiste entre sesiones.

**Puede reanudar despues de una interrupcion?** Si. En la siguiente invocacion, detecta la ejecucion anterior y reanuda desde el ultimo estado consistente.

**Puede buscar en la web?** Si, cuando esta atascado despues de multiples cambios de estrategia. Los resultados de la busqueda web se tratan como hipotesis y se verifican mecanicamente.

**Como lo uso en CI?** Usa `Mode: exec` o `codex exec`. Toda la configuracion se proporciona por adelantado, la salida es JSON y los codigos de salida indican exito/fallo.

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
