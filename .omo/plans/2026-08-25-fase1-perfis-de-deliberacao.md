# Fase 1 — Perfis de Deliberação — Plano de Execução

**Objetivo:** llm-council passa a deliberar (entrada bundle + perfil, membros com papéis, candidatos destilados, decisão estruturada, cadeia por `run_refs`) sem mudar o comportamento atual do `ask`, comprovado por teste golden.

**Fase:** Implementação (Fase 1 de 3; Fase 2 rodadas/clustering e Fase 3 hooks ficam fora deste plano)

**Dependências:** nenhuma nova — stdlib pura se mantém; SDK `anthropic` é a única dependência e não muda. Chaves de API já configuradas em `.env`.

**Duração estimada:** 3 a 4 sessões de agente (T1-T4 ~1 sessão; T5-T8 ~1; T9-T11 ~1; T12-T13 ~0,5-1) + 1 smoke run pago com aprovação do operador.

**Commit:** um commit por tarefa, estilo do log atual (`git log --oneline`: "audit: o que a sintese afirma que ninguem sustentou"). Sem commit sem pedido explícito do operador por sessão.

---

## Intent (cinco partes)

| Campo | Conteúdo |
|---|---|
| **Description** | O conselho ganha um eixo de parametrização: `council deliberate --profile <p> --bundle <f> [--ref <sha>...]` monta mensagens com papel por membro, destila candidatos das respostas do estágio 1, ranqueia os candidatos às cegas com critérios do perfil, e o presidente devolve saída estruturada (decisão ou fronteira) parseada tolerante. Cada deliberação referencia anteriores por `run_refs` (sha256). Dois perfis iniciais: `continuation` (próximo passo pós-execução de issue) e `grill` (rodada de interrogatório com questões ranqueadas por load-bearingness). Duas skills consumidoras: `grill-the-council` (lê registros, entrevista o operador) e `council-grill` (dirige rodadas via ferramenta MCP). |
| **Constraints** | Ver seção abaixo (6, dentro do orçamento 5-7). |
| **Failure scenarios** | (a) O prompt default muda silenciosamente — deriva de qualidade invisível. (b) Perfis viram framework especulativo com abstrações para casos que não existem. (c) Parse de decisão inventa campo ausente — decisão "bem-sucedida" sem fundamento. (d) Cota GLM do coding plan queimada por deliberações de ciclo automático. (e) Registro antigo vira ininterpretável após o upgrade. (f) Servidor MCP ganha estado de sessão e quebra a filosofia arquivo+sha. |
| **Success scenarios** | (1) `council ask "..."` pós-upgrade produz prompts byte a byte idênticos (golden diff vazio) e `test_offline.py` 100% verde. (2) `council deliberate "..." --profile continuation --bundle evidencia.md` devolve JSON com `status`, `escolha`, `confianca`, `dissidencias` — e `status: "encalhado"` quando `divided`. (3) Uma rodada `--profile grill` devolve fronteira de questões ranqueadas com recomendações. (4) `run_refs` do round N+1 apontam para o sha do round N sem alterar o registro anterior. (5) As duas skills operam uma sessão real cada. |
| **Connections** | Servidor MCP registrado no Claude Code (contrato inalterado, ferramenta nova); família de skills grill (`grilling`, `batch-grill-me` em `~/.agents/skills/`); cota trimestral GLM do coding plan (2 chamadas por pergunta hoje; deliberação = 2N+1 chamadas); `runs/*.json` endereçados por sha (padrão de `judgment.py`); README e `docs/arquitetura.html` (só README neste plano); Fases 2 e 3 futuras constroem sobre estes mesmos seams. |

## Constraints (orçamento: 6)

Direcionais, incondicionais, em linguagem de dono do resultado:

1. **O council atual vira o primeiro perfil, congelado**: nenhuma mudança de comportamento no caminho `ask`; prompts default byte-idênticos comprovados por golden test que roda antes de qualquer refactor e depois de cada tarefa.
2. **Servidor MCP permanece sem estado de sessão**: uma chamada = um ciclo de conselho; estado de rodadas vive no chamador (skill), passado como `run_refs` + bundle.
3. **Falha nunca silenciosa se preserva em todo caminho novo**: parser que não adivinha (padrão `parse_ballot`), aviso nomeado por parsing falho, truncamento e recusa continuam detectados.
4. **Proveniência continua selando o que gerou o registro**: perfis entram no `config_snapshot`/`config_sha256`; bundle entra com `sha256` do conteúdo; `council show` segue reportando divergência.
5. **Stdlib pura se mantém**: nenhuma dependência nova além do SDK `anthropic` existente.
6. **Registro antigo continua interpretável**: campos novos são apenas aditivos no `Run`; arquivos existentes em `runs/` não são reescritos.

