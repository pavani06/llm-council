# Loop de execução do épico #1 — Runbook

**Tracker/autorização:** issue #18 (label `loop`). **Escopo:** issues #4 a #12. **Não delegadas:** #13, #14, #15. O bootstrap de sessão fria está no `AGENTS.md`; este runbook governa o modo em lote.

## 1. Objetivo

Executar a cadeia principal restante do épico #1 em segmentos, com gates delegados e paradas cirúrgicas, de forma que uma sessão fria (zero contexto) conduza o loop lendo apenas artefatos persistidos.

## 2. Etapa 0 (opcional, recomendada): CI mínimo

- [ ] `.github/workflows/tests.yml`: `on: [push, pull_request]`; ubuntu-latest; setup-python 3.12+; step `python3 test_offline.py`.
- As checagens que exigem o SDK anthropic são puladas com aviso pelo desenho do próprio teste (ele roda no python do sistema); o CI valida o restante das 177+ checagens.
- Verde no master = gate mecânico ganho de graça em todos os PRs seguintes. Sem ele, o Oracle é o único revisor independente do loop.

## 3. Disciplina de seleção e execução

1. **Pick:** menor número ABERTO do épico #1 com todos os blockers CLOSED. Conferir blockers via `gh issue view` + grafo do épico, nunca por memória.
2. **Serial:** uma issue em voo por vez. Após cada merge: `git pull origin master`, suite exit 0, só então pick da próxima.
3. **Ciclo por issue:** o mesmo do relay individual (diretiva → issue-start → implementar → suite → issue-review com Oracle → ship it → issue-finish + handoff no PR). Nada do ciclo é dispensado no modo lote; o que muda é quem assina os gates (ver §4).
4. **Budget:** nunca iniciar uma issue nova se a sessão não tem fôlego para terminá-la. Fim de sessão = parar em fronteira de issue (nunca no meio), comentar estado na #18.

## 4. Segmentos e gates

| Segmento | Issues | Gates delegados por issue | Fim de segmento |
|---|---|---|---|
| 0 (opcional) | CI mínimo | nenhum (operador) | CI verde no master |
| 1 | #4, #5, #6 | diretiva fiel ao plano/épico + ship it pós-PASS | PARADA 1: relatório na #18, aguardar operador |
| 2a | #7 | idem | PARADA 2: relatório, aguardar |
| 2b | #8 | idem, com diretiva estrita (maior risco do épico) | PARADA 3: relatório, aguardar |
| 3 | #9, #10, #11, #12 | idem | PARADA FINAL: relatório, fechar a #18 |

O operador lança UM segmento por vez com a frase de lançamento (§7). "Continua" após uma parada = novo lançamento nomeando o próximo segmento.

## 5. Condições de parada IMEDIATA

1. Divergência handoff↔plano (sobe ao operador, nunca absorvida em silêncio).
2. Review FAIL após **2 rodadas** de correção na mesma issue (espelha a regra dos 3 erros;Oracle com histórico de 4 passadas — depois de 2 rodadas sem PASS, o problema é de desenho, não de execução).
3. Suite vermelha ou regressão das seções 1-15 (golden incluso) sem causa imediata óbvia e corrigível na hora.
4. Necessidade de sair do escopo do brief/diretiva (scope creep não se aprova sozinho).
5. Diretiva que exija divergir do plano ou do épico (emenda de plano é ato do operador).
6. Infra persistente (gh/git/rede) após retries razoáveis.
7. Fim de segmento.
8. Imediatamente antes de iniciar #8, sempre.

Em qualquer parada: comentar estado na #18 (o que parou, por quê, o que falta) e aguardar o operador.

## 6. Recuperação de crash / retomada

1. Sessão nova roda o bootstrap frio (`AGENTS.md` §Bootstrap) e lê os últimos comentários da #18 (progresso).
2. `git log origin/master` + `gh pr list` + `git worktree list` para detectar órfãos:
   - PR aberto de issue em voo → retomar do ponto (issue-review/finish).
   - Worktree com trabalho sem PR → perguntar ao operador antes de qualquer coisa.
   - Nada em voo → pick normal.
3. A regra de ouro do relay vale: estado vive no GitHub (claim, PR, handoff, label `agent:working`), nunca em memória de sessão.

## 7. Frase de lançamento (template do operador)

```
Executo o loop de execucao do epico #1 segundo o runbook (docs/plans/2026-08-25-loop-relay.md)
e a issue #18, a partir do estado atual do master, segmento <S>.
Autorizo por issue do segmento: aprovacao de diretivas fieis ao plano/epico e "ship it"
pos-review PASS. Paradas obrigatorias: condicoes 1-8 do runbook e o fim do segmento.
Nao delegadas: #13, #14, #15.
<data e hora>
```

A frase nomeia o objeto (runbook + issue + segmento) e os gates delegados; o campo de data/hora fecha o requisito de aprovação nomeada. Sem ela preenchida, é cópia do spec, não autorização.

## 8. Relatórios

Por issue (comentário na #18, uma linha):

```
#<n> <titulo-curto> — MERGED <sha12> · PR #<pr> · suite <X> checks exit 0 ·
review PASS em <k> rodada(s) · handoff docs/handoffs/issue-<n>.md · avisos: <nenhuma|lista>
```

Por segmento: bloco com as linhas das issues + fronteira resultante (o que abriu) + qualquer sinal que mereça olho humano retrospectivo.

## 9. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Erosão de gate (8+ merges sem olho humano, repo sem CI) | Etapa 0; Oracle obrigatório sem exceção; paradas segmentadas; relatórios auditáveis na #18 |
| Erro composto na cadeia #4→#6 propagando para #7+ | Golden (constraint 1) + suite verde como invariante duro por issue; parada 3; divergência sobe |
| Review sem convergência | Máx. 2 rodadas por issue, depois parada 2 |
| Scope creep aprovado pelo próprio loop | Paradas 4 e 5; diretiva fiel ao plano/épico é condição da delegação |
| Fronteira mal computada | Blockers conferidos por `gh issue view` a cada pick; serial elimina corrida |
| Handoff fraco quebrando a cadeia seguinte | Handoff ausente/incompleto já é BLOCKING no review (herança do relay) |
| Custo/cota (tokens do executor + Oracle; smoke pago) | #15 fora do loop; fim de segmento = fronteira natural de custo |

## 10. Fechamento

A #18 fecha ao fim do segmento 3 (ou quando superseded), com relatório final: issues executadas, merges, pendências (#13/#14/#15 manuais), lições para o próximo lote.
