PAUTA (rodada 1): Emenda 2 do pre-registro 1-vs-N — campos aditivos de resiliencia
do CLI no registro Run (docs/prereg/2026-08-28-emenda-2.md).

CONTEXTO FATUAL (verificado no repo):

- Texto-base congelado: docs/prereg/2026-08-27-experimento-1vsN.md (tag prereg-1vsN,
  8b82214), com a Emenda 1 (itens 1-12) ja incorporada. O §7 congela o schema do
  registro Run para o experimento; a §11 permite emenda nomeada. O piloto AINDA NAO
  COMECOU. A emenda foi selada ANTES do piloto precisamente para nao reabrir decisao
  metodologica: campos declarados antes do piloto preservam o congelamento.
- Emenda 2 (SELADA, ato do operador 28/08 16:01) declara DOIS campos aditivos ao Run:
  1. resumed_from: string | None — sha256 do parcial (<...>-partial.json) que originou
     o registro por retomada; o registro novo REFERENCIA o parcial, que nunca e mutado
     nem removido. None/ausente = execucao integral (leitura retroativa: registros
     existentes permanecem validos).
  2. stage2_mode: "full" | "lite" — estagio 2 em subconjunto orcavel (deliberacao nao
     plena). Ausente = "full" (leitura retroativa: registros pre-existentes sao de
     deliberacao plena).
- Origem: plano de resiliencia do CLI (docs/plans/2026-08-28-cli-resiliencia.md,
  aprovado com revisao adversarial Momus OKAY em 28/08), implementado no epico #47,
  CONCLUIDO: council ask --resume de parcial por composicao (sintese-only, guards
  fail-closed nomeados incluindo config_drift via producer.config_sha256), help/README
  de execucao desanexada, --rank-lite (avaliadores = primeiros max(2, n//2) NA ORDEM DA
  CONFIG, warning nomeado no registro), auditor classificado em dois blocos. Handoff:
  docs/handoffs/issue-47.md.
- A emenda NAO altera prompts, roster, perfis, rubricas, manifest, endpoint nem regras
  de engenharia. Nenhum registro existente em runs/ e reescrito.

DECISOES JA ASSENTADAS PELO OPERADOR (sessao grill 26/08, docs/grill/sessao-fase2.md):

- Multi-rodada = composicao de runs/bundles imutaveis por hash (nada stateful); schema
  aditivo; fast-path mantem proveniencia + rotulo de "deliberacao nao plena".
- Emenda 1, itens 5/6: interrupcao de infraestrutura permite re-execucao; toda
  tentativa iniciada permanece em runs/, inclusive parciais; a retomada produz registro
  novo que referencia o parcial por sha e preserva o arquivo original.
- Experimento 1-vs-N: unidade = defeito/requisito verificavel por registro; endpoint =
  correcao de defeito pre-registrado + atribuivel a informacao da deliberacao + ausencia
  de dano compensatorio; rubrica pre-selada escrita pelo operador, cega ao braco;
  teto 3 rodadas, parada por estabilidade; corpus do piloto usa os registros reais.

PERGUNTA AO CONSELHO: interrogando a Emenda 2 como seladora de schema do experimento,
quais questoes dentro dela sao do OPERADOR e fariam o experimento 1-vs-N nascer torto
se respondidas errado AGORA, antes do piloto comecar? Eixos candidados (nao exaustivos,
nao precisam ser seguidos): semantica do resumed_from como garantia de proveniencia (o
que exatamente o sha do parcial certifica, e o que NAO certifica); stage2_mode=lite e a
validade comparativa entre bracos do experimento (pode registro lite entrar no corpus
de comparacao full vs lite?); leitura retroativa ausente=default versus campo explicito;
interacao resume x experimento (registro retomado pode entrar no corpus do piloto?);
custo/limites do modo lite como decisao metodologica versus decisao de produto.
