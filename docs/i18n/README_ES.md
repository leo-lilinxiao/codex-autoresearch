# Codex Autoresearch

[English](../../README.md) | **Español**

Un bucle autónomo y medible de experimentación para Codex.

Indica a Codex un objetivo numérico. Codex inspecciona el repositorio, confirma el experimento, cambia una cosa, verifica, conserva las mejoras, revierte los fallos y repite hasta alcanzar el objetivo.

Sirve para fallos de pruebas, cobertura, errores de tipos, avisos, latencia, tamaño de binarios y hallazgos de seguridad reproducibles.

## Inicio rápido

Instala desde Codex:

```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

Abre un repositorio Git limpio con Full Access:

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

Después invoca:

```text
$codex-autoresearch reduce error_count de `python3 scripts/score.py` a 0
```

Antes de escribir, Codex confirma el objetivo, el alcance, la línea base, la meta, el comando de medida, el guard opcional y foreground/background.

Codex conserva las decisiones y autorizaciones que ya has dado. Tras iniciar, continúa los experimentos sin pedir confirmación en cada iteración. Para retomar una ejecución en segundo plano detenida, basta con pedir «reanudar»; una nueva dirección es opcional.

## Bucle

```text
examinar -> cambiar una hipótesis -> commit y medida
                                      |
                         mejora + guard correcto: conservar
                         si no: git revert
                                      |
                              registrar y repetir
```

Codex decide las hipótesis y modifica el código. El script de control posee los límites Git, la medida, el rollback y el estado.

## Foreground y Background

| | Foreground | Background |
|---|---|---|
| Ejecución | Tarea Codex actual | Controller separado |
| Continuidad | Goal oficial de Codex | Un worker `codex exec` por iteración |
| Uso | Observar y dirigir | Ejecuciones largas o nocturnas |
| Control | Pausa/reanudación del Goal | Status/stop/resume con `$codex-autoresearch` |

Foreground continúa mediante el Goal oficial. Background no crea un Goal; el controller mantiene la ejecución. La instalación no cambia la configuración de Codex.

## Resultados

Los archivos no confirmados viven en `autoresearch-results/`:

| Ruta | Función |
|---|---|
| `run.json` | Configuración confirmada e inmutable |
| `events.jsonl` | Historial de estado de solo anexado |
| `logs/` | Salida completa de métricas, guards y workers |
| `runtime.json` | Estado del proceso background |
| `runtime.log` | Ciclo de vida del controller |

`events.jsonl` es la única fuente del estado. Los datos ausentes, dañados o contradictorios producen un error explícito; nunca se reconstruyen por aproximación.

## Historial e informe

```text
$codex-autoresearch show experiment history
$codex-autoresearch export experiment history as TSV
$codex-autoresearch generate an HTML report
```

La tabla y el informe HTML se generan desde eventos validados. La instantánea HTML se guarda en `autoresearch-results/report.html` y no forma parte del estado ni de la recuperación.

## Garantías

- Una ejecución nueva exige una rama Git limpia y con nombre.
- Cada ejecución gestiona un repositorio, una métrica y una meta.
- Cada experimento se confirma; los fallos se revierten con `git revert`.
- Cambios fuera de alcance, deriva Git, métricas inválidas, fallos de comandos, tiempos agotados y errores de rollback detienen el proceso con una ruta de log.
- Solo se marca `complete` cuando la métrica conservada alcanza la meta.

## Requisitos

- Codex CLI actual con Skills y Goals
- Python 3.11+
- Git

Consulta [Instalación](../INSTALL.md), [Guía de usuario](../GUIDE.md) y [Ejemplos](../EXAMPLES.md).

Licencia MIT. Inspirado por [autoresearch de Karpathy](https://github.com/karpathy/autoresearch).
