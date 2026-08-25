# Handoff — issue #3 (T4)
PR #17 · branch issue/3-structured-parser (código em 9dea0fd4511f) · 2026-08-25

## O que mudou no repo
- `council/structured.py` (novo, folha): `parse_questions(texto, max_n)`, `parse_proposal(texto)`, `parse_decision(texto, ids_validos)` — todos `(resultado, erro)`.
- `test_offline.py`: seção 18 (17 checks: bem-formados, variantes, malformados).

## Decisões tomadas em voo (fora do plano)
- TÍTULO/TITULO cobertos por `T[ÍI]TULO`; regexes de campo com `re.MULTILINE` (a seção começa com `:` após o cabeçalho — sem MULTILINE o `^` nunca casa; mesmo motivo pelo qual o parser de cédulas usa MULTILINE).
- Pipes extras além do 5º campo voltam para `fundamentos` por join, não split-drop.
- Id de questão repetido no bloco: primeira ocorrência vence (dedup), id fora de `1..max_n` é ignorado (mesma regra do `parse_verificacao`).

## Pegadinhas descobertas
- Cabeçalho de bloco vem seguido de `:` — o `_section` não o tira; qualquer regex de campo dentro da seção precisa `re.MULTILINE`.
- Linha `N | pergunta` (um pipe só) é linha destruída: fica FORA, nunca vira questão com recomendacao vazia.

## O que a próxima issue precisa saber
- Gramática exata (para #7 consumir `parse_questions` e #8 consumir `parse_decision` sem reler código):
  - `QUESTIONS:` → linhas `N | pergunta | recomendacao` (N em 1..max_n; negrito/tradução tolerados; headers aceitos: QUESTIONS/QUESTOES/PERGUNTAS);
  - `PROPOSAL:` → `TITULO: <linha>` + `CORPO:` (corpo = todo o resto do bloco; aceita PROPOSTA/TÍTULO);
  - `DECISION:` → UMA linha `STATUS | ESCOLHA | CONFIANCA | DISSIDENCIAS | FUNDAMENTOS` (STATUS ∈ {DECIDIDO, ENCALHADO}; ESCOLHA deve estar em ids_validos; aceita DECISAO, minúsculo, ponto final);
  - erro é sempre string nomeada; resultado vazio quando há erro — nunca campo inventado.
- A #5 (decision_prompt) deve pedir EXATAMENTE a linha de 5 campos com pipes — o parser já está calibrado para isso.

## Pendências deixadas
- nenhuma
