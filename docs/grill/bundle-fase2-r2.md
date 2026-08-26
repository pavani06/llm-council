PAUTA (rodada 2 de 3): Fase 2 do llm-council — detalhar as 3 dependencias deixadas
abertas pela rodada 1 (sha e5957637d9ae), cujas decisoes o operador ja assentou:
mecanismos desacoplados; saida = recomendacao auditavel; opcoes seladas por versao;
posicoes independentes antes de ver pares (objeccoes anonimizadas); revisao =
registro estruturado; composicao de runs imutaveis; schema aditivo; clustering
diagnostico sobre endossos; moderador sem poder de decisao; fast-path mantem
proveniencia; pares sao entrada nao-confiavel; evidencia insuficiente e resultado
valido; teto 3 rodadas com parada por estabilidade; Borda default com veto/aprovacao
opt-in por perfil.

Decidido tambem: o experimento 1-vs-N rodadas e a PRIMEIRA issue da Fase 2, com
criterios de abandono pre-registrados antes de qualquer codigo de rodadas.

AS TRES DEPENDENCIAS DESTA RODADA — interroguem cada uma:

A. METRICA DO EXPERIMENTO: "qualidade da deliberacao" precisa ser operacional no
   corpus real (3 registros existentes: ask, continuation, grill). O que medir,
   com que denominador, e quem adjudica? O que conta como falha da rodada unica
   que multiplas rodadas teriam pego?

B. SCHEMA MINIMO DA REVISAO: o registro estruturado de revisao (posicao anterior,
   posicao nova, evidencia motivadora, confianca) precisa de formato concreto que
   o parser tolerante consiga extrair e o registro aditivo consiga guardar. Quais
   campos, quais validacoes, o que acontece com revisao invalida?

C. SANITIZACAO ENTRE MEMBROS: respostas dos pares sao entrada nao-confiavel
   (injection, dados sensiveis, citacoes inventadas). Qual e a politica MINIMA
   viavel para a Fase 2 sem virar subsystema de seguranca: o que sanitize, onde
   no pipeline, e o que explicitamente fica fora de escopo?

PERGUNTA: quais SUB-decisoes dentro de A, B e C ainda sao do operador e fariam a
Fase 2 nascer torta se respondidas errado?
