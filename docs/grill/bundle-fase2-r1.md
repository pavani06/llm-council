PAUTA (Fase 2 do llm-council, a definir): rodadas de deliberacao e clustering de posicoes.

Estado atual (Fase 1 completa, 13/15 do epico, smoke pago OK):
- Deliberacao de 1 rodada: estagio 1 (respostas com papeis + bundle) -> destilacao em
  candidatos -> estagio 2 (ranqueamento cego por Borda) -> estagio 3 (sintese ou decisao).
- Cadeia entre execucoes: run_refs por sha256; bundle selado por sha256; registro imutavel.
- Perfis: continuation (decider/proposal) e grill (synthesizer/questions). MCP stateless.
- Constraints vigentes: golden byte a byte do caminho ask; registros aditivos; stdlib pura.

O que a Fase 2 promete (do plano aprovado, Tarefa "Fase 2"):
- Loop de rodadas intra-run: membro ve respostas anonimizadas dos pares + veredictos da
  rodada anterior e pode revisar; destinado a debates de verdade (ADR, root-cause).
- Clustering de posicoes por opcao (matriz de endosso) ao lado do Borda.
- Presidente-moderador para sintese de dissidencia.
- Fast-path: perfis baratos com subconjunto de membros e/ou sem ranking.

Decisoes ja tomadas pelo operador (sessao grill 74f19a4aa888, 2026-08-26):
- Fase 2 so abre depois que a Fase 1 fechar pelas skills (#13 feita; #14 e esta sessao).
- Nada de Fase 2 em paralelo com o fechamento.

PERGUNTA DA RODADA: antes de desenhar a Fase 2, quais decisoes sobre escopo, formato
e limites precisam ser tomadas pelo operador? Questionem o que, respondido errado,
faz a Fase 2 nascer torta.