### Failure conditions (superfície do validador — separadas das constraints pela regra "saber isto mudaria como o construtor escreve o código?")

- Golden diff não-vazio após qualquer tarefa → tarefa reprovada.
- Qualquer check existente das 14 seções de `test_offline.py` regredir → tarefa reprovada.
- Registro de `deliberate` sem `profile`/`bundle_sha256` quando bundle foi dado → falha.
- Parser estrutural devolver campo inventado ou aceitar bloco ausente → falha (deve devolver erro nomeado).
- Handler MCP mantendo estado entre `tools/call` → falha de desenho (revisão no T10).

## Manual Brake Gate (respondido antes de finalizar o plano)

1. **Quem precisa e o que quebra sem isto?** O operador (você). Sem isto: decisões de continuidade de plano seguem mono-modelo ou com bundle colado à mão na pergunta — dor já evidenciada em `runs/20260824T132101` ("SEGUNDA rodada... este mesmo conselho já avaliou") e `runs/20260825T010853` ("Contexto (autocontido...)"); o grill segue monocultural (um entrevistador).
2. **Custaria uma semana de engenharia — construiríamos?** O núcleo (T1-T11) sim: dois consumidores imediatos recorrentes e 14 casos catalogados reutilizam os mesmos seams. As Fases 2/3 não sobrevivem a esta pergunta agora — por isso ficam fora. As skills (T12) custam pouco e têm valor independente.
3. **Quem é o dono do não?** O operador. Gates de parada embutidos: T1 é a âncora que protege o existente; T13 exige aprovação explícita para o smoke run pago (custo real de cota GLM).

## Lifecycle (BUILD/STABILIZE/SIMPLIFY/REMOVE)

- Componentes novos (perfis, `structured.py`, `deliberate`, `council_deliberate`): estado **BUILD** defensivo — formatos rígidos de saída nos prompts, parsers tolerantes mas que nunca inventam, warnings nomeados.
- Comportamento atual (ask): o golden test é o mecanismo de **STABILIZE** — congela o que a produção (`runs/` com 8 registros reais) já valida.
- Nada entra neste plano para ser removido depois; "One In, One Out" não se aplica (não é harness de avaliação, é produto). Risco de retrabalho tratado no Eixo 2.

---

## Tarefas

### Tarefa 1: Congelar o comportamento atual (golden snapshots) — ÂNCORA

**Artefatos:**
- Entrada: `council/prompts.py` (renderizações atuais), `test_offline.py`
- Saída: `golden/ranking.txt`, `golden/chairman.txt`, seção 15 em `test_offline.py`

- [ ] **Passo 1: Gerar baselines golden**
  Criar seção "15) golden: prompts byte a byte" em `test_offline.py`: com entrada FIXA (pergunta, dict de respostas rotuladas, fixture de consensus), chamar `ranking_prompt` e `chairman_prompt` (modo atual); se `golden/*.txt` não existir, gravar e passar; se existir, comparar byte a byte.
  Comando: `rm -rf golden && .venv/bin/python test_offline.py`
  Esperado: "todos os testes passaram", exit 0, `golden/` criado com os dois arquivos.

- [ ] **Passo 2: Inspecionar os baselines**
  Comando: `cat golden/ranking.txt golden/chairman.txt`
  Esperado: texto idêntico ao corpo das funções em `prompts.py` com a entrada fixa substituída; os 4 critérios literais de `prompts.py:20-23` presentes; sem sobras de template.

- [ ] **Passo 3: Provar que o teste detecta regressão**
  Alterar temporariamente um caractere em `prompts.py` (ex.: "Correcao" → "Correção"), rodar, reverter.
  Comando: `.venv/bin/python test_offline.py`
  Esperado: FALHA nomeada na seção 15; após reverter, verde de novo.

- [ ] **Passo 4: Verificação da tarefa**
  Critério: `.venv/bin/python test_offline.py` → exit 0 com seção 15 verde; golden regenerado idêntico ao commit anterior se re-rodado.

### Tarefa 2: Config — perfis, papéis e validação

**Artefatos:**
- Entrada: `council/config.py` (`Settings`, `load`, validação de settings desconhecidos em `config.py:164-167`)
- Saída: dataclass `Profile`, parsing de `[profiles.<nome>]` em `council.toml`, validações

