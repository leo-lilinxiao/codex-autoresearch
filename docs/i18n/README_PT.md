<p align="center">
  <img src="../../image/banner.png" width="700" alt="Codex Autoresearch">
</p>

<h2 align="center"><b>Aim. Iterate. Arrive.</b></h2>

<p align="center">
  <i>Motor de experimentacao autonoma orientada por objetivos para o Codex.</i>
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

<p align="center">
  <a href="#inicio-rapido">Inicio rapido</a> ·
  <a href="#o-que-faz">O que faz</a> ·
  <a href="#arquitetura">Arquitetura</a> ·
  <a href="#como-funciona">Modos</a> ·
  <a href="#o-que-o-codex-descobre-automaticamente">Configuracao</a> ·
  <a href="#aprendizado-entre-execucoes">Aprendizado</a> ·
  <a href="#experimentos-paralelos">Paralelo</a> ·
  <a href="../GUIDE.md">Guia de operacao</a> ·
  <a href="../EXAMPLES.md">Receitas</a>
</p>

---

## Inicio rapido

**1. Instalacao:**

```bash
git clone https://github.com/leo-lilinxiao/codex-autoresearch.git
cp -r codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

Ou use o skill installer no Codex:
```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

**2. Abra o Codex no seu projeto e diga o que voce quer fazer:**

```text
$codex-autoresearch
Quero eliminar todos os tipos `any` do meu codigo TypeScript
```

**3. O Codex escaneia, confirma e depois itera de forma autonoma:**

```
Codex: Encontrei 47 ocorrencias de `any` em src/**/*.ts.

       Confirmado:
       - Objetivo: eliminar os tipos `any` em src/**/*.ts
       - Metrica: quantidade de `any` (atual: 47), direcao: reduzir
       - Verificacao: grep + tsc --noEmit como guarda

       Preciso confirmar:
       - Modo de execucao: foreground ou background?
       - Executar ate eliminar todos, ou limitar a N iteracoes?

       Escolha um modo de execucao e depois responda "go" para comecar,
       ou me diga o que alterar.

Voce:  Background, go. Roda a noite toda.

Codex: Iniciando execucao em background -- linha de base: 47.
       O runtime desacoplado ja esta iterando.
```

As melhorias se acumulam. As falhas sao revertidas. Tudo fica registrado.

Mais opcoes de instalacao em [INSTALL.md](../INSTALL.md). Manual completo em [GUIDE.md](../GUIDE.md).

---

## O que faz

Um skill do Codex que executa um loop de "modificar-verificar-decidir" no seu codigo. Cada iteracao faz uma alteracao atomica, verifica contra uma metrica mecanica e mantem ou descarta o resultado. O progresso se acumula no git; falhas sao revertidas automaticamente. Funciona com qualquer linguagem, qualquer framework, qualquer objetivo mensuravel.

