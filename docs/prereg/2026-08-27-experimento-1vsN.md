# Pré-registro — Experimento 1-vs-N de rodadas (abertura da Fase 2)

Selado em 27/08/2026 pelo operador (autorização: "pode congelar o contrato do
experimento", 27/08). Este commit e a tag `prereg-1vsN` são o selo. A partir daqui
o contrato está congelado: mudança só por emenda nomeada (seção 11).

Origem: sessões de grill r1/r2 (`docs/grill/sessao-fase2.md`,
`docs/grill/bundle-fase2-r2.md`), deliberação `e099e70ae96d` e a decisão do
operador sobre a dissidência do claude de 27/08 6:20 (Apêndice A, verbatim).

## 1. Status e hipótese

- Piloto exploratório / decisão de engenharia. n=3, direcional, sem falsa precisão.
- Hipótese de falha: a rodada única deixa questões load-bearing incontestadas por
  isolamento da própria rodada; múltiplas rodadas com revisão estruturada expõem
  essas questões.
- Este experimento é a PRIMEIRA issue da Fase 2. Nenhum código de rodadas antes
  deste selo; depois do selo, o código vem DESTE contrato.
- A proposta vencedora da `e099e70` (glm) prevalece na forma, com os reparos da
  dissidência dobrados dentro dos artefatos abaixo.

## 2. Artefato 1 — Desenho

- Braços: 1 rodada vs N rodadas (composição de runs/bundles imutáveis por hash,
  com revisão estruturada entre rodadas). Tudo constante entre braços; só varia o
  número de rodadas.
- Teto 3 rodadas; parada por estabilidade — estabilidade ≠ correção.
- Sem retry no piloto (conformidade já é dado).

## 3. Artefato 2 — Denominador (congelado)

- Corpus: `74f19a4aa888`, `e5957637d9ae`, mais registros novos produzidos pelo
  schema pós-C5.
- EXCLUÍDO por decisão do operador: `6656b23a66c7` (circularidade — produzido sob
  as decisões que o experimento testa).
- Parciais (`*-partial.json`) jamais entram no denominador; execução interrompida
  não conta como terminada (C1). Só registro final conta.

## 4. Artefato 3 — Taxonomia de falhas (fechada antes do código)

1. Premissa não questionada.
2. Erro endossado.
3. Alternativa ausente.
4. Consenso por conformidade.

Achado novo = exploratório, não vitória retrospectiva.

## 5. Artefato 4 — Endpoint, rubrica e regra de engenharia

Endpoint: correção de defeito pré-registrado + atribuível à informação da
deliberação + ausência de dano compensatório.

Adjudicação: estrutural por regra mecânica; substância pela rubrica pré-selada do
operador, cega ao braço; LLM do run não é juiz.

Rubrica (aplicada sobre itens normalizados, seção 6):

- **correção atribuível**: defeito do corpus corrigido E a correção depende de
  informação que só existe na deliberação (não recuperável do bundle/run_refs
  sozinhos);
- **dano compensatório**: regressão, falso consenso introduzido, ou correção que
  cria novo defeito pré-registrável;
- **falha de conformidade**: item inválido ou ilegível — texto preservado, erro
  classificado, posição anterior persiste operacionalmente, conta no denominador;
  nunca descartado em silêncio;
- **neutro**: item que nenhum braço captura.

Regra de engenharia (n=3, direcional):

- ≥1 correção atribuível sem dano = seguir para o corte seguinte;
- 0/3, ou qualquer falso consenso introduzido = restringir a perfis e reavaliar;
- **INCONCLUSIVO** (decisão do operador, 27/08 6:20): falha de conformidade que
  consuma 1/3 do denominador, ou resultado dentro do ruído esperado (nenhuma
  correção atribuível E nenhum dano compensatório) = repetir o piloto uma vez sem
  contar a rodada anterior, antes de qualquer decisão de restrição.

## 6. Protocolo de normalização e teste de vazamento (decisão do operador)

- Normalização: extrair apenas os itens verificáveis do registro — defeito,
  endosso, evidência, gatilho — em formato único, sem metadados de rodada.
- Teste de vazamento (pré-piloto, destravador): o normalizador aplicado a um par
  1-vs-3 conhecido não pode permitir identificar o braço. Se permitir, o piloto
  não roda até corrigir.

## 7. Contrato de schema (o que o `Run` grava — congelado para o experimento)

Campos do registro na data do selo (lista aditiva completa, épico #29):

- base: `question`, `seed`, `started_at`, `config_source`, `producer`, `members`,
  `stage1`, `stage2`, `consensus`, `synthesis`, `warnings`, `usage`, `elapsed_s`,
  `divided`;
- deliberação: `profile_name`, `bundle_sha256`, `run_refs`, `candidates`,
  `decision`;
- C1: `partial`, `stage_reached`, `interrupted`, `interruption_reason`;
- C2: `usage_by_stage` (stage1/stage2/synthesis/total) e `usage`/`latency_s` por
  cédula;
- C3: `decision_aliases` (rótulo cego → id real);
- C4/C5: nenhum campo novo (C4 muda o conteúdo de `candidates[].text` em perfis
  `proposal`; C5 é tooling de leitura).

Convenções de leitura: `usage_by_stage == {}` identifica registro pré-C2 (custo do
estágio 2 não recuperável); cédula com `usage` `None` é chamada que não houve.
Proveniência sela tudo: selo de produtor (código/config/commit) e bundle com
sha256; `runs/` jamais reescrito; campos novos apenas aditivos. Mudança de schema
antes do fim do experimento = emenda nomeada (seção 11).

## 8. Regra de nomeação do roster (advisory da #33, adotada por decisão do operador)

É proibido nome de membro, provider, token de modelo (split `[-/._]`, ≥3 chars) ou
`identity_terms` de config colidindo com os tokens estruturais:

`proposal | titulo | corpo | questions | perguntas | proposta`

Motivo (evidência): o cegamento mascara o texto ANTES da destilação
(`engine.py:415-427`, `ranking.py:213`); colisão destrói o bloco estrutural e
exclui o candidato com aviso nomeado (probe de 27/08). O roster atual (gpt,
deepseek, claude, glm) não colide.

## 9. Vinculações herdadas do grill r2 (valem para o código do experimento)

- Revisão = registro estruturado: anterior → nova/manutenção explícita, natureza,
  gatilho (peer/artefato/evidência/interno — interno não conta como efeito
  causal), justificativa, round, proveniência.
- Multi-rodada = composição de runs/bundles imutáveis por hash; nada stateful.
- Revisões sempre acrescentam; posições abandonadas reconstruíveis.
- Clustering = diagnóstico sobre endossos por id; nunca regra de decisão.
- Moderador sintetiza/rotula/registra; nunca exclui, desempata ou sobreponhe.
- Fast-path mantém proveniência + rótulo de "deliberação não plena"; pares são
  entrada não-confiável; "evidência insuficiente" é resultado válido.
- Sanitização: contenção estrutural; original preservado segregado ANTES de
  sanitizar; versão/motivo de cada redação vinculados; falha = continuar marcado.

## 10. Leitura registrada como hipótese (não fato)

A "fronteira vazia na 2ª rodada de grill" lê-se como hipótese de saturação; o modo
"consenso por conformidade" não foi excluído (decisão do operador sobre a
dissidência `e099e70`, Candidato B).

## 11. Emendas

Nenhuma. Emenda = entrada nova nesta seção com data, texto-base (commit do
pré-registro que emenda), motivo e ato nomeado do operador.

---

## Apêndice A — Decisão do operador sobre a dissidência `e099e70` (verbatim, 27/08 6:20)

> Decisão do operador sobre a dissidência e099e70 (claude, Candidato B) — aceita em 27/08 6:20
>
> 1. Denominador: o corpus do experimento exclui 6656b23a66c7 (circularidade: produzido sob as decisões que o experimento testa). Corpus congelado: 74f19a4aa888, e5957637d9ae + registros novos pós-schema.
> 2. Cegueira da rubrica: a adjudicação usa protocolo de normalização (extrair apenas os itens verificáveis do registro — defeito, endosso, evidência, gatilho — em formato único, sem metadados de rodada) e um teste de vazamento pré-piloto: o normalizador aplicado a um par 1-vs-3 conhecido não pode permitir identificar o braço; se identificar, o piloto não roda até corrigir.
> 3. Regra de engenharia: acrescentado o ramo inconclusivo — "qualquer falha de conformidade que consuma 1/3 do denominador, ou resultado dentro do ruído esperado (nenhuma correção atribuível E nenhum dano compensatório) = inconclusivo: repetir o piloto uma vez sem contar a rodada anterior, antes de qualquer decisão de restrição".
> 4. Bundle da r2: a leitura de "fronteira vazia" como saturação fica registrada como hipótese, não fato (o modo "consenso por conformidade" não foi excluído).
>
> A proposta vencedora (glm) prevalece na forma: a primeira issue da Fase 2 continua sendo o experimento 1-vs-N pré-registrado — agora com estes reparos dobrados dentro dos quatro artefatos.