- [ ] **Passo 1: Definir `Profile`**
  Campos: `name: str`, `roles: dict[str, str]` (nome de membro → texto do papel), `criteria: list[str]` (1 a 7 itens — orçamento de constraints aplicado na validação), `chairman_mode: str` (`"synthesizer"` | `"decider"`), `stage1_format: str` (`"prose"` | `"questions"` | `"proposal"`). Default de `criteria` quando ausente: os 4 critérios atuais de `prompts.py:20-23`.

- [ ] **Passo 2: Parsing + validação com erro nomeado**
  `Config.profiles: dict[str, Profile]`. Erros `ValueError` nomeados para: papel referindo membro inexistente; criteria vazio ou > 7; `chairman_mode`/`stage1_format` fora da lista; nome de perfil duplicado. Perfis são opcionais (ausência = comportamento atual).

- [ ] **Passo 3: Checagens offline (seção 16)**
  Fixture TOML em tmpdir com perfil válido e três inválidos; `COUNCIL_CONFIG` apontando para cada.
  Comando: `.venv/bin/python test_offline.py`
  Esperado: perfil válido carrega com campos corretos; cada inválido levanta `ValueError` com a mensagem nomeada esperada; `council.toml` atual (sem perfis) continua carregando.

- [ ] **Passo 4: Verificação**
  Critério: seção 16 verde; `./bin/council doctor` continua exit 0 e inalterado na saída.

### Tarefa 3: Prompts parametrizados (default byte-idêntico)

**Artefatos:**
- Entrada: `council/prompts.py`, golden da T1
- Saída: `ranking_prompt(question, labelled, criteria=DEFAULT_CRITERIA)`, `chairman_prompt(..., mode="synthesizer")`, `decision_prompt(...)` nova, `stage1_user_prompt(...)`

- [ ] **Passo 1: Parametrizar sem tocar o default**
  `DEFAULT_CRITERIA` = tupla com os 4 literais atuais verbatim. `ranking_prompt` renderiza criteria injetados; assinatura default renderiza byte a byte o golden. `chairman_prompt` ganha `mode`; `"synthesizer"` = texto atual exato.

- [ ] **Passo 2: Modo decider e molduras**
  Nova `decision_prompt(question, candidates, consensus, instructions)`: pede bloco `DECISION:` com campos `STATUS | ESCOLHA | CONFIANCA | DISSIDENCIAS | FUNDAMENTOS` (formato rígido no prompt, parse tolerante no T4). Nova `stage1_user_prompt(question, bundle, role_hint=None)`: compõe bundle + pergunta para o estágio 1 com perfil; sem perfil, devolve a pergunta inalterada.

- [ ] **Passo 3: Checagens offline (seção 17)**
  Critérios custom aparecem na renderização e os default não; golden inalterado; `decision_prompt` contém o bloco de formato e os rótulos cegos; `stage1_user_prompt(None, None)` == pergunta.
  Comando: `.venv/bin/python test_offline.py`
  Esperado: seção 17 verde E seção 15 (golden) verde.

- [ ] **Passo 4: Verificação**
  Critério: golden diff vazio com os novos defaults — esta é a prova de comportamento inalterado.

### Tarefa 4: Parser estruturado — `council/structured.py`

**Artefatos:**
- Entrada: padrão de `ranking.py:47-103` (`_section`, regex tolerante, nunca inventa)
- Saída: `council/structured.py` (módulo folha, não importa nada do projeto)

- [ ] **Passo 1: Três parsers**
  `parse_questions(text, max_n)` → lista de `{id, pergunta, recomendacao}` do bloco `QUESTIONS:` (linhas `N | pergunta | recomendacao`). `parse_proposal(text)` → `{titulo, corpo}` do bloco `PROPOSAL:`. `parse_decision(text, valid_ids)` → `{status, escolha, confianca, dissidencias, fundamentos}` do bloco `DECISION:`. Todos seguem `_section` com variantes de cabeçalho; devolvem `(resultado, erro)`; bloco ausente/ilegível → erro nomeado, resultado vazio — nunca adivinham.

- [ ] **Passo 2: Checagens offline (seção 18)**
  Casos bem-formados; variantes reais (negrito, cabeçalho traduzido, minúsculo — espelhar a tabela da seção 7); malformados (sem bloco, linha pela metade, `ESCOLHA` fora de `valid_ids`, `STATUS` fora de `DECIDIDO|ENCALHADO`) → erro nomeado, nada inventado.
  Comando: `.venv/bin/python test_offline.py`
  Esperado: seção 18 verde, incluindo "formato quebrado devolve erro, não inventa decisão".

