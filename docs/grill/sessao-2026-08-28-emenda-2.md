# Entendimento compartilhado — Emenda 2 (campos aditivos de resiliência)
Sessão council-grill · 2026-08-28 · Pauta: `docs/prereg/2026-08-28-emenda-2.md` ·
Operador: Fernando Pavani · Rodadas: 2 (fronteira vazia na 2ª) · Orçamento aprovado:
3 rodadas / ~27 chamadas / ~6 GLM · Custo real: 18 chamadas / 4 GLM / 54.483 tok.

## Rodadas

- Rodada 1 — sha `9573a1b2664c` (24.607 tok, 435s, 9 chamadas / 2 GLM): 11 questões
  ranqueadas. Avisos do registro: árvore de trabalho suja na execução; presidente usou
  termo novo em 4 trechos (`council audit 9573a1b2664c --bundle
  docs/grill/bundle-emenda2-r1.md` para ver). Bundle: `bundle-emenda2-r1.md`.
  Tese do conselho: a Emenda 2 é aditiva no formato, mas não neutra para o experimento —
  o schema registra `stage2_mode` e `resumed_from`, mas não decide a admissibilidade
  deles no corpus; isso é decisão do operador antes da primeira execução elegível.
- Rodada 2 — sha `0b4e3f212ab9`, ref `9573a1b2664c` (29.876 tok, 446s, 9 chamadas /
  2 GLM): 5 residuais classificados. Avisos do registro: árvore de trabalho suja;
  conselho dividido no topo — "trate a síntese como uma opção, não consenso";
  presidente usou termo novo em 1 trecho (`council audit 0b4e3f212ab9 --bundle
  docs/grill/bundle-emenda2-r2.md` para ver). Veredito: só **D** (regra de seleção
  do que será retomado) é decisão do operador load-bearing; **A** é condicional
  (só vira decisão se lite virar estrato analítico); B, C e E fechados como
  engenharia/limitação. Cautela adicional: falhas e exclusões devem ser reportadas
  por braço (1 vs N), sem inventar limiar de rebaixamento agora.

## Fronteira da rodada 1 (fechada — respostas na seção "Decisões assentadas")

1. Runs `stage2_mode="lite"` no corpus primário 1-vs-N? — Rec: não; primário só `full`.
2. Quem decide `lite` e com base em quê? — Rec: política congelada anterior aos dados.
3. Runs retomadas (`resumed_from` ≠ null) na comparação primária? — Rec conservadora:
   fora do primário, só sensibilidade. (Divergência decisiva do conselho: duas políticas
   defensáveis; escolha depende de capacidade real de auditar continuação exata.)
4. Parcial + retomada = quantas observações? — Rec: uma unidade experimental, nunca duas.
5. O que o sha de `resumed_from` certifica? — Rec: só identidade/integridade dos bytes.
6. Ausência dos campos = default até quando? — Rec: só legado pré-corte declarado; runs
   do piloto gravam explícito; ausência pós-corte = falha fechada, registro inelegível.

## Residuais da rodada 2 (todos fechados)

- A: FECHADO como decisão 8 — sem intenção de estrato; lite é produto puro.
- B: FECHADO como engenharia — retomadas fora do primário (r1-3) e sensibilidade
  descritiva não exigem escolha experimental nova; guards existentes cobrem o
  que cobrem; preservação de estado/sequência é propriedade de implementação.
- C: FECHADO como limitação — drift de config é fail-closed; degradação
  silenciosa do endpoint sob mesmo identificador vira limitação declarada do
  piloto (canary/pinagem seria expansão de engenharia, não decisão do piloto).
