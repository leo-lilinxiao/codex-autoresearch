# Codex Autoresearch

[English](../../README.md) | **Português**

Um ciclo autônomo e mensurável de experimentação para Codex.

Diga ao Codex qual meta numérica deseja alcançar. Ele inspeciona o repositório, confirma o experimento, altera uma coisa, verifica, mantém melhorias, reverte falhas e repete até atingir a meta.

É adequado para falhas de teste, cobertura, erros de tipo, avisos, latência, tamanho de binário e achados de segurança reproduzíveis.

## Início rápido

Instale no Codex:

```text
$skill-installer install https://github.com/leo-lilinxiao/codex-autoresearch
```

Abra um repositório Git limpo com Full Access:

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

Depois invoque:

```text
$codex-autoresearch reduza error_count de `python3 scripts/score.py` para 0
```

Antes da primeira escrita, Codex confirma objetivo, escopo, linha de base, meta, comando de métrica, guard opcional e foreground/background.

O Codex mantém as escolhas e autorizações já fornecidas. Após iniciar, continua os experimentos sem pedir confirmação a cada iteração. Para retomar uma execução em segundo plano interrompida, basta pedir para retomar; uma nova direção é opcional.

## Ciclo

```text
examinar -> alterar uma hipótese -> commit e medição
                                       |
                          melhora + guard aprovado: manter
                          caso contrário: git revert
                                       |
                                registrar e repetir
```

Codex cuida das hipóteses e mudanças de código. O script de controle cuida dos limites Git, medição, rollback e estado.

## Foreground e Background

| | Foreground | Background |
|---|---|---|
| Execução | Tarefa Codex atual | Controller separado |
| Continuidade | Goal oficial do Codex | Um worker `codex exec` por iteração |
| Uso | Observar e orientar | Execuções longas ou noturnas |
| Controle | Pausar/retomar Goal | Status/stop/resume via `$codex-autoresearch` |

Foreground continua por meio do Goal oficial. Background não cria Goal; o controller mantém a execução. A instalação não altera a configuração do Codex.

## Resultados

Arquivos não commitados ficam em `autoresearch-results/`:

| Caminho | Finalidade |
|---|---|
| `run.json` | Configuração confirmada e imutável |
| `events.jsonl` | Histórico de estado somente por anexação |
| `logs/` | Saída completa de métricas, guards e workers |
| `runtime.json` | Estado do processo background |
| `runtime.log` | Ciclo de vida do controller |

`events.jsonl` é a única fonte de estado. Dados ausentes, corrompidos ou contraditórios causam erro explícito e nunca são reconstruídos por suposição.

## Histórico e relatório

```text
$codex-autoresearch show experiment history
$codex-autoresearch export experiment history as TSV
$codex-autoresearch generate an HTML report
```

A tabela e o relatório HTML são gerados a partir de eventos validados. O snapshot HTML fica em `autoresearch-results/report.html` e não participa do estado nem da recuperação.

## Garantias

- Uma nova execução exige uma branch Git limpa e nomeada.
- Cada execução gerencia um repositório, uma métrica e uma meta.
- Cada experimento vira commit; falhas são revertidas com `git revert`.
- Alterações fora do escopo, desvio Git, métricas inválidas, falhas de comando, timeout e erro de rollback interrompem com caminho de log.
- O estado só vira `complete` quando a métrica mantida atinge a meta.

## Requisitos

- Codex CLI atual com Skills e Goals
- Python 3.11+
- Git

Veja [Instalação](../INSTALL.md), [Guia do usuário](../GUIDE.md) e [Exemplos](../EXAMPLES.md).

Licença MIT. Inspirado no [autoresearch de Karpathy](https://github.com/karpathy/autoresearch).