- [ ] **Passo 3: Verificação**
  Critério: seção 18 verde; `python3 -c "from council import structured"` sem erro no python do sistema (stdlib pura).

### Tarefa 5: Engine — spec de entrada e mensagens com papel

**Artefatos:**
- Entrada: `council/engine.py` (`run` em `engine.py:191`, `_ask_one` em `engine.py:77-94`)
- Saída: dataclass `Deliberation`, `run(spec | str)`, `_ask_one` com messages

- [ ] **Passo 1: `Deliberation` e compatibilidade**
  `Deliberation(question, profile: Profile | None = None, bundle: str | None = None, run_refs: list[str] = ())`. `Council.run` aceita `str` (monta spec default com `profile=None`) — assinatura compatível, `test_offline.py` atual roda sem edição.

- [ ] **Passo 2: Mensagens do estágio 1 e roteamento de `stage1_format`**
  Sem perfil: exatamente `[{"role": "user", "content": question}]` (idêntico a `engine.py:81-83`). Com perfil: `[{"role": "system", "content": papel}, {"role": "user", "content": stage1_user_prompt(...)}]` quando o membro tem papel no perfil. `stage1_user_prompt` injeta a diretriz de formato conforme `stage1_format` do perfil: `prose` → nenhuma diretriz (pergunta + bundle); `questions` → diretriz pedindo o bloco `QUESTIONS:` no formato de linha `N | pergunta | recomendacao`; `proposal` → diretriz pedindo o bloco `PROPOSAL:` com `TITULO:` e `CORPO:`. O roteamento vive em `stage1_user_prompt` (T3), o engine apenas passa `profile.stage1_format`.

- [ ] **Passo 3: Checagens offline (seção 19)**
  Com fixture de perfil (via `COUNCIL_CONFIG`): membro com papel recebe 2 mensagens (system com o texto do papel, user com bundle); membro sem papel recebe 1; run sem perfil: todas as chamadas com 1 mensagem `user` e conteúdo idêntico à pergunta; perfil `questions` → prompt do estágio 1 contém a diretriz `QUESTIONS:`; perfil `proposal` → contém `PROPOSAL:`; perfil `prose` → não contém nenhuma das duas diretrizes.
  Comando: `.venv/bin/python test_offline.py`
  Esperado: seção 19 verde; seções 1-14 inalteradas.

- [ ] **Passo 4: Verificação**
  Critério: suite completa verde; nenhuma checagem existente editada ou removida.

### Tarefa 6: Engine — candidatos destilados no estágio 2

**Artefatos:**
- Entrada: `engine.py` (`stage2`/`_rank_one` em `engine.py:103-154`), `ranking.borda` (`ranking.py:117`)
- Saída: `Candidate(id, text, author)`, `stage2` operando sobre candidatos, `borda` por id de candidato

- [ ] **Passo 1: Desacoplar autores/avaliadores/candidatos**
  `stage1` respostas viram candidatos: perfil `prose` → 1 candidato por resposta (`id = author = nome`); `questions` → `parse_questions` por resposta, cada questão um candidato (`author` = membro que a escreveu, `id` = `q<m>-<n>`); `proposal` → 1 candidato por resposta. `exclude_self_rank` passa a comparar `author` (um membro não ranqueia as próprias questões). Ordem de cegamento: scrub de identidade → destilação → ranking (candidatos já nascem cegos).

- [ ] **Passo 2: Borda generalizado, registro compatível**
  `borda(ballots, candidate_ids)`; o campo `Consensus.member` passa a carregar o id do candidato (no caminho default, id == nome do membro → registro com shape idêntico ao atual).

- [ ] **Passo 3: Checagens offline (seção 20)**
  Default: consensus igual ao da seção 4 (mesmos scores por membro). Perfil `questions` com fake emitindo 3 questões por resposta: candidatos = 12, cédulas sem questões do próprio autor, rótulos cegos sem nome de membro no prompt de ranking (reusar verificação de vazamento da seção 3).
  Comando: `.venv/bin/python test_offline.py`
  Esperado: seção 20 verde.

- [ ] **Passo 4: Verificação**
  Critério: default path produz `consensus` idêntico ao pré-refactor para a mesma entrada (comparar contra valor capturado na seção 4 antes do refactor — snapshot em variável do próprio teste).

### Tarefa 7: Engine — `run_refs`, campos de registro e selo

