# AGENTS.md — llm-council

Regras para qualquer agente ou operador executando trabalho neste repo.
Valem para todo trabalho aqui: o épico #1 (Fase 1 — Perfis de Deliberação) e o épico
#29 (correções de registro) estão concluídos; a Fase 2 abre pelo pré-registro selado.

## Sempre

- Teste: `.venv/bin/python test_offline.py` — exit 0 obrigatório antes de qualquer PR.
  Nenhuma checagem existente é editada, enfraquecida ou removida. CI: o workflow
  `offline` (GitHub Actions) roda a suíte a cada push/PR; a proteção de branch não o
  exige como required — registre o resultado real de `gh pr checks`, nunca finja verde.
- Commit: pt-BR minúsculo sem acento, prefixo de tema (`test:`, `docs:`, `engine:`...),
  um commit por issue (squash no merge). Nunca sem pedido explícito do operador.
- Stdlib pura: nenhuma dependência nova (SDK `anthropic` é a única, já existente).
- Falha nunca silenciosa: erro nomeado, nunca warning vago, nunca resultado inventado.
- Edição cirúrgica: só o que a issue pede; código adjacente não se "melhora".

## Constraints da Fase 1 (violou uma = issue reprovada)

1. O comportamento atual do `council ask` é intocável: prompts default byte-idênticos,
   provados pelo golden (seção 15 do teste) após cada tarefa.
2. Servidor MCP permanece sem estado de sessão; estado de rodadas vive no chamador.
3. Proveniência sela tudo: perfis entram no `config_sha256`; bundle entra com sha256.
4. Registros antigos em `runs/` jamais reescritos; campos novos são apenas aditivos.

## Rotina de execução (relay)

Detalhe completo: comentário "Rotina de bastão" no épico #1. Resumo operacional:

1. **Pré-voo**: blockers da issue todos CLOSED? Ler `docs/handoffs/issue-N.md` dos
   blockers (comece por eles, não pelo plano). Divergência handoff↔plano sobe ao
   operador — nunca absorvida em silêncio.
2. **Diretiva**: comentário na issue, formato fixo (Missão / Estado de chegada / Passos /
   Invariantes / Validação / Fora de escopo / Entrega), aprovação nomeada do operador
   antes de executar.
3. **Ciclo**: issue-start → issue-review → GATE HUMANO ("ship it" explícito) →
   issue-finish.

## Bootstrap de sessão fria (zero contexto)

O operador diz apenas `execute a #N`. Desta raiz, em ordem:

1. `git pull origin master` no repo; confirmar repo/branch default (`gh repo view`).
2. Ler este `AGENTS.md` inteiro.
3. Ler o épico #1 (grafo + comentário "Rotina de bastão") e a issue #N — verificar
   se a diretiva já está postada nos comentários.
4. Pré-voo (acima). Sem diretiva postada: escrever e PARAR para aprovação nomeada.
   Com diretiva postada e o operador citando a issue: implementar.
5. Ciclo completo (issue-start → implementar → suite exit 0 → issue-review com
   segundo agente → PARAR no "ship it" → issue-finish + cleanup).

Nada além disso é preciso: as camadas AGENTS.md → épico #1 → handoffs → diretiva
carregam todo o estado. Nenhuma sessão anterior, vault ou memória é requerida.

## Handoff obrigatório

Todo PR de código carrega `docs/handoffs/issue-N.md` (≤ 35 linhas):

```
# Handoff — issue #N (T-x)
PR #<n> · branch <nome> (código em <sha12 do commit de código>) · <data>

## O que mudou no repo
## Decisões tomadas em voo (fora do plano)
## Pegadinhas descobertas
## O que a próxima issue precisa saber
## Pendências deixadas
```

O cabeçalho só afirma o que é verdadeiro antes do merge: o handoff viaja dentro do PR,
então nunca declare "merged" nele — o estado de merge vive no PR, que é a fonte.

Handoff ausente ou incompleto = finding BLOCKING no review. A próxima issue lê este
arquivo ANTES do plano.

## Aplicabilidade por issue

- **#2-#12, #15**: ciclo completo (diretiva + handoff obrigatório). #15 (gate final):
  o PR carrega o README; o smoke pago exige aprovação explícita do operador ANTES de
  rodar (custo real de cota GLM); ao final, marcar o checklist do épico #1 e verificar
  que nenhuma das issues #2-#14 ficou aberta — se alguma ficou, parar e reportar.
- **#13, #14** (skills, artefato em `~/.agents/skills/`): sem ciclo, sem PR, sem handoff.
  Diretiva leve (missão + critérios + gate); o gate é uma sessão real do operador;
  evidência em comentário de fechamento da issue. Ainda leem os handoffs dos blockers
  (#14 lê os da #11 e #12).
- **#8** toca o core (engine, decider, selo): maior risco do épico — invariantes mais
  estritos na diretiva e review mais rigoroso (golden + seções 1-14 + 21).

## Mapa

- Plano aprovado (Momus OKAY): `docs/plans/2026-08-25-fase1-perfis-de-deliberacao.md`
  (cópia de revisão em `.omo/plans/`; canônico é o de `docs/`).
- Loop de execução em lote (issues restantes da cadeia principal): runbook
  `docs/plans/2026-08-25-loop-relay.md` + issue #18 (label `loop`). Lançamento
  exige a frase do operador que nomeia runbook + issue + segmento e os gates
  delegados (template na §7 do runbook); sem ela, é execução individual, não lote.
- Épicos concluídos: #1 (Fase 1) e #29 (correções de registro — sobrevivência do
  registro, custo por estágio, `decision_aliases`, destilação de `proposal`,
  `council cost`), com relatório final na issue #35 e handoffs
  `docs/handoffs/issue-30..34.md`.
- Épico concluído: #47 (resiliência do CLI — `--resume` de parcial por composição,
  help/README de execução desanexada, `--rank-lite`, auditor classificado em dois
  blocos), com Emenda 2 selada antes do piloto e handoff em
  `docs/handoffs/issue-47.md`.
- **Fase 2 e o selo**: o contrato do experimento 1-vs-N está congelado em
  `docs/prereg/2026-08-27-experimento-1vsN.md` (tag `prereg-1vsN`). O schema do
  registro está congelado para o experimento: qualquer mudança antes do seu fim
  exige emenda nomeada (seção 11 do pré-registro). A primeira issue da Fase 2
  nasce desse contrato.
- Épico e grafo de dependências: issue #1. Cópia local do plano pode estar atrás do
  GitHub; em dúvida, o GitHub manda.
