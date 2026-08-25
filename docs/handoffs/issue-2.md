# Handoff — issue #2 (T1)
Merged: via squash no PR · data: 2026-08-25

## O que mudou no repo
- `test_offline.py`: seção 15 — golden byte a byte dos 3 renders (ranking, chairman cego, chairman aberto), entrada FIXA declarada no teste.
- `golden/`: 3 baselines (`ranking.txt`, `chairman-blind.txt`, `chairman-open.txt`).

## Decisões tomadas em voo (fora do plano)
- 3 arquivos golden em vez de 2: a variante não-cega do chairman altera o render (alias com nomes), e a diretiva mandava incluí-la quando diferisse.
- Mensagem de falha mostra a primeira divergência (índice do char + janela de contexto dos dois lados), não apenas "diferente".

## Pegadinhas descobertas
- O teste boota criando o golden quando ausente: apagar `golden/` e rodar "reseta" a âncora em silêncio. Nunca remova `golden/` a não ser que regenerar seja a intenção explícita e justificada.
- Worktree não tem `.venv` (é ignorado): rode o teste com o python do venv da árvore principal a partir do diretório da worktree.

## O que a próxima issue precisa saber
- Para #4 (T2 config): "default = os 4 critérios atuais" agora tem endereço físico — `golden/ranking.txt`, bloco "Criterios". A `DEFAULT_CRITERIA` da #5 deve renderizar exatamente aquele bloco.
- Toda issue que tocar `council/prompts.py` (ou caminho que alimente os prompts) deve ver a seção 15 verde — é a constraint 1 do épico em forma de teste.

## Pendências deixadas
- nenhuma
