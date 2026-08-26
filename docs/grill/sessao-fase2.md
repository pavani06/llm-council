# Entendimento compartilhado — Fase 2 do llm-council
Sessão council-grill · 2026-08-26 · Skill: council-grill (estreia, issue #14) ·
Operador: Fernando Pavani · Rodadas: 2 (fronteira vazia na 2ª) · Orçamento aprovado:
18-27 chamadas / 4-6 GLM · Custo real: 18 chamadas / 4 GLM (1 execução parcial da r2
morreu por timeout de processo antes de salvar registro; reexecutada com sucesso —
falha registrada, custo contabilizado no limite aprovado).

## Rodadas (encadeadas por run_refs)

- Rodada 1 — sha `e5957637d9ae` (19.341 tok, dividido): 26 questões → blocos A (11
  decisões de fundação) e B (5 recomendações aceitas).
- Rodada 2 — sha `6656b23a66c7`, ref `e5957637` (22.952 tok, dividido): sub-decisões
  de métrica/schema/sanitização → blocos C (validado) e D (aceito).

## Decisões assentadas (quem decidiu: o operador, exceto onde indicado)

### Fundação (r1, bloco A — "valido o bloco A inteiro")
1. Rodadas, clustering, moderação e fast-path são **mecanismos desacoplados**,
   entregues em cortes verificáveis — não nascem juntos.
2. Saída da Fase 2 = **recomendação com dissidências auditáveis**; decisão automática
   só em domínio de baixo risco com política explícita.
3. Opções **seladas por versão**; opção nova gera nova versão da rodada comparável.
4. Posições independentes primeiro; revisão vê **objeções anonimizadas**; placar
   pré-revisão exige justificativa (ancoragem).
5. Revisão válida = registro estruturado (anterior→nova, evidência, confiança).
6. Multi-rodada = **composição de runs/bundles imutáveis por hash** (nada stateful).
7. Revisões **sempre acrescentam**; posições abandonadas reconstruíveis.
8. Schema **aditivo**; caminho de 1 rodada intocado (golden segue valendo).
9. Clustering = **diagnóstico** sobre endossos por id; nunca regra de decisão.
10. Moderador sintetiza/rotula/registra; **nunca** exclui, desempata ou sobreponhe.
11. Fast-path mantém proveniência + rótulo de "deliberação não plena"; pares são
    entrada não-confiável; "evidência insuficiente" é resultado válido.

### Experimento (r1 B + r2 C/D — recomendações aceitas pelo operador)
- Falha-hipótese: questões load-bearing não contestadas por isolamento da rodada única;
  corpus = os registros reais existentes (74f19a, e59576, 6656b2).
- **Primeira issue da Fase 2 = o experimento 1-vs-N, pré-registrado, antes de qualquer
  código de rodadas.** Tudo constante entre braços; só varia nº de rodadas; teto 3,
  parada por estabilidade (estabilidade ≠ correção).
- Status: **piloto exploratório / decisão de engenharia** (n=3, sem falsa precisão).
- Unidade: defeito/requisito verificável por registro; denominador congelado no
  pré-registro; taxonomia de falhas fechada antes do código (premissa não questionada,
  erro endossado, alternativa ausente, consenso por conformidade; achado novo =
  exploratório, não vitória retrospectiva).
- Endpoint: correção de defeito pré-registrado + atribuível à informação da deliberação
  + ausência de dano compensatório. Adjudicação: estrutural mecânica; substância por
  **rubrica pré-selada escrita pelo operador**, cega ao braço; LLM do run não é juiz.
- Regra de engenharia (n=3, direcional): ≥1 correção atribuível sem dano = seguir para
  o corte seguinte; 0/3 ou qualquer falso consenso introduzido = restringir a perfis e
  reavaliar. **Sem retry no piloto** (conformidade já é dado).

### Schema e sanitização (r2 — validado/aceito)
- Schema da revisão: anterior, nova/manutenção explícita, natureza, **gatilho**
  (peer/artefato/evidência/interno — interno não conta como efeito causal), justificativa,
  round, proveniência. Inválida: texto preservado + erro classificado + posição anterior
  persiste operacionalmente + conta no denominador como falha de conformidade — nunca
  descarte silencioso. "Persiste" ≠ "sem mudança deliberada".
- Sanitização: **contenção estrutural** (dado delimitado, sem autoridade de controle;
  NÃO remoção por padrões de injection); original preservado segregado ANTES de
  sanitizar; versão/motivo de cada redação vinculados; falha = continuar marcado
  (bloqueio só para segredo/PII se política exigir). Piloto: escopo = só isolamento;
  PII/segredos declarados fora de escopo (bundles controlados pelo operador).

## Os quatro artefatos a selar antes de qualquer código (entregáveis da 1ª issue da Fase 2)

1. Rubrica + endpoint (escrita pelo operador, por caso).
2. Taxonomia de falhas + denominador.
3. Contrato do schema de revisão + política de inválidos.
4. Modelo de ameaça + política de transformação/continuidade.

## Questões descartadas e por quê

Nenhuma descartada; questões dependentes de decisões abertas foram re-agendadas pela
skill para a rodada 2 e resolvidas lá.

*O conselho aconselhou (duas rodadas, ambas honestamente divididas no topo — os avisos
estão nos registros); quem assentou cada questão foi o operador. Nada foi assumido em
silêncio.*