**Artefatos:**
- Entrada: `engine.py` (`Run`, `save_run`), `council/provenance.py` (`config_snapshot` em `provenance.py:71-90`), padrão de endereçamento por sha de `judgment.py:152-174`
- Saída: campos `profile_name`, `bundle_sha256`, `run_refs`, `candidates`, `decision` no `Run`; perfis no `config_snapshot`

- [ ] **Passo 1: Campos aditivos no `Run`**
  Defaults neutros (`None`/`[]`) para o caminho ask não mudar semântica. `bundle_sha256` = sha256 do conteúdo do bundle (o conteúdo em si não é duplicado no registro; o arquivo/caminho é responsabilidade do chamador, o hash dá a âncora). `candidates` registra id/author/texto destilado. `decision` = resultado do parse do T4 (ou `None`).

- [ ] **Passo 2: Roteamento do estágio 3 por `chairman_mode`**
  `synthesizer` (default, com e sem perfil): usa `chairman_prompt` atual, `decision` fica `None`. `decider`: usa `decision_prompt` (T3) sobre os candidatos + consensus, parseia a resposta com `parse_decision` (T4); decisão parseada vai para `rec.decision` e a síntese cru continua em `rec.synthesis`. Parse falho ou bloco ausente → `decision = None` + aviso nomeado em `rec.warnings` ("estagio 3: decisao ilegivel — <erro>") — o mesmo tratamento que cédula ilegível recebe no estágio 2 (`engine.py:271-276`). `divided=True` com decider → o prompt exige `STATUS = ENCALHADO` (a síntese do impasse é a saída). Nenhuma chamada extra é feita além da que já existia.

- [ ] **Passo 3: Perfis no selo**
  `config_snapshot` ganha `"profiles"` (nome → campos do perfil). `config_sha256` muda quando perfis mudam — registro continua auto-interpretável.

- [ ] **Passo 4: Checagens offline (seção 21)**
  Registro de run default: campos novos com default neutro; `decision is None`. Run com perfil `decider` e fake emitindo `DECISION:` válido: `profile_name` preenchido, `bundle_sha256` = sha256 calculado à mão do bundle de fixture, `candidates` com autores, `decision.status` parseado. Fake emitindo `DECISION:` malformado: `decision is None` + aviso nomeado contendo "ilegivel". Run `synthesizer` com perfil: `decision is None` e sintese normal. Registro gravado em disco não é reescrito por segunda execução (endereçamento por sha, padrão `judgment.py`).
  Comando: `.venv/bin/python test_offline.py`
  Esperado: seção 21 verde; arquivos antigos em `runs/` intocados (`git status` limpo para `runs/`).

- [ ] **Passo 5: Verificação**
  Critério: `ls runs/*.json | wc -l` inalterado; seção 12 (selo) segue verde com os campos novos.

### Tarefa 8: Audit — corpus inclui bundle

**Artefatos:**
- Entrada: `council/audit.py` (`auditar` em `audit.py:126-153`, corpus em `audit.py:139`)
- Saída: corpus = respostas + pergunta + bundle (quando presente no registro)

- [ ] **Passo 1: Estender corpus e definir a fonte durável do bundle**
  `corpus = normalizar(respostas + pergunta + rec.get("bundle_content"))`. O registro guarda `bundle_sha256`, não o texto — a fonte durável é o arquivo original do chamador. `council audit` ganha flag `--bundle CAMINHO`: carrega o texto, confere `sha256(conteúdo) == rec["bundle_sha256"]` (divergência ou registro sem `bundle_sha256` com `--bundle` → erro nomeado e recusa, exit 2 — auditar com bundle que não é o da execução seria grounding fictício), e passa o texto para `auditar`. Sem `--bundle`, audit de registro com bundle audita só com respostas + pergunta (comportamento atual) e emite aviso de que o bundle não foi conferido. `auditar` mantém o parâmetro opcional `bundle_text` (T8 passo 1) para CLI/MCP passarem em memória no `deliberate` (onde o texto ainda existe).

- [ ] **Passo 2: Checagens offline (seção 22)**
  Termo presente só no bundle → não sinalizado; termo ausente de tudo → sinalizado (fixture espelhando seção 14). E2E da flag: registro fixture com `bundle_sha256` correto + arquivo bundle → termos do bundle não sinalizados e sem aviso; arquivo com conteúdo divergente do hash → exit 2 com erro nomeado; registro com `bundle_sha256` auditado sem `--bundle` → aviso "bundle nao conferido".
  Comando: `.venv/bin/python test_offline.py`
  Esperado: seção 22 verde; seção 14 inalterada.

