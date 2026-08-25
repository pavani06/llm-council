# Handoff — issue #3 (T4)
PR #17 · branch issue/3-structured-parser (código em 9dea0fd4511f) · 2026-08-25

## O que mudou no repo
- `council/structured.py` (novo, folha): `parse_questions(texto, max_n)`, `parse_proposal(texto)`, `parse_decision(texto, ids_validos)` — todos `(resultado, erro)`.
- `test_offline.py`: seção 18 (29 checks: bem-formados, variantes, malformados, regressões de probes adversariais do review).

## Decisões tomadas em voo (fora do plano)
- Correções do review adversarial (4 bloqueios): cabeçalho vale só como LINHA INTEIRA (`NOTQUESTIONS:`/`COUNTERPROPOSAL:`/`INDECISION:` não abrem bloco); seção termina no próximo cabeçalho estruturado de qualquer tipo (PROPOSAL não engole DECISION posterior); campo vazio invalida (questão/decisão/título/corpo — linha destruída ou erro "vazio"); id limitado a 9 dígitos (int() de milhares de dígitos lança ValueError).
- Semântica ausente × vazio: linha de campo presente sem conteúdo = "vazio"; linha/cabeçalho ausente = "ausente".
- TÍTULO/TITULO cobertos por `T[ÍI]TULO`; regexes de campo com `re.MULTILINE` (a seção começa com `:` após o cabeçalho).
- Id de questão repetido: primeira ocorrência vence; id fora de `1..max_n` ignorado (mesma regra do `parse_verificacao`).

## Pegadinhas descobertas
- Cabeçalho de bloco vem seguido de `:` — o `_section` não o tira do texto; regexes de campo precisam `re.MULTILINE`.
- Linha `N | pergunta` (um pipe só) é linha destruída: fica FORA, nunca vira questão com recomendacao vazia.

## O que a próxima issue precisa saber
- Gramática exata (para #5/#7/#8 consumirem sem reler código):
  - cabeçalhos aceitos: QUESTIONS/QUESTOES/QUESTÕES/PERGUNTAS, PROPOSAL/PROPOSTA, DECISION/DECISAO/DECISÃO — sempre como linha inteira, com ou sem `:`, com negrito;
  - `QUESTIONS:` → linhas `N | pergunta | recomendacao` (N ∈ 1..max_n, ≤9 dígitos; campos vazios invalidam a linha);
  - `PROPOSAL:` → `TITULO: <linha>` + `CORPO: <resto do bloco>` (ambos obrigatórios e não vazios);
  - `DECISION:` → UMA linha `STATUS | ESCOLHA | CONFIANCA | DISSIDENCIAS | FUNDAMENTOS` (todos não vazios; STATUS ∈ {DECIDIDO, ENCALHADO}; ESCOLHA ∈ ids_validos; pipes extras ficam em fundamentos);
  - erro é sempre string nomeada; resultado vazio quando há erro — nunca campo inventado.
- A #5 (decision_prompt) deve pedir EXATAMENTE a linha de 5 campos com pipes e marcador explícito para "sem dissidências" (ex.: "nenhuma") — campo vazio invalida.

## Pendências deixadas
- nenhuma