Inspirado nos principios do [autoresearch do Karpathy](https://github.com/karpathy/autoresearch), generalizado para alem de ML.

### Por que existe

O autoresearch do Karpathy provou que um loop simples -- modificar, verificar, manter ou descartar, repetir -- pode levar um treinamento de ML da linha de base a novos patamares durante a noite. codex-autoresearch generaliza esse loop para tudo em engenharia de software que tenha um numero. Cobertura de testes, erros de tipo, latencia de performance, avisos de lint -- se existe uma metrica, pode iterar de forma autonoma.

---

## Arquitetura

O diagrama abaixo mostra primeiro o fluxo de inicializacao interativo e, em seguida, o nucleo de loop compartilhado. Antes de entrar no loop, o Codex sonda o ambiente, verifica se existe uma sessao recuperavel, confirma a configuracao e exige uma escolha explicita entre `foreground` e `background`.

```
              +----------------------+
              | Sondagem de ambiente |  <-- detectar CPU/GPU/RAM/toolchains
              +----------+-----------+
                         |
              +----------v-----------+
              | Retomar sessao?      |  <-- inspecionar resultados/estado anteriores
              +----------+-----------+
                         |
              +----------v-----------+
              | Ler contexto         |  <-- escopo + licoes + estado do repo
              +----------+-----------+
                         |
              +----------v-----------+
              | Confirmacao wizard   |  <-- objetivo/metrica/verify/guard
              | + escolha do modo    |      + foreground ou background
              +----------+-----------+
                         |
               +---------+---------+
               |                   |
     +---------v--------+  +-------v---------+
     | Execucao em      |  | Execucao em     |
     | foreground       |  | background      |
     | sessao atual     |  | manifest + ctl  |
     | sem runtime files|  | runtime isolado |
     +---------+--------+  +-------+---------+
               |                   |
               +---------+---------+
                         |
              +----------v-----------+
              | Nucleo de loop       |
              | compartilhado        |
              | baseline -> change   |
              | -> verify/guard ->   |
              | keep/discard/log     |
              +----------+-----------+
                         |
              +----------v-----------+
              | Resultado supervisor |  <-- continuar / stop / needs_human
              +----------------------+
```

Foreground e background compartilham exatamente o mesmo protocolo experimental. A unica diferenca e onde o loop executa: na sessao atual do Codex para foreground, ou no controlador desacoplado para background. Ambos rodam ate serem interrompidos (sem limite) ou por exatamente N iteracoes (limitadas por `Iterations: N`).

**Pseudocodigo:**

```
PHASE 0: Sondar o ambiente e verificar se existe uma sessao recuperavel
PHASE 1: Ler contexto + arquivo de licoes
PHASE 2: Confirmar a configuracao + escolher foreground ou background

SE foreground:
  executar o loop na sessao atual do Codex
SENAO background:
  escrever autoresearch-launch.json e iniciar o runtime desacoplado

LOOP COMPARTILHADO (para sempre ou N vezes):
  1. Revisar estado atual + historico git + registro de resultados + licoes
  2. Escolher UMA hipotese (aplicar perspectivas, filtrar por ambiente)
     -- ou N hipoteses se o modo paralelo estiver ativo
  3. Fazer UMA alteracao atomica
  4. git commit (antes da verificacao)
  5. Executar verificacao mecanica + guard
  6. Melhorou -> manter (extrair licao). Piorou -> estrategia de rollback aprovada. Quebrou -> corrigir ou pular.
  7. Registrar o resultado
  8. Health check (disco, git, saude da verificacao)
  9. Se 3+ descartes -> REFINE; 5+ -> PIVOT; 2 PIVOTs -> busca web
  10. Repetir. Nunca parar. Nunca perguntar.
```

---

## Como funciona

Voce diz o que quer em uma frase. O Codex faz o resto.

Ele escaneia seu repositorio, propoe um plano, confirma com voce e depois itera de forma autonoma:

| Voce diz | O que acontece |
|---------|---------------|
| "Melhorar minha cobertura de testes" | Escaneia o repo, propoe metrica, itera ate o objetivo ou interrupcao |
| "Corrigir os 12 testes que falham" | Detecta falhas, repara um a um ate zero restantes |
| "Por que a API retorna 503?" | Rastreia a causa raiz com hipoteses falsificaveis e evidencia |
| "Esse codigo e seguro?" | Executa auditoria STRIDE + OWASP, cada achado respaldado por codigo |
| "Lancar" | Verifica preparacao, gera checklist, lancamento com portoes |
| "Quero otimizar mas nao sei o que medir" | Analisa o repo, sugere metricas, gera configuracao pronta para uso |

Nos bastidores, o Codex mapeia sua frase para um dos 7 modos especializados
(loop, plan, debug, fix, security, ship, exec). Voce nunca precisa escolher um modo --
apenas descreva seu objetivo.

---

## O que o Codex descobre automaticamente

O Codex infere tudo a partir da sua frase e do seu repositorio. Voce nunca escreve configuracao.

| O que precisa | Como obtem | Exemplo |
|--------------|-----------|---------|
| Objetivo | Sua frase | "eliminar todos os tipos any" |
| Escopo | Escaneia a estrutura do repo | descobre automaticamente src/**/*.ts |
| Metrica | Propoe com base no objetivo + ferramentas | contagem de any (atual: 47) |
| Direcao | Infere de "melhorar" / "reduzir" / "eliminar" | reduzir |
| Comando de verificacao | Identifica ferramentas do repo | contagem grep + tsc --noEmit |
| Guarda (opcional) | Sugere se existe risco de regressao | npm test |

Antes de comecar, o Codex sempre mostra o que encontrou e pede confirmacao.
Minimo uma rodada de confirmacao, ate cinco se necessario. Depois voce escolhe `foreground` ou `background` e diz "go". Em `foreground`, a iteracao continua na sessao atual; em `background`, ela e entregue ao runtime desacoplado para que voce possa se afastar.
Para execucoes realmente sem supervisao, inicie o Codex CLI com configuracoes de aprovacao / sandbox que nao interrompam `git commit` nem `git revert`. Em um repositorio descartavel ou confiavel, dar permissoes mais amplas ao Codex e a opcao mais simples.

### Verificacao de duplo portao

Dois comandos com funcoes distintas:

- **Verify** = "A metrica alvo melhorou?" (mede o progresso)
- **Guard** = "Algo mais quebrou?" (previne regressoes)

```text
Verify: pytest --cov=src --cov-report=term 2>&1 | grep TOTAL | awk '{print $NF}'   # a cobertura subiu?
Guard: npx tsc --noEmit                                                              # os tipos ainda passam?
```

Se verify passa mas guard falha, a alteracao e reajustada (ate 2 tentativas) e depois revertida. Os arquivos de Guard nunca sao modificados.

---

## Detalhes dos modos

### loop

Modo padrao. Itera em direcao a um objetivo mensuravel.

```
Voce:  Elimine todos os tipos `any` do meu codigo TypeScript

Codex: Encontrei 47 `any` em src/**/*.ts.

       Confirmado:
       - Objetivo: eliminar todos os tipos `any`
       - Metrica: quantidade de `any` (atual: 47), direcao: reduzir
       - Verificacao: grep count, Guard: tsc --noEmit

       Preciso confirmar:
       - Modo de execucao: foreground ou background?
       - Executar ate zero, ou limitar a N iteracoes?

       Escolha um modo de execucao e depois responda "go" para comecar.

Voce:  Background, go. A noite toda.

Codex: Iniciando execucao em background. Primeiro a linha de base, depois as iteracoes desacopladas.
```

### plan

Converte um objetivo vago em uma configuracao de loop validada.

```
Voce:  Quero que nossa API seja mais rapida mas nao sei por onde comecar

Codex: Escaneei o repositorio. A camada API esta em src/api/ com Express + Prisma.

       Preciso confirmar:
       - O que importa mais: latencia p95, throughput ou cold start?
       - Fazer benchmark de toda a API ou de endpoints especificos?

       Me diga sua prioridade.

Voce:  Latencia p95, o endpoint /search e o pior.
```

### debug

Caca de bugs baseada em evidencia. Cada iteracao testa uma hipotese falsificavel.

```
Voce:  Nossa API retorna 503 aleatoriamente sob carga, nao sei por que

Codex: Vejo connection pooling em src/db/pool.ts, rate limiting em src/middleware/,
       e 3 handlers assincronos sem limites de erro.

       Confirmado:
       - Sintoma: 503 intermitentes sob carga concorrente
       - Escopo: src/api/, src/db/, src/middleware/

       Preciso confirmar:
       - Quando comecou? Depois de uma mudanca especifica, ou sempre?
       - Se eu encontrar a causa, tambem corrijo?

       Me de contexto.

Voce:  Comecou depois da refatoracao do connection pool semana passada. Primeiro encontre a causa.
```

### fix

Repara erros iterativamente ate a contagem chegar a zero.

```
Voce:  pytest esta falhando, 12 testes quebrados depois da refatoracao

Codex: Vejo 12 falhas em tests/.

       Confirmado:
       - Objetivo: fazer todos os testes do pytest passarem
       - Atual: 12 falhas

       Preciso confirmar:
       - Modo de execucao: foreground ou background?
       - Tambem usar ruff como guarda para evitar introduzir problemas de lint?
       - Corrigir todos os 12, ou focar em um modulo primeiro?

       Escolha um modo de execucao e depois responda "go" para comecar.

Voce:  Foreground, go. Corrige todos e usa ruff como guarda.
```

### security

Auditoria somente leitura STRIDE + OWASP + red team. Cada achado requer evidencia em codigo.

```
Voce:  Verifique nossa API em busca de vulnerabilidades de injecao

Codex: Confirmado:
       - Escopo: src/api/ e src/middleware/ (14 arquivos)
       - Foco: injecao SQL, XSS, sanitizacao de entrada

       Preciso confirmar:
       - Apenas relatorio, ou tambem corrigir achados criticos?
       - Tambem cobrir autenticacao/controle de acesso?

       Me diga sua preferencia.

Voce:  Primeiro o relatorio, e sim cobre autenticacao tambem.
```

### ship

Verificacao de lancamento com portoes. Detecta automaticamente o que voce esta lancando (PR, deploy, release).

```
Voce:  Lancar

Codex: Detectado: PR para main com 3 commits.

       Confirmado:
       - Tipo: PR de codigo
       - Destino: branch main

       Preciso confirmar:
       - Primeiro um ensaio ou direto em producao?
       - Monitoramento pos-lancamento? (5 min / 15 min / pular)

       Me diga sua preferencia.

Voce:  Primeiro um ensaio.
```

Consulte [GUIDE.md](../GUIDE.md) para uso detalhado e opcoes avancadas de cada modo.

---

## Combinacao de modos

Os modos podem ser compostos sequencialmente:

```
plan  -->  loop              # primeiro gerar configuracao, depois executar
debug -->  fix               # primeiro encontrar bugs, depois corrigi-los
security + fix               # auditar e remediar em um so passo
```

---

## Aprendizado entre execucoes

Cada execucao iterativa, exceto `exec`, extrai licoes estruturadas -- o que funcionou, o que falhou e por que. As licoes sao armazenadas em `autoresearch-lessons.md` (sem commit, como o registro de resultados) e consultadas no inicio de execucoes futuras para direcionar a geracao de hipoteses para estrategias comprovadas e para longe de becos sem saida conhecidos. O modo `exec` pode ler licoes existentes, mas nao as cria nem as atualiza.

- Licoes positivas apos cada iteracao mantida
- Licoes estrategicas apos cada decisao PIVOT
- Licoes de resumo ao completar uma execucao
- Capacidade: maximo 50 entradas, as mais antigas sao resumidas com decaimento temporal

Consulte `references/lessons-protocol.md` para detalhes.

---

## Recuperacao inteligente de travamentos

Em vez de tentar cegamente apos falhas, o loop usa um sistema de escalonamento graduado:

| Gatilho | Acao |
|---------|------|
| 3 descartes consecutivos | **REFINE** -- ajustar dentro da estrategia atual |
| 5 descartes consecutivos | **PIVOT** -- abandonar a estrategia, tentar uma abordagem fundamentalmente diferente |
| 2 PIVOTs sem melhoria | **Busca web** -- procurar solucoes externas |
| 3 PIVOTs sem melhoria | **Bloqueio suave** -- avisar e continuar com mudancas mais ousadas |

Um unico manter bem-sucedido reinicia todos os contadores. Consulte `references/pivot-protocol.md`.

---

## Experimentos paralelos

Teste multiplas hipoteses simultaneamente usando workers subagente em worktrees git isolados:

```
Orquestrador (agente principal)
  +-- Worker A (worktree-a) -> hipotese 1
  +-- Worker B (worktree-b) -> hipotese 2
  +-- Worker C (worktree-c) -> hipotese 3
```

O orquestrador escolhe o melhor resultado, faz o merge e descarta o resto. Ative os experimentos paralelos durante o assistente dizendo "sim". Se os worktrees nao forem suportados, executa em serie.

Consulte `references/parallel-experiments-protocol.md`.

---

## Retomada de sessao

Se o Codex detectar uma execucao interativa interrompida, ele pode retomar do ultimo estado consistente em vez de comecar do zero. A fonte de recuperacao principal e `autoresearch-state.json`, um snapshot de estado compacto atualizado atomicamente a cada iteracao. No modo `exec`, o estado existe apenas em um arquivo temporario sob `/tmp/codex-autoresearch-exec/...` e o fluxo `exec` deve remove-lo explicitamente antes de sair. `foreground` retoma com `research-results.tsv` e `autoresearch-state.json`; a retomada direta do controlador desacoplado em `background` continua exigindo um `autoresearch-launch.json`.

Prioridade de recuperacao para modos interativos:

1. **JSON + TSV consistentes, com manifesto de lancamento presente:** retomada imediata, assistente ignorado
2. **JSON valido, TSV inconsistente:** mini-assistente (1 rodada de confirmacao)
3. **JSON ausente ou corrompido, TSV presente:** o utilitario reconstrui o estado retido para confirmacao e depois continua com um novo manifesto de lancamento
4. **Nenhum presente:** inicio limpo (os artefatos persistentes anteriores de controle do run sao arquivados)

Veja `references/session-resume-protocol.md`.

---

## Modo CI/CD (exec)

Modo nao interativo para pipelines de automacao. Toda a configuracao e fornecida antecipadamente -- sem assistente, sempre limitado, saida JSON.

```yaml
# Exemplo de GitHub Actions
- name: Otimizacao com Autoresearch
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

Codigos de saida: 0 = melhorou, 1 = sem melhoria, 2 = bloqueio duro.

Antes de usar `codex exec` em CI, configure antecipadamente a autenticacao do CLI do Codex. Em ambientes de automacao controlados, prefira `codex exec --dangerously-bypass-approvals-and-sandbox ...` para que as execucoes `exec` independentes sigam a politica padrao `danger_full_access` do runtime gerenciado. Para execucoes programaticas, a autenticacao por API key e a opcao preferida.

Quando `Mode: exec` roda pelos helper scripts empacotados com a skill, nao renomeie manualmente os artefatos antigos na raiz do repo. `autoresearch_init_run.py --mode exec ...` ja arquiva `research-results.tsv` e `autoresearch-state.json` com os nomes canonicos `research-results.prev.tsv` e `autoresearch-state.prev.json` antes de iniciar a nova execucao.

Consulte `references/exec-workflow.md`.

---

## Registro de resultados

Cada iteracao e registrada em dois formatos complementares:

- **`research-results.tsv`** -- trilha de auditoria completa, com uma linha principal por iteracao e linhas paralelas de worker quando necessario
- **`autoresearch-state.json`** -- snapshot de estado compacto para retomada rapida de sessao em modos interativos

```
iteration  commit   metric  delta   status    description
0          a1b2c3d  47      0       baseline  initial any count
1          b2c3d4e  41      -6      keep      replace any in auth module with strict types
2          -        49      +8      discard   generic wrapper introduced new anys
3          c3d4e5f  38      -3      keep      type-narrow API response handlers
```

No modo `exec`, o snapshot de estado existe apenas em `/tmp/codex-autoresearch-exec/...` e o fluxo `exec` deve remove-lo explicitamente antes da saida. Atualize esses artefatos pelos helper scripts empacotados em `<skill-root>/scripts/...`, e nao pelo diretorio `scripts/` do repo alvo.

Ambos os arquivos nao sao commitados no git. Durante a retomada de sessao, o estado JSON e validado cruzadamente com um resumo reconstruido das iteracoes principais do TSV, e nao com a simples contagem de linhas. Resumos de progresso sao impressos a cada 5 iteracoes. Execucoes limitadas imprimem um resumo final da linha de base ao melhor resultado.

Esses artefatos de estado sao mantidos pelos helper scripts empacotados em `<skill-root>/scripts/...`, mas a maioria dos usuarios deve continuar usando apenas o unico ponto de entrada humano: **`$codex-autoresearch`**. Aqui, `<skill-root>` significa o diretorio que contem o `SKILL.md` carregado; na instalacao repo-local mais comum isso e `.agents/skills/codex-autoresearch`.

Se voce estiver automatizando ou depurando a control-plane, os helpers orientados ao repo usam `--repo <repo>` por padrao. Prefira:

- `python3 <skill-root>/scripts/autoresearch_resume_check.py --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_launch_gate.py --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo <repo>`

`--results-path`, `--state-path`, `--launch-path` e `--runtime-path` continuam disponiveis como overrides avancados. A mesma convencao repo-first tambem vale para chamadas diretas de `autoresearch_resume_prompt.py` e `autoresearch_supervisor_status.py`.

Para usuarios humanos, agora existe apenas uma entrada principal: **`$codex-autoresearch`**.

- Na primeira execucao interativa, descreva o objetivo naturalmente, responda as perguntas de confirmacao, escolha explicitamente `foreground` ou `background` e depois diga `go`
- Em `foreground`, o Codex permanece na sessao atual, continua iterando ao vivo e grava apenas `research-results.tsv`, `autoresearch-state.json` e lessons
- Em `background`, o Codex grava `autoresearch-launch.json` e inicia automaticamente o controlador de execucao desacoplado
- `foreground` e `background` compartilham o mesmo protocolo de loop, a mesma semantica de metricas e as mesmas regras de repo/scope, mas sao mutuamente exclusivos para o mesmo repo/run; nao execute os dois modos ao mesmo tempo sobre os mesmos artefatos do repositorio primario
- Se depois quiser continuar esse mesmo run interativo no outro modo, continue usando a mesma entrada `$codex-autoresearch`; antes de prosseguir, a skill sincroniza internamente o estado compartilhado com o modo escolhido, e background `start` executa automaticamente a mesma sincronizacao
- Execucoes em um unico repositorio continuam sendo o padrao; nesse caso, o scope declarado se aplica apenas ao repositorio primario que guarda os artefatos de controle
- Se o experimento abranger varios repositorios, o launch manifest confirmado tambem pode declarar companion repos, cada um com seu proprio scope. O preflight do runtime verifica todos os repositorios gerenciados, enquanto `research-results.tsv`, `autoresearch-state.json` e os artefatos de controle continuam ancorados no repositorio primario
- Nesse modelo, a coluna `commit` do TSV continua registrando apenas o commit do repositorio primario; a proveniencia de commits por repositorio para os companion repos fica em `autoresearch-state.json`
- Cada ciclo gerenciado em `background` executa uma sessao nao interativa de `codex exec`, passando o prompt do runtime via stdin
- `execution_policy` so se aplica aos caminhos que iniciam sessoes Codex aninhadas, isto e, `background` e `exec`; este skill usa `danger_full_access` por padrao
- Pedidos posteriores de `status`, `stop` ou `resume` continuam passando pelo mesmo `$codex-autoresearch`; `status/stop` so valem para `background`
- `Mode: exec` continua sendo o caminho avancado para CI ou automacao totalmente especificada

Os comandos diretos de controle continuam disponiveis para scripting ou depuracao da execucao:

- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py status --repo <repo>`
- `python3 <skill-root>/scripts/autoresearch_runtime_ctl.py stop --repo <repo>`


---

## Modelo de seguranca

| Preocupacao | Como e tratada |
|-------------|----------------|
| Diretorio de trabalho sujo | O preflight do runtime bloqueia inicio ou relancamento ate que mudancas fora da area definida sejam limpas ou isoladas |
| Alteracao com falha | Usa a estrategia de rollback aprovada antes do inicio: `git reset --hard HEAD~1` apenas em branch/worktree experimental isolado e aprovado; caso contrario usa `git revert --no-edit HEAD`; o registro de resultados continua sendo a trilha de auditoria |
| Falha do Guard | Ate 2 tentativas de reajuste, depois reverte |
| Erro de sintaxe | Correcao imediata, nao conta como iteracao |
| Crash em tempo de execucao | Ate 3 tentativas de correcao, depois pula |
| Esgotamento de recursos | Reverte, tenta uma variante menor |
| Processo travado | Encerra apos timeout, reverte |
| Preso (3+ descartes) | Estrategia REFINE; 5+ descartes -> PIVOT para nova abordagem; escalonamento para busca web se necessario |
| Ambiguidade durante o loop | Aplica melhores praticas de forma autonoma; nunca para para perguntar ao usuario |
| Efeitos colaterais externos | O modo `ship` requer confirmacao explicita durante o assistente de pre-lancamento |
| Limites do ambiente | Detectados na inicializacao; hipoteses inviaveis sao filtradas automaticamente |
| Sessao interrompida | Retomada do ultimo estado consistente na proxima invocacao |
| Deriva de contexto (execucoes longas) | Verificacao de impressao digital do protocolo a cada 10 iteracoes; aumentar a frequencia apos compaction; releitura do disco em caso de falha |

---

## Estrutura do projeto

```
codex-autoresearch/
  SKILL.md                          # ponto de entrada do skill (carregado pelo Codex)
  README.md                         # documentacao em ingles
  CONTRIBUTING.md                   # guia de contribuicao
  LICENSE                           # MIT
  agents/
    openai.yaml                     # metadados do Codex UI
  image/
    banner.png                      # banner do projeto
  docs/
    INSTALL.md                      # guia de instalacao
    GUIDE.md                        # manual de operacao
    EXAMPLES.md                     # receitas por dominio
    i18n/
      README_ZH.md                  # chines
      README_JA.md                  # japones
      README_KO.md                  # coreano
      README_FR.md                  # frances
      README_DE.md                  # alemao
      README_ES.md                  # espanhol
      README_PT.md                  # este arquivo
      README_RU.md                  # russo
  scripts/
    validate_skill_structure.sh     # structure validator
    autoresearch_helpers.py         # utilitarios compartilhados para TSV / JSON / runtime
    autoresearch_launch_gate.py     # decide fresh / resumable / needs_human antes do lancamento
    autoresearch_resume_prompt.py   # monta o prompt gerenciado pelo runtime a partir da configuracao salva
    autoresearch_runtime_ctl.py     # controla launch / create-launch / start / status / stop do runtime
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
    core-principles.md              # principios universais
    autonomous-loop-protocol.md     # especificacao do protocolo de loop
    plan-workflow.md                # especificacao do modo plan
    debug-workflow.md               # especificacao do modo debug
    fix-workflow.md                 # especificacao do modo fix
    security-workflow.md            # especificacao do modo security
    ship-workflow.md                # especificacao do modo ship
    exec-workflow.md                # especificacao do modo CI/CD nao interativo
    interaction-wizard.md           # contrato de configuracao interativa
    structured-output-spec.md       # especificacao de formato de saida
    modes.md                        # indice de modos
    results-logging.md              # especificacao de formato TSV
    lessons-protocol.md             # aprendizado entre execucoes
    pivot-protocol.md               # recuperacao inteligente de travamentos (PIVOT/REFINE)
    web-search-protocol.md          # busca web quando travado
    environment-awareness.md        # deteccao de hardware/recursos
    parallel-experiments-protocol.md # testes paralelos com subagentes
    session-resume-protocol.md      # retomar execucoes interrompidas
    health-check-protocol.md        # automonitoramento
    hypothesis-perspectives.md      # raciocinio de hipoteses multi-perspectiva
```

---

## FAQ

**Como escolho uma metrica?** Use `Mode: plan`. Ele analisa seu codigo e sugere uma.

**Funciona com qualquer linguagem?** Sim. O protocolo e agnostico a linguagem. Apenas o comando de verificacao e especifico do dominio.

**Como eu paro?** Interrompa o Codex, ou configure `Iterations: N`. O estado do git e sempre consistente porque os commits acontecem antes da verificacao.

**O modo security modifica meu codigo?** Nao. Analise somente leitura. Diga ao Codex "tambem corrija os achados criticos" durante a configuracao para optar pela remediacao.

**Quantas iteracoes?** Depende da tarefa. 5 para correcoes direcionadas, 10-20 para exploracao, ilimitadas para execucoes noturnas.

**Ele aprende entre execucoes?** Sim. As licoes sao extraidas apos cada `keep`, apos cada `pivot` e no fim da execucao gerenciada quando nao existe licao recente. O arquivo de licoes persiste entre sessoes; `exec` apenas le as licoes existentes.

**Pode retomar apos uma interrupcao?** Sim. `foreground` retoma com `research-results.tsv` e `autoresearch-state.json`; `background` precisa disso e tambem de `autoresearch-launch.json`. Se o estado de lancamento confirmado estiver ausente, inicie um novo run `background` pelo fluxo normal de lancamento.

**Pode pesquisar na web?** Sim, quando travado apos multiplas mudancas de estrategia. Os resultados da busca web sao tratados como hipoteses e verificados mecanicamente.

**Como uso no CI?** Use `Mode: exec` ou `codex exec`. Em ambientes de automacao controlados, prefira `codex exec --dangerously-bypass-approvals-and-sandbox ...` para alinhar as permissoes ao runtime padrao. Toda a configuracao e fornecida antecipadamente, a saida e JSON e os codigos de saida indicam sucesso/falha.

**Pode testar multiplas ideias ao mesmo tempo?** Sim. Ative os experimentos paralelos durante a configuracao. Usa worktrees do git para testar ate 3 hipoteses simultaneamente.

---

## Agradecimentos

Este projeto se baseia nas ideias do [autoresearch do Karpathy](https://github.com/karpathy/autoresearch). A plataforma de skills do Codex e da [OpenAI](https://openai.com).

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

## Licenca

MIT -- veja [LICENSE](../../LICENSE).