- [ ] **Passo 3: Verificação**
  Critério: suite verde; comportamento do `council audit` sobre registros antigos (sem bundle) idêntico — sem `--bundle`, nenhuma mensagem nova aparece.

### Tarefa 9: CLI — `council deliberate`

**Artefatos:**
- Entrada: `council/cli.py` (`build_parser` em `cli.py:454-498`, estilo de `cmd_ask`)
- Saída: subcomando `deliberate`

- [ ] **Passo 1: Subcomando**
  `council deliberate QUESTION --profile NOME --bundle CAMINHO|- --ref SHA... [--json] [--members ...]`. `--profile` obrigatório (ask cobre o caso sem perfil). Bundle `-` lê stdin. `--ref` valida prefixo contra `runs/*.json` (padrão `judgment.carregar`) e registra os sha256 completos.

- [ ] **Passo 2: Erros nomeados e exit codes**
  Perfil inexistente → exit 2 com lista de perfis disponíveis; bundle ausente → exit 2; refs sem casamento → exit 2 com os prefixos problemáticos. Saída espelha `cmd_ask`: síntese/decisão em stdout, progresso em stderr, `--json` com registro completo.

- [ ] **Passo 3: Checagens offline (seção 23)**
  Com fixture TOML (perfil `questions` simplificado) e `Endpoint.chat` mockado: run completo gera registro com `profile_name`, decisão parseada, exit 0; os três erros nomeados → exit 2.
  Comando: `.venv/bin/python test_offline.py`
  Esperado: seção 23 verde.

- [ ] **Passo 4: Verificação**
  Critério: `./bin/council deliberate --help` mostra o subcomando; `./bin/council ask --help` inalterado.

### Tarefa 10: MCP — ferramenta `council_deliberate`

**Artefatos:**
- Entrada: `council/mcp_server.py` (`TOOLS` em `mcp_server.py:20-67`, `handle` em `mcp_server.py:148-181`)
- Saída: terceira ferramenta no servidor existente; servidor permanece stateless

- [ ] **Passo 1: Definição e handler**
  Schema: `{question, profile, bundle?, run_refs?, members?}` — todos os parâmetros chegam por chamada (estado zero entre calls). Handler monta `Deliberation`, roda, devolve JSON de texto com `profile`, `consensus`, `decision`, `sintese`, `dividido`, `avisos`, `sha256`, `registro` — mesmo padrão de `tool_debate` (`mcp_server.py:105-142`). Descrição da ferramenta orienta quando usar (decisão de continuidade, gate, rodada de grill) e quando não (pergunta trivial).

- [ ] **Passo 2: Checagens offline (seção 24)**
  `handle({"method": "tools/call", ...})` com chat mockado e `COUNCIL_CONFIG` fixture → resultado com `decision`; perfil desconhecido → `isError: true` com erro nomeado; segunda chamada não vê estado da primeira (sem globals mutáveis).
  Comando: `.venv/bin/python test_offline.py`
  Esperado: seção 24 verde.

- [ ] **Passo 3: Verificação**
  Critério: `tools/list` devolve 3 ferramentas; `council_ask`/`council_debate` com schemas inalterados.

### Tarefa 11: Perfis `continuation` e `grill` no `council.toml`

**Artefatos:**
- Entrada: `council.toml`, T2-T10 prontos
- Saída: dois perfis reais + `doctor` listando perfis

- [ ] **Passo 1: Perfil `continuation`**
  `chairman_mode = "decider"`, `stage1_format = "proposal"`. Papéis: continuador (otimiza progresso da trajetória), auditor (questiona se a evidência sustenta o que a execução afirma), guardião de escopo (questiona se o passo pertence ao plano) — um membro sem papel (contraponto neutro). Criteria (4): aderência à trajetória do plano; risco do passo e custo de reversão; dependências que bloqueia ou desbloqueia; sustentação na evidência do bundle.

- [ ] **Passo 2: Perfil `grill`**
  `chairman_mode = "synthesizer"`, `stage1_format = "questions"`. Papéis: quatro lentes de interrogatório distintas (cético, caçador de premissa load-bearing, mapeador de dependências, adversário de escopo). Criteria (4): load-bearingness (quanto a resposta muda o plano); decidibilidade (é decisão do operador, não fato buscável); especificidade (nomeia o trade-off); urgência (bloqueia a frontier atual?).

