# Handoff — issue #3 (T4)
PR #17 · branch issue/3-structured-parser (código em 76bfb9e33800) · 2026-08-25

## O que mudou no repo
- `council/structured.py` (novo, folha): `parse_questions(texto, max_n)`, `parse_proposal(texto)`, `parse_decision(texto, ids_validos)` — todos `(resultado, erro)`.
- `test_offline.py`: seção 18 (43 checks: bem-formados, variantes, malformados, 25 regressões de tres rodadas de probes adversariais do review).

## Decisões tomadas em voo (fora do plano)
- Cabeçalho vale só como LINHA INTEIRA, com negrito/crase e dois-pontos finais em qualquer quantidade/ordem (`**QUESTIONS**:`, `__DECISÃO__:`, `QUESTIONS::::` → abrem bloco; `NOTQUESTIONS:` → não). Seção termina no próximo cabeçalho estruturado de qualquer tipo.
- Vazio semântico: campo que só tem espaço/aspas/negrito (`""`, `**`, só-espaços) invalida; `-` e `nenhuma` são conteúdo válido.
- Ausente × vazio: linha de campo presente sem conteúdo = "vazio"; linha/cabeçalho ausente = "ausente".
- Id de questão ≤ 9 dígitos (int() gigante lança ValueError); repetido: primeira ocorrência vence; fora de 1..max_n ignorado.

## Pegadinhas descobertas
- Linha de corpo que consiste EXATAMENTE numa palavra-cabeçalho (`proposta`, `decision` sozinhos numa linha) encerra a seção — é comportamento por design (cabeçalho = linha inteira); redija corpo que nunca seja só a palavra do cabeçalho.
- Regexes de campo dentro da seção precisam `re.MULTILINE` e gaps `[ \t]` (nunca `\s*`, que cruza linha e engole o campo seguinte quando o atual vem vazio).

## O que a próxima issue precisa saber
- Gramática exata (para #5/#7/#8 consumirem sem reler código):
  - cabeçalhos: QUESTIONS/QUESTOES/QUESTÕES/PERGUNTAS, PROPOSAL/PROPOSTA, DECISION/DECISAO/DECISÃO — linha inteira, minúsculo ok, com `:`(es) e negrito opcionais;
  - `QUESTIONS:` → linhas `N | pergunta | recomendacao` (N ∈ 1..max_n, ≤9 dígitos; campos semanticamente vazios invalidam a linha);
  - `PROPOSAL:` → `TITULO: <linha>` + `CORPO: <resto do bloco até o próximo cabeçalho>` (ambos não vazios);
  - `DECISION:` → UMA linha `STATUS | ESCOLHA | CONFIANCA | DISSIDENCIAS | FUNDAMENTOS` (todos não vazios; STATUS ∈ {DECIDIDO, ENCALHADO}; ESCOLHA ∈ ids_validos; pipes extras ficam em fundamentos);
  - erro é sempre string nomeada; resultado vazio quando há erro — nunca campo inventado.
- A #5 (decision_prompt) deve pedir EXATAMENTE a linha de 5 campos com pipes e marcador explícito para "sem dissidências" (ex.: "nenhuma") — campo vazio invalida. E não pode deixar o modelo citar palavras-cabeçalho sozinhas em linha.

## Pendências deixadas
- nenhuma
