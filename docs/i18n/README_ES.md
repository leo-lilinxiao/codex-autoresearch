<p align="center">
  <img src="../../image/banner.png" width="700" alt="Codex Autoresearch">
</p>

<h2 align="center"><b>Apuntar. Iterar. Llegar.</b></h2>

<p align="center">
  <i>Experimentación autónoma orientada a objetivos para Codex.</i>
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

---

La idea: dile a Codex qué quieres mejorar y vete. Modifica tu código, verifica el resultado, conserva o descarta, y repite. Vuelves a un registro de experimentos y un código mejor.

Inspirado en [autoresearch de Karpathy](https://github.com/karpathy/autoresearch), generalizado más allá de ML a todo lo que se pueda verificar mecánicamente: cobertura de tests, errores de tipos, latencia, advertencias de lint, hallazgos de seguridad, preparación de releases — si un comando puede determinar si mejoró, el bucle puede iterar sobre ello.

## Inicio rápido

```text
# Instalar en Codex (recomendado)
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

Reinicia Codex, abre tu proyecto y adelante:

```
Tú:    $codex-autoresearch
       Quiero eliminar todos los tipos `any` de mi código TypeScript

Codex: Encontré 47 ocurrencias de `any` en src/**/*.ts.
       Directorio Results: ./autoresearch-results/
       Métrica: cantidad de `any` (actual: 47), dirección: menor
       Verificación: conteo grep + tsc --noEmit como guard
       Modo de ejecución: ¿foreground o background?

Tú:    Background, go. Déjalo corriendo toda la noche.

Codex: Iniciando ejecución en segundo plano — línea base: 47. Iterando.
```

Cada mejora se acumula. Cada fallo se revierte. Todo queda registrado.

Opciones de copia manual, symlink y alcance de usuario en [INSTALL.md](../INSTALL.md). Manual completo en [GUIDE.md](../GUIDE.md).

## Cómo funciona

```
Dices una frase  →  Codex analiza y confirma  →  Dices "go"
                                                      |
                                       +--------------+--------------+
                                       |                             |
                                  foreground                    background
                                (sesión actual)             (separado, toda la noche)
                                       |                             |
                                       +--------------+--------------+
                                                      |
                                                      v
                                            +-------------------+
                                            |    El bucle       |
                                            |                   |
                                            |  modificar algo   |
                                            |  git commit       |
                                            |  ejecutar verify  |
                                            |  ¿mejoró? guardar |
                                            |  ¿empeoró? revert |
                                            |  registrar result.|
                                            |  repetir          |
                                            +-------------------+
```

Eso es todo. Eliges uno: foreground mantiene el bucle en tu sesión actual, background lo delega a un proceso separado para que puedas dormir. El mismo bucle en ambos casos, pero no se ejecutan a la vez.

## Lo que dices vs lo que pasa

| Lo que dices | Lo que pasa |
|-------------|-------------|
| «Mejora mi cobertura de tests» | Itera hasta alcanzar el objetivo o ser interrumpido |
| «Arregla los 12 tests que fallan» | Repara uno por uno hasta que no quede ninguno |
| «¿Por qué la API devuelve 503?» | Rastrea la causa raíz con hipótesis falsificables |
| «¿Es seguro este código?» | Auditoría STRIDE + OWASP, cada hallazgo respaldado con código |
| «Listo para desplegar» | Verifica preparación, genera checklist, controla el lanzamiento |
| «Quiero optimizar pero no sé qué» | Analiza el repo, sugiere métricas, genera configuración |

Tras bambalinas, Codex mapea tu frase a uno de 7 modos (loop, plan, debug, fix, security, ship, exec). Nunca necesitas elegir uno.

## Lo que Codex deduce automáticamente

No escribes configuración. Codex infiere todo a partir de tu frase y tu repositorio:

| Lo que necesita | Cómo lo obtiene | Ejemplo |
|----------------|-----------------|---------|
| Objetivo | Tu frase | «eliminar todos los tipos any» |
| Alcance | Escanea la estructura del repo | `src/**/*.ts` |
| Métrica | Propone según objetivo + herramientas | cantidad de any (actual: 47) |
| Dirección | Infiere de «mejorar» / «reducir» / «eliminar» | menor |
| Verificación | Asocia con las herramientas del repo | conteo `grep` + `tsc --noEmit` |
| Guard | Sugiere si existe riesgo de regresión | `npm test` |

Antes de empezar, Codex siempre muestra lo que encontró y pide confirmación. Luego eliges foreground o background y dices «go».
Por defecto, el directorio Results se queda en el contexto de arranque: si iniciaste Codex dentro de un repo git, la raíz de ese repo es el workspace root por defecto; si lo iniciaste fuera de un repo git, el directorio actual de arranque es el workspace root por defecto. Codex no debería ampliarlo silenciosamente a un directorio padre salvo que confirmes explícitamente un workspace multi-repo más amplio. El resumen de confirmación siempre debería mostrar el directorio Results elegido antes de lanzar.

## Cuando se atasca

En lugar de reintentar a ciegas, el bucle escala:

| Disparador | Acción |
|-----------|--------|
| 3 fallos consecutivos | **REFINE** — ajustar dentro de la estrategia actual |
| 5 fallos consecutivos | **PIVOT** — probar un enfoque fundamentalmente diferente |
| 2 PIVOTs sin progreso | **Búsqueda web** — buscar soluciones externas |
| 3 PIVOTs sin progreso | **Detener** — informar que se necesita intervención humana |

Un solo éxito reinicia todos los contadores.

## Registro de resultados

Cada iteración se registra en `autoresearch-results/results.tsv`:

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module
2          -        49      +8      discard   generic wrapper introduced new anys
3          d4e5f6g  38      -3      keep      type-narrow API response handlers
```

Los experimentos fallidos se revierten en git pero permanecen en el registro. El registro es la verdadera pista de auditoría, mientras que `autoresearch-results/state.json` es la instantánea de reanudación.

## Más funcionalidades

Detalles completos en [GUIDE.md](../GUIDE.md):

- **Aprendizaje entre ejecuciones** — las lecciones de ejecuciones pasadas orientan la generación futura de hipótesis
- **Experimentos paralelos** — prueba hasta 3 hipótesis simultáneamente mediante git worktrees
- **Reanudación de sesión** — las ejecuciones interrumpidas continúan desde el último estado consistente
- **Modo CI/CD** (`exec`) — no interactivo, salida JSON, para pipelines de automatización
- **Verificación de doble puerta** — verify (¿mejoró?) y guard (¿se rompió algo?) separados
- **Session hooks** — instalados automáticamente; mantienen a Codex en curso entre sesiones

## FAQ

**Solo hace cambios pequeños. ¿Puede intentar ideas más grandes?**
Por defecto el bucle favorece pasos pequeños y verificables — es intencional. Pero puede ir más grande: describe una hipótesis más amplia en tu prompt (ej: "reemplaza el mecanismo de attention por linear attention y ejecuta la evaluación completa"), y lo tratará como un solo experimento a verificar. El mejor uso: el humano define la dirección de investigación, el agente se encarga de la ejecución y análisis intensivos.

**¿Es más para optimización de ingeniería o para investigación?**
Es más fuerte cuando el objetivo y la métrica están claros — subir cobertura, reducir errores, bajar latencia. Si la dirección de investigación es incierta, usa primero el modo `plan` para explorar, luego cambia a `loop` cuando sepas qué medir. Piénsalo como colaboración humano-IA: tú aportas el criterio, el agente aporta la velocidad de iteración.

**¿Cómo lo detengo?** Foreground: interrumpe Codex. Background: `$codex-autoresearch` y pide que se detenga.

**¿Puede reanudar tras una interrupción?** Sí. Reanuda automáticamente desde `autoresearch-results/state.json`.

**¿Cómo lo uso en CI?** `Mode: exec` con `codex exec`. Toda la configuración por adelantado, salida JSON, códigos de salida 0/1/2.

## Documentación

| Doc | Contenido |
|-----|-----------|
| [INSTALL.md](../INSTALL.md) | Todos los métodos de instalación, rutas de descubrimiento de skills, configuración de hooks |
| [GUIDE.md](../GUIDE.md) | Manual completo: modos, campos de configuración, modelo de seguridad, uso avanzado |
| [EXAMPLES.md](../EXAMPLES.md) | Recetas por dominio: cobertura, rendimiento, tipos, seguridad, etc. |

## Agradecimientos

Construido sobre ideas de [autoresearch de Karpathy](https://github.com/karpathy/autoresearch). La plataforma Codex skills es de [OpenAI](https://openai.com).

## Star History

<a href="https://www.star-history.com/?repos=leo-lilinxiao%2Fcodex-autoresearch&type=timeline&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
 </picture>
</a>

## Licencia

MIT — ver [LICENSE](../../LICENSE).
