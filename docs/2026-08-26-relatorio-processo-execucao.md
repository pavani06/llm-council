# Relatório de processo: execução de uma deliberação (perfil continuation)

Insumo para melhorar a estrutura do council. Não é proposta de implementação: cada achado
traz o sintoma observado, a evidência no código e o que a decisão do operador teria de
resolver. Fonte: uma execução real de ponta a ponta nesta data, mais a execução morta que
a precedeu.

## O que foi executado

```
./bin/council deliberate "Qual e o proximo passo do plano de evolucao do llm-council (Fase 2), \
dado o entendimento assentado nas duas rodadas de grill?" \
  --profile continuation --bundle docs/grill/sessao-fase2.md \
  --ref e5957637d9ae --ref 6656b23a66c7 --json
```

| campo | valor |
|---|---|
| registro | `runs/20260826T162008+0000-e099e70ae96d.json` |
| selo | código `d0e5f9a7cbbb` · config `06928aee5039` · commit `46ce7b05f2a5` · árvore limpa |
| bundle | `ed10de3fde3f2bde` (sha256 de `docs/grill/sessao-fase2.md`) |
| run_refs | `e5957637...`, `6656b23a...` |
| resultado | `DECIDIDO \| glm \| alta`, `divided=false`, `warnings=[]` |
| relógio | 175,08 s |
| usage registrado | 20.389 tokens |

Consenso: glm 0,83 `[1,2,1]` spread 0,471 · claude 0,67 `[3,1,1]` spread 0,943 · gpt 0,33 ·
deepseek 0,17. Latências do estágio 1: gpt 8,49 s, deepseek 25,32 s, glm 41,85 s, claude
47,69 s; presidente 6,81 s.

## Linha do tempo real (as duas tentativas)

1. `doctor`: verde, 4 conselheiros, perfis listados, selo impresso. Custo zero. Serviu ao
   propósito de pré-voo sem ressalva.
2. Tentativa 1, lançada com `nohup ... &` sob um harness com teto de 120 s. Completou o
   estágio 1 inteiro (4 respostas) e 2 das 4 cédulas; o processo foi morto aos 120 s.
   **Nenhum artefato**: sem registro, sem registro parcial, sem contabilidade. Custo
   perdido: 6 chamadas, 1 delas GLM.
3. Tentativa 2, relançada dentro de `tmux` (imune ao teto do harness). Fechou em 175 s,
   `EXIT=0`, registro salvo.
4. Leitura do resultado: `council show e099e70ae96d` aceitou o prefixo de 12 e imprimiu
   consenso, cédulas e o bloco `DECISION`.

Custo total da sessão: 15 chamadas, 3 GLM, das quais 6 chamadas e 1 GLM não produziram
nada e só existem porque foram anotadas à mão aqui.

## Achados, por load-bearingness

### 1. O registro é all-or-nothing: morte do processo apaga tudo o que já foi pago