- D: FECHADO como decisão 7 — regra de retomada congelada.
- E: FECHADO como engenharia/produto — o operador precisa só da propriedade de
  auditabilidade da cadeia; a forma (escalar recursivo vs. manifesto) é
  delegável. Retenção já selada na Emenda 2 ("o parcial nunca é mutado nem
  removido"); retenção não é reconstrutível depois, então vale desde o início.

## Questões descartadas e por quê

- B, C, E: descartadas como decisão do operador pela classificação do conselho
  na r2 — são trabalho de engenharia ou limitação a registrar, não escolha
  experimental; o operador assentou com a classificação.
- Cautela da r2 (falhas/exclusões por braço 1 vs N): registrada como nota
  operacional para o relatório do experimento — sem limiar novo de
  "rebaixamento" agora (seria decisão fora destes residuais).
- Questões adiadas da r1: todas re-enquadradas e resolvidas na r2; nenhuma
  ficou aberta sem resolução.

## Decisões assentadas (quem decidiu: o operador)

Rodada 1 — as 6 questões da fronteira, todas com a recomendação do conselho aceita:

1. **`lite` fora do corpus primário** — corpus primário 1-vs-N só
   `stage2_mode="full"` explícito; `lite` no máximo como estrato/braço próprio
   pré-especificado; nunca agregar lite+full. (Operador: "Aceito: lite fora do
   primário (Rec.)")
2. **Política do `lite` pré-dados** — congelada antes dos dados; escolha não
   depende de resultado observado, dificuldade, urgência ou falha seletiva;
   fallback operacional = fora do corpus; motivo registrado no run.
   (Operador: "Aceito: política pré-dados (Rec.)")
3. **Primário só execuções integrais** — runs retomadas (`resumed_from` ≠ null)
   fora da comparação primária; vivem em análise de sensibilidade e contabilidade
   operacional. (Operador: "Primário só integrais (Rec.)")
4. **Uma unidade experimental** — parcial + retomada = 1 observação, nunca 2;
   endpoint de qualidade usa só o resultado final elegível; custo/latência agrega
   todas as tentativas por regra prévia; atrito no relatório.
   (Operador: "Aceito: uma unidade (Rec.)")
5. **sha = integridade de bytes** — `resumed_from` certifica apenas
   identidade/integridade dos bytes apontados; match de config é verificação
   separada; não prova equivalência nem elegibilidade causal.
   (Operador: "Aceito: só integridade de bytes (Rec.)")
6. **Corte declarado + fail-closed** — leitura retroativa (ausente=default) só
   para legado anterior a corte declarado; toda run do piloto grava
   `stage2_mode` e `resumed_from` explicitamente; ausência pós-corte = registro
   inelegível, nunca default silencioso. (Operador: "Aceito: corte + fail-closed
   (Rec.)")

Rodada 2 — o residual load-bearing e o condicional:

7. **Regra de retomada congelada** — retomar toda falha tecnicamente retomável,
   por classes objetivas de falha, nunca pelo conteúdo do parcial observado;
   exceções (teto de custo, segurança) pré-declaradas e registradas.
   (Operador: "Aceito: regra congelada (Rec.)")
8. **`lite` é produto puro no piloto** — sem intenção de estrato analítico;
   nenhuma análise do piloto usa resultados lite. Se um dia virar estrato,
   nova emenda congelando nº de avaliadores, regra de seleção e ordem pré-dados.
   (Operador: "Sem intenção de estrato (Rec.)")

Fato verificado no repo durante a sessão: `config_snapshot` cobre providers,
membros (provider/model/params), chairman, profiles e settings
(`provenance.py:67-99`); o guard `config_drift` do resume compara o
`config_sha256` do parcial com o atual — drift de modelo/provider entre parcial e
retomada é detectado, fail-closed.

## Custo acumulado

- Rodada 1: 9 chamadas / 2 GLM / 24.607 tok / 435s (registro `9573a1b2664c`).
- Rodada 2: 9 chamadas / 2 GLM / 29.876 tok / 446s (registro `0b4e3f212ab9`).
- Total: 18 chamadas / 4 GLM / 54.483 tok (dentro do orçamento de 3 rodadas;
  fronteira esvaziou na 2ª).

*Bundles: `bundle-emenda2-r1.md`, `bundle-emenda2-r2.md`. O conselho aconselhou
(duas rodadas encadeadas; avisos e a divisão do topo da r2 estão nos registros);
quem fechou cada questão foi o operador. Nada foi assumido em silêncio.*
