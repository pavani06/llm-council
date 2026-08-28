PAUTA (rodada 2 de 3): Emenda 2 do pre-registro 1-vs-N — os residuais apos a rodada 1
(sha 9573a1b2664c), cujas decisoes o operador ja assentou.

DECIDIDO PELO OPERADOR NA RODADA 1 (todas as recomendacoes do conselho aceitas):

1. Corpus primario 1-vs-N: so stage2_mode="full" explicito. lite FORA do primario;
   no maximo estrato/braco proprio pre-especificado; nunca agregar lite+full.
2. Politica do lite: congelada ANTERIOR aos dados; escolha nao depende de resultado
   observado, dificuldade, urgencia ou falha seletiva; fallback operacional = fora do
   corpus; motivo registrado no run.
3. Runs retomadas (resumed_from != null): FORA da comparacao primaria; vivem em
   analise de sensibilidade e contabilidade operacional.
4. Parcial + retomada = UMA unidade experimental, nunca duas; endpoint de qualidade
   usa so o resultado final elegivel; custo/latencia agrega todas as tentativas por
   regra previa; falhas e retomadas no relatorio de atrito.
5. sha de resumed_from certifica SO identidade/integridade dos bytes apontados;
   match de config e verificacao separada; nao prova equivalencia a execucao
   integral nem elegibilidade causal.
6. Leitura retroativa (ausente=default) so para legado anterior a corte declarado;
   toda run do piloto grava stage2_mode e resumed_from explicitamente; ausencia
   pos-corte = falha fechada, registro inelegivel.

FATO VERIFICADO NO REPO (relevante para C): config_snapshot cobre providers
(base_url, api, api_key_env, known_models), membros (provider/model/params),
chairman, profiles e settings (council/provenance.py:67-99); o guard config_drift do
resume compara o producer.config_sha256 do parcial com o config atual e falha com
erro nomeado. Drift de modelo/provider/roster entre parcial e retomada JA E
detectado, fail-closed. Limite conhecido fora do repo: degradacao silenciosa do lado
do endpoint (mesmo nome de modelo servindo peso diferente) nao e detectavel por hash.

OS CINCO RESIDUAIS DESTA RODADA — reenquadrados pelas decisoes acima, interroguem
cada um:

A. DEFINICAO DO LITE CONGELADA: com lite fora do primario (1) mas admissivel como
   estrato pre-especificado, o operador precisa congelar antes do piloto o numero de
   avaliadores, a regra de selecao (prefixo deterministico da config NAO e subamostra
   aleatoria) e a ordem? Ou lite fica 100% fora de qualquer analise no piloto
   (produto puro, sem estrato)?

B. INVARIANTES DE RETOMADA PARA A SENSIBILIDADE: retomadas fora do primario (3),
   mas podem entrar na analise de sensibilidade. Que invariantes uma retomada precisa
   satisfazer para entrar nessa analise: mesma unidade/braco original; manifest,
   prompt, roster, rubrica e endpoint identicos; estado parcial preservado; nenhuma
   chamada estocastica repetida/omitida/recalculada; decisao de retomar independente
   do conteudo; identidade do produtor preservada? Quais sao exigiveis com o
   mecanismo atual (config_drift + sha) e quais precisariam de convencao nova?

C. LIMITE DE DETECCAO: dado que config_sha256 ja cobre drift de provider/modelo
   (fato acima), o residual e so o limite fora do repo (degradacao silenciosa do
   endpoint)? Isso e decisao do operador, risco aceito por padrao, ou fora de escopo
   do piloto?

D. REGRA DE RETOMADA PRE-DADOS: a decisao de retomar pode ocorrer apos observar o
   parcial. Com retomadas fora do primario (3), a selecao do que se retoma enviesa a
   analise de sensibilidade. Congelar regra (ex.: "retomar toda falha tecnicamente
   retomavel") ou registrar a selecao como limitacao declarada da sensibilidade?

E. CADEIAS DE RETOMADA: um campo escalar apontando so para o ULTIMO parcial basta
   (decisoes 3-5 reduziram a carga do resume), ou o registro precisa permitir auditar
   a cadeia inteira (retomada de retomada) para a sensibilidade e o relatorio de
   atrito? Peso baixo ou decisao de schema ainda aberta?

PERGUNTA: desses cinco residuais, quais ainda sao decisoes do OPERADOR load-bearing
para o experimento 1-vs-N, quais sao de produto/engenharia que o operador nao precisa
fechar agora, e quais ja estao resolvidos pelas seis decisoes da rodada 1 sem decisao
nova?