- [ ] **Passo 3: Checagens offline (seção 25)**
  `council.toml` real carrega com os dois perfis; validação da T2 passa; E2E offline de cada perfil com fake emitindo os formatos (`PROPOSAL:`, `QUESTIONS:`, cédulas, `DECISION:`) → registro completo com decisão/fronteira parseada; `divided=True` vira `status: "encalhado"` no decision do `continuation`.
  Comando: `.venv/bin/python test_offline.py`
  Esperado: seção 25 verde.

- [ ] **Passo 4: `doctor` lista perfis**
  Linha por perfil com modo e formato. `./bin/council doctor` → exit 0.

- [ ] **Passo 5: Verificação**
  Critério: suite verde; doctor limpo; `council.toml` comenta que cada questão ao conselho gasta 2 chamadas GLM (aviso existente em `council.toml:26-27` vale para os perfis).

### Tarefa 12: Skills consumidoras — `grill-the-council` (B) e `council-grill` (A)

**Artefatos:**
- Entrada: formato de `~/.agents/skills/grilling/SKILL.md` e `batch-grill-me/SKILL.md` (frontmatter, `disable-model-invocation: true`)
- Saída: `~/.agents/skills/grill-the-council/SKILL.md`, `~/.agents/skills/council-grill/SKILL.md`

- [ ] **Passo 1: `grill-the-council` (Direção B — zero mudança no council)**
  Skill que lê o registro mais recente (ou por sha) de `runs/`, extrai divergências (dispersão no consensus, avisos, acrescimos de audit), e entrevista o operador uma questão por vez, cada uma com resposta recomendada (contrato do grilling). Veredito A/B quando aplicável registrado via `council ab --choose` existente; decisões de aceitação de divergência em arquivo markdown da sessão. Frontmatter com `disable-model-invocation: true`.

- [ ] **Passo 2: `council-grill` (Direção A — dirige rodadas)**
  Skill que mantém estado em arquivo da sessão (plano + árvore de decisões + `run_refs` das rodadas), e por rodada: monta bundle, chama `council deliberate --profile grill` (CLI) ou `council_deliberate` (MCP quando o chamador é agente), apresenta a fronteira sintetizada com recomendações, coleta respostas do operador, recomputa a fronteira. Termina com fronteira vazia e documento de entendimento compartilhado referenciando os shas das rodadas. Batch (fronteira inteira por rodada), nunca uma questão por vez — custo de ~1 min por rodada de conselho. `disable-model-invocation: true`.

- [ ] **Passo 3: Verificação (manual, gate do operador)**
  Critério: uma sessão real de cada skill conduzida pelo operador sobre um plano pequeno; `grill-the-council` completa um julgamento; `council-grill` completa ≥ 2 rodadas com run_refs encadeados e termina com fronteira vazia. Skills são prompts — a verificação é a sessão, não um teste automático.

### Tarefa 13: Gate E2E, README e smoke run pago

**Artefatos:**
- Entrada: tudo acima
- Saída: README atualizado, smoke run real aprovado, gate final

- [ ] **Passo 1: Suite completa**
  Comando: `.venv/bin/python test_offline.py`
  Esperado: "todos os testes passaram", exit 0, seções 1-25 verdes (14 originais + golden + 10 novas). Nenhuma checagem original editada ou apagada.

- [ ] **Passo 2: Golden + doctor + registro**
  Comando: `./bin/council doctor && ./bin/council show`
  Esperado: doctor exit 0 com perfis listados; show lê o último registro sem erro.

- [ ] **Passo 3: README**
  Seções: `deliberate` no Uso (com os dois perfis), parágrafo em "O que ele faz diferente" (perfis, candidatos, decisão estruturada, run_refs, MCP stateless com estado no chamador), aviso de custo (2N+1 chamadas; GLM 2 por questão). Estilo do README atual: prosa curta, exemplos de comando.

- [ ] **Passo 4: Smoke run pago — GATE DO OPERADOR**
  Comando: `./bin/council ask "Em uma frase: por que Borda normalizado em vez de soma de pontos?"` e `./bin/council deliberate "Qual o proximo passo?" --profile continuation --bundle <resumo curto de um plano real> --json > smoke.json`
  Esperado: ask com síntese normal (regressão de comportamento); `smoke.json` parseia como JSON e contém `decision.status` ∈ {DECIDIDO, ENCALHADO} e `sha256` registrado (conferir com `python3 -c "import json; d=json.load(open('smoke.json')); assert d['decision']['status'] in ('DECIDIDO','ENCALHADO')"`). Aprovação explícita do operador antes de rodar (custo: ~9 chamadas na primeira + ~2N+1 na segunda, das quais 2 GLM por membro glm).