`Council.run()` acumula o `Run` em memória e só retorna no fim
([engine.py:454](../council/engine.py#L454)); `save_run` é chamado depois disso, tanto no
CLI ([cli.py:56](../council/cli.py#L56) e [cli.py:437](../council/cli.py#L437)) quanto no
servidor MCP ([mcp_server.py:129](../council/mcp_server.py#L129) e
[mcp_server.py:235](../council/mcp_server.py#L235)). Não há handler de sinal nem escrita
incremental por estágio.

Consequência observada duas vezes: a r2 do grill (registrada em
[sessao-fase2.md:3-6](grill/sessao-fase2.md)) e a tentativa 1 desta sessão. Nos dois casos
o conselho respondeu, os tokens foram cobrados e o artefato não existe.

Isso é a única forma de falha silenciosa que sobrou no sistema. O `AGENTS.md` do repo
proíbe exatamente isso ("falha nunca silenciosa: erro nomeado, nunca warning vago"), e o
engine cumpre a regra dentro da execução (provedor que cai vira aviso nomeado,
[engine.py:331](../council/engine.py#L331); truncamento idem,
[engine.py:334](../council/engine.py#L334)). A execução que morre inteira escapa da regra
porque quem escreveria o aviso morreu junto.

O peso é maior no caminho MCP: cliente de MCP tem teto de resposta muito abaixo dos 20 min
que uma rodada pode legitimamente levar, e o mesmo `save_run` no fim vale ali.

Decisão do operador: um registro parcial é registro? Se sim, ele precisa nascer marcado
(estágio alcançado, chamadas pagas, motivo da interrupção) e ficar fora de qualquer
denominador de experimento, o que toca o pré-registro da Fase 2.

### 2. O custo do estágio 2 não entra em lugar nenhum

`_total_usage` soma apenas estágio 1 e presidente
([engine.py:457-464](../council/engine.py#L457-L464)). O `Ballot` não tem campo de usage
([ranking.py:16-26](../council/ranking.py#L16-L26)) e `_rank_one` descarta `reply.usage` ao
construir a cédula ([engine.py:204-205](../council/engine.py#L204-L205)).

Confere na aritmética deste registro: 16.350 (estágio 1) + 4.039 (presidente) = 20.389,
exatamente o `usage` reportado. As 4 cédulas ficaram fora. Elas não são resíduo: o prompt
de cada cédula carrega os candidatos inteiros, o maior input da execução, e o texto cru das
quatro somou 10.895 caracteres só de saída.

Efeito prático: o número que o operador usa para orçar subconta aproximadamente metade, e
a cota que de fato importa (2 chamadas GLM por questão, declarada em
[council.toml:26-27](../council.toml)) não é derivável do registro. Toda a contabilidade de
orçamento das sessões de grill foi feita à mão.

Decisão do operador: corrigir `usage` muda o significado do campo entre registros antigos e
novos. Campo novo por estágio (aditivo, preserva a leitura antiga) ou correção do campo
existente com nota de descontinuidade?

### 3. Dois terços do relógio não são atribuíveis a ninguém

Elapsed 175,08 s. Estágio 1 é paralelo, então o teto dele é a maior latência: 47,69 s. O
presidente levou 6,81 s. Sobram cerca de 120,6 s, 69% da execução, sem latência registrada,
porque a cédula não grava `latency_s` (mesma lacuna do achado 2).

Efeito: quando uma rodada demora, não dá para dizer qual provedor a segurou, e a decisão
"aumentar o teto de quem" fica sem base. O `settings.timeout = 1200` com `retries = 2`
([council.toml:126-127](../council.toml)) admite até 60 min em uma única chamada; sem
latência por cédula, esse risco é invisível no registro.

### 4. O alias A/B/C do decisor cego morre na memória

Os rótulos são construídos na ordem do consenso
([engine.py:417-420](../council/engine.py#L417-L420)) e só a `escolha` volta traduzida para
o id real ([engine.py:448-449](../council/engine.py#L448-L449)). `dissidencias` e
`fundamentos` ficam com o texto do presidente cru.

Neste registro: `dissidencias = "Candidato B sustenta reparos adicionais de auditoria..."`.
Quem lê o JSON não tem como saber que B é o claude sem reconstruir a ordem do consenso e
ler o código que atribui as letras.

O campo `dissidencias` existe justamente para que o dissenso não seja absorvido pela
decisão. Hoje ele é o campo menos legível do registro. O mapa é derivável, então persistir
`decision_aliases` é aditivo e não reescreve nada.

### 5. O formato `proposal` não é destilado: análise e proposta entram juntas no ranking

Para `stage1_format = "questions"`, cada questão vira um candidato. Para qualquer outro
formato, o candidato é a resposta inteira
([engine.py:66-67](../council/engine.py#L66-L67)). O parser `parse_proposal`
([structured.py:115](../council/structured.py#L115)) existe, é testado, e **não é chamado
em nenhum ponto do fluxo** (única referência fora do próprio módulo está em
`test_offline.py`).

Mas o prompt pede as duas coisas: "responda com uma análise curta e termine com um bloco de
proposta" ([prompts.py:183-191](../council/prompts.py#L183-L191)). Logo o que é ranqueado
às cegas, sob os critérios do perfil (aderência à trajetória, risco, dependências,
sustentação na evidência), é um texto misto de análise e proposta.

Isso não é hipotético nesta execução. O candidato do claude abre com quatro críticas de
auditoria ao bundle e só depois propõe. Ele foi o mais disputado do painel: posições
`[3,1,1]`, spread 0,943, contra 0,471 dos outros três. Um avaliador o pôs em último e dois
em primeiro, e o registro não permite dizer se discordaram da análise ou da proposta,
porque ranquearam um texto só. O mesmo vale para a justificativa do presidente, que rejeita
citando o teor crítico ("reabrem decisões já fixadas e introduzem reexecução incompatível
com a regra de não retry") sem que se possa separar o que era análise do que era passo
proposto.

Decisão do operador: destilar `proposal` como já se destila `questions`, ou assumir por
escrito que o candidato é a resposta inteira e ajustar os critérios do perfil a isso.

### 6. Não existe pré-voo de custo, só pré-voo de configuração

`doctor` confere chaves, roster, perfis e selo. Nada estima o que a próxima execução vai
gastar, e nada acumula o gasto entre execuções. O orçamento de uma sessão vive em prosa,
no documento da sessão ([sessao-fase2.md:3-6](grill/sessao-fase2.md)), inclusive a
contabilidade da execução que morreu.

Com os achados 1 e 2 no lugar, um `council cost` derivado dos registros seria mecânico.
Sem eles, qualquer ledger nasce errado.

## O que funcionou e não deve regredir

- `doctor` como pré-voo: em uma tela, chaves, roster, perfis e o selo que um registro
  gerado agora carregaria. Foi o que autorizou gastar.
- Prefixo de sha em toda parte: `--ref e5957637d9ae` e `show e099e70ae96d` aceitaram o
  prefixo sem cerimônia.
- Encadeamento por `run_refs`: as duas rodadas de grill entraram no registro por hash, sem
  estado em lugar nenhum.
- Bundle por arquivo, selado por sha256 antes de qualquer retorno antecipado
  ([engine.py:302-308](../council/engine.py#L302-L308)): a origem sobrevive até a execuções
  que falham cedo.
- Progresso no stderr com latência e tokens por membro: foi o que permitiu saber, na
  tentativa 1, exatamente onde o processo morreu e quanto havia sido gasto.
- Cegamento e auto-exclusão observáveis no registro: `label_to_member` por cédula permite
  reconstruir o ranking de cada avaliador sem confiar na agregação.

## O acoplamento que o operador precisa resolver antes da Fase 2

Os achados 1 a 5 tocam `engine.py` e o formato do registro. O plano da Fase 2 congela o
pré-registro do experimento 1-vs-N sobre esse mesmo registro: denominador, taxonomia de
falhas e contrato de schema são definidos em cima do que o `Run` grava hoje.

Duas ordens possíveis, e a escolha é do operador:

- Corrigir antes de selar. O experimento mede um sistema que contabiliza o próprio custo,
  registra latência por cédula e nomeia execução interrompida. O preço é adiar o
  pré-registro e mexer no código que o experimento vai medir.
- Selar antes de corrigir. O pré-registro fica congelado sobre o comportamento atual, e
  qualquer correção posterior vira variável não controlada entre os braços, exatamente o
  que "tudo constante entre braços, só varia nº de rodadas" proíbe.

O achado 1 tem um agravante para essa escolha: uma execução morta no meio de um braço hoje
não deixa rastro, e "sem retry no piloto" transforma isso em caso perdido do denominador
sem registro do que foi perdido. A regra de engenharia (n=3, `≥1 correção atribuível`) não
sobrevive a um denominador que encolhe em silêncio.

O achado 5 tem outro: o corpus do experimento inclui registros produzidos com `proposal`
não destilado. Destilar depois muda o que "candidato" significa entre corpus e execução.
