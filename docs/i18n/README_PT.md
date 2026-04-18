<p align="center">
  <img src="../../image/banner.png" width="700" alt="Codex Autoresearch">
</p>

<h2 align="center"><b>Mirar. Iterar. Chegar.</b></h2>

<p align="center">
  <i>Experimentação autônoma orientada a objetivos para o Codex.</i>
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
  <a href="README_ES.md">🇪🇸 Español</a> ·
  <b>🇧🇷 Português</b> ·
  <a href="README_RU.md">🇷🇺 Русский</a>
</p>

---

A ideia: diga ao Codex o que você quer melhorar e vá embora. Ele modifica seu código, verifica o resultado, mantém ou descarta, e repete. Você volta para um registro de experimentos e um código melhor.

Inspirado no [autoresearch do Karpathy](https://github.com/karpathy/autoresearch), generalizado além de ML para tudo que se pode verificar mecanicamente: cobertura de testes, erros de tipo, latência, avisos de lint, achados de segurança, prontidão para release — se um comando pode dizer se melhorou, o loop pode iterar.

## Início rápido

```text
# Instalar no Codex (recomendado)
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

Reinicie o Codex, abra seu projeto e mande ver:

```
Você:  $codex-autoresearch
       Quero eliminar todos os tipos `any` do meu código TypeScript

Codex: Encontrei 47 ocorrências de `any` em src/**/*.ts.
       Diretório Results: ./autoresearch-results/
       Métrica: contagem de `any` (atual: 47), direção: menor
       Verificação: contagem grep + tsc --noEmit como guard
       Modo de execução: foreground ou background?

Você:  Background, go. Deixa rodando a noite toda.

Codex: Iniciando execução em segundo plano — baseline: 47. Iterando.
```

Cada melhoria se acumula. Cada falha é revertida. Tudo fica registrado.

Opções de cópia manual, symlink e escopo de usuário em [INSTALL.md](../INSTALL.md). Manual completo em [GUIDE.md](../GUIDE.md).

## Como funciona

```
Você diz uma frase  →  Codex analisa e confirma  →  Você diz "go"
                                                         |
                                          +--------------+--------------+
                                          |                             |
                                     foreground                    background
                                   (sessão atual)             (separado, a noite toda)
                                          |                             |
                                          +--------------+--------------+
                                                         |
                                                         v
                                               +-------------------+
                                               |    O loop         |
                                               |                   |
                                               |  modificar algo   |
                                               |  git commit       |
                                               |  executar verify  |
                                               |  melhorou? manter |
                                               |  piorou? revert   |
                                               |  registrar result.|
                                               |  repetir          |
                                               +-------------------+
```

É isso. Você escolhe um: foreground mantém o loop na sua sessão atual, background delega para um processo separado para você poder dormir. O mesmo loop nos dois casos, mas não rodam ao mesmo tempo.

## O que você diz vs o que acontece

| O que você diz | O que acontece |
|---------------|----------------|
| «Melhore minha cobertura de testes» | Itera até atingir o objetivo ou ser interrompido |
| «Corrija os 12 testes falhando» | Repara um por um até zerar |
| «Por que a API está retornando 503?» | Rastreia a causa raiz com hipóteses falsificáveis |
| «Esse código é seguro?» | Auditoria STRIDE + OWASP, cada achado com evidência no código |
| «Pronto para deploy» | Verifica prontidão, gera checklist, controla o lançamento |
| «Quero otimizar mas não sei o quê» | Analisa o repo, sugere métricas, gera configuração |

Por trás dos panos, o Codex mapeia sua frase para um dos 7 modos (loop, plan, debug, fix, security, ship, exec). Você nunca precisa escolher.

## O que o Codex deduz automaticamente

Você não escreve configuração. O Codex infere tudo a partir da sua frase e do seu repositório:

| O que ele precisa | Como obtém | Exemplo |
|-------------------|-----------|---------|
| Objetivo | Sua frase | «eliminar todos os tipos any» |
| Escopo | Escaneia a estrutura do repo | `src/**/*.ts` |
| Métrica | Propõe com base no objetivo + ferramentas | contagem de any (atual: 47) |
| Direção | Infere de «melhorar» / «reduzir» / «eliminar» | menor |
| Verificação | Associa às ferramentas do repo | contagem `grep` + `tsc --noEmit` |
| Guard | Sugere se existe risco de regressão | `npm test` |

Antes de começar, o Codex sempre mostra o que encontrou e pede confirmação. Depois você escolhe foreground ou background e diz «go».
Por padrão, o diretório Results fica no contexto de início: se você iniciou o Codex dentro de um repo git, a raiz desse repo é o workspace root padrão; se iniciou fora de um repo git, o diretório atual de início é o workspace root padrão. O Codex não deve ampliar isso silenciosamente para um diretório pai, a menos que você confirme explicitamente um workspace multi-repo mais amplo. O resumo de confirmação deve sempre mostrar o diretório Results escolhido antes do início.

## Quando trava

Em vez de tentar às cegas, o loop escala:

| Gatilho | Ação |
|---------|------|
| 3 falhas consecutivas | **REFINE** — ajustar dentro da estratégia atual |
| 5 falhas consecutivas | **PIVOT** — tentar uma abordagem fundamentalmente diferente |
| 2 PIVOTs sem progresso | **Busca web** — procurar soluções externas |
| 3 PIVOTs sem progresso | **Parar** — reportar que intervenção humana é necessária |

Um único sucesso reseta todos os contadores.

## Registro de resultados

Cada iteração é registrada em `autoresearch-results/results.tsv`:

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module
2          -        49      +8      discard   generic wrapper introduced new anys
3          d4e5f6g  38      -3      keep      type-narrow API response handlers
```

Experimentos que falharam são revertidos no git mas permanecem no registro. O registro é a verdadeira trilha de auditoria, enquanto `autoresearch-results/state.json` é o snapshot de retomada.

## Mais funcionalidades

Detalhes completos em [GUIDE.md](../GUIDE.md):

- **Aprendizado entre execuções** — lições de execuções passadas influenciam a geração futura de hipóteses
- **Experimentos paralelos** — testa até 3 hipóteses simultaneamente via git worktrees
- **Retomada de sessão** — execuções interrompidas continuam do último estado consistente
- **Modo CI/CD** (`exec`) — não interativo, saída JSON, para pipelines de automação
- **Verificação de dupla porta** — verify (melhorou?) e guard (quebrou algo?) separados
- **Session hooks** — instalados automaticamente; mantêm o Codex no rumo entre sessões

## FAQ

**Só faz mudanças pequenas. Pode tentar ideias maiores?**
Por padrão o loop favorece passos pequenos e verificáveis — isso é intencional. Mas pode ir além: descreva uma hipótese maior no seu prompt (ex: "substitua o mecanismo de attention por linear attention e rode a avaliação completa"), e ele tratará como um único experimento a verificar. O melhor uso: o humano define a direção de pesquisa, o agente faz a execução e análise intensivas.

**É mais para otimização de engenharia ou para pesquisa?**
É mais forte quando o objetivo e a métrica estão claros — subir cobertura, reduzir erros, baixar latência. Se a direção de pesquisa ainda é incerta, use primeiro o modo `plan` para explorar, depois mude para `loop` quando souber o que medir. Pense como colaboração humano-IA: você fornece o julgamento, o agente fornece a velocidade de iteração.

**Como paro?** Foreground: interrompa o Codex. Background: `$codex-autoresearch` e peça para parar.

**Consegue retomar após interrupção?** Sim. Retoma automaticamente a partir de `autoresearch-results/state.json`.

**Como uso em CI?** `Mode: exec` com `codex exec`. Toda a configuração antecipada, saída JSON, códigos de saída 0/1/2.

## Documentação

| Doc | Conteúdo |
|-----|----------|
| [INSTALL.md](../INSTALL.md) | Todos os métodos de instalação, caminhos de descoberta de skills, configuração de hooks |
| [GUIDE.md](../GUIDE.md) | Manual completo: modos, campos de configuração, modelo de segurança, uso avançado |
| [EXAMPLES.md](../EXAMPLES.md) | Receitas por domínio: cobertura, performance, tipos, segurança, etc. |

## Agradecimentos

Construído sobre ideias do [autoresearch do Karpathy](https://github.com/karpathy/autoresearch). A plataforma Codex skills é da [OpenAI](https://openai.com).

## Star History

<a href="https://www.star-history.com/?repos=leo-lilinxiao%2Fcodex-autoresearch&type=timeline&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=leo-lilinxiao/codex-autoresearch&type=timeline&legend=top-left" />
 </picture>
</a>

## Licença

MIT — veja [LICENSE](../../LICENSE).