- [ ] **Passo 5: Verificação final**
  Critério: todos os passos acima verdes; `git status` mostra apenas os artefatos previstos; commits por tarefa no estilo do log.

---

## Análise por Eixo

### Eixo 1 — Verificação e dependências
Toda tarefa tem comando + esperado; o gate de conclusão é a T13 (suite 25 seções + golden diff vazio + doctor + smoke real pago com aprovação). Nenhuma dependência externa nova; a dependência compartilhada interna é `prompts.py`/`engine.py`, coberta pelo golden (T1) e pelas 14 seções originais intocadas. Não há build/sync/release — stdlib pura; o registro MCP no Claude Code não muda (mesmo launcher, ferramenta nova aparece por `tools/list`). Ordem de dependência: T1 → T2 → T3 → T5 → T6 → T7; T4 independente (paralelo); T8-T10 sobre T5-T7; T11 sobre T2+T9; T12 sobre T11/T10 (A) e nada (B); T13 por último.

### Eixo 2 — Manutenção futura
Risco de retrabalho vs. Fase 2 (rodadas): minimizado por desenho — rodadas ficam no chamador (skill) via `run_refs`, então a Fase 2 adiciona rodadas intra-run sem reescrever a Fase 1 (campos aditivos de novo). O seam load-bearing é o desacoplamento candidatos/autores (T6), desenhado uma vez e reusado pelos 16 casos catalogados. Contrato de registro muda aditivamente; custo de migração documentado: registros antigos leem igual (campos novos ausentes = neutros), `council show` reporta divergência de selo por design. Acoplamento reduzido: prompts deixam de hardcodar critérios; estágio 2 deixa de assumir candidato==membro. Risco residual: `Consensus.member` carregando id de candidato (nome de membro no default) é um naming compromise — aceito para manter o shape do registro, revisitável na Fase 2 se doer.

### Eixo 3 — Impacto arquitetural
Toca componentes compartilhados do repo: engine, prompts, config, CLI, servidor MCP — todos cobertos por teste. A decisão arquitetural do plano (MCP permanece stateless; estado de sessão vive no chamador) está documentada aqui e vai para o README na T13; o repo não tem convenção de ADR (a doc viva é o README + `docs/arquitetura.html`), então nenhum ADR é exigido — se o operador quiser formalizar, a skill `architecture` pode gerar um a partir deste plano. Alinhamento com roadmap: este plano é a Fase 1 exata discutida e acordada na conversa que o originou; Fases 2 e 3 explicitamente fora. Padrões existentes respeitados: endereçamento por sha (`judgment.py`), selo de produtor (`provenance.py`), parser tolerante que nunca inventa (`ranking.py`, `audit.py`), falha nomeada.

---

## Compliance Gate (pós-plano)

Padrões aplicados e rastreáveis:

- **intent-five-part-primitive**: seção Intent com os 5 campos preenchidos; nenhum campo vago. Cenários de falha (a)-(f) têm correspondente verificação (golden, validações, parser, gate de custo, aditividade, stateless).
- **constraint-budget-gate**: 6 constraints (dentro de 5-7), direcionais e incondicionais; excessos classificados e roteados — checks pós-execução foram para failure conditions (superfície do validador), não constraints; detalhes de implementação (campos de dataclass, regex) vivem nas tarefas, não nas constraints.
- **constraint-failure-decision-rule**: cada candidato a requisito foi classificado pela pergunta "saber isto mudaria como o construtor escreve o código?" — ex.: "golden diff vazio" não muda o código, só verifica → failure condition; "additive-only" muda decisões de desenho em cada tarefa → constraint.
- **measured-harness-evolution-lifecycle**: componentes novos classificados BUILD defensivo; comportamento atual em STABILIZE via golden; risco de retrabalho tratado no Eixo 2 com lifecycle explícito (Fase 2 não invalida Fase 1).
- **manual-brake-question-gate**: seção com as 3 perguntas respondidas antes da finalização; gates de parada reais no plano (T1 âncora, T13 aprovação de custo).
- Regras estruturais da skill: toda tarefa tem artefatos entrada/saída, passos com comando+esperado, critério de verificação; 3 eixos documentados; sem placeholders (nenhum TBD/TODO; formatos de prompt e schemas nomeados).

Desvio justificado: T12 (skills) tem verificação por sessão manual do operador em vez de comando automático — skills são prompts, não código; o critério é observável (sessão completa, julgamento gravado, rodadas encadeadas) mas não automatizável. É o mesmo tratamento que o repo dá ao `council ab` interativo.
