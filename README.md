# council

Vários LLMs de provedores diferentes respondem a mesma pergunta, avaliam-se **às cegas**, e um
presidente sintetiza. CLI + servidor MCP.

Stdlib pura para OpenAI, DeepSeek e z.ai. O provedor Anthropic usa o **SDK oficial**
(`anthropic`) — única dependência, e só ela precisa do venv.

Conselho atual: `gpt-5.6-terra`, `deepseek-v4-pro`, `claude-opus-5`, `glm-5.3` (coding plan);
presidente `gpt-5.6-sol`, de fora do conselho.

Derivado do `llm-council` do Karpathy, com as correções que a versão original não tem: cegamento
que de fato cega, agregação por Borda em vez de ranking descartado, e falha nunca silenciosa.

## Em linguagem de negócio

**Para que serve.** Decisão importante de plano costuma ouvir uma só voz — o executor de
plantão. O council coloca quatro modelos de IA de quatro fornecedores diferentes (OpenAI,
DeepSeek, Anthropic, z.ai) para responder à mesma pergunta, avaliar as respostas uns dos
outros **às cegas** — ninguém sabe de quem é o texto que está julgando — e entregar uma
decisão documentada: o placar, quem discorda e por quê, e o grau de confiança.

**O que você recebe.** Um registro permanente e auditável de cada deliberação: a pergunta, as
respostas completas, as notas que cada avaliador deu às respostas dos outros, o resultado
agregado e — quando o pedido é "decida" — uma decisão estruturada: `DECIDIDO` ou
`ENCALHADO`, a escolha, a confiança, as dissidências e os fundamentos. Quando o conselho não
converge, ele **declara** que está dividido em vez de fabricar consenso.

**Casos de uso reais** (os registros existem e são auditáveis):
- *"Qual é o próximo passo deste plano?"* — decide a próxima tarefa a partir do relatório
  da execução anterior (`deliberate --profile continuation`);
- *"Interrogue este plano antes de comprometer código"* — devolve as perguntas cujas
  respostas mudariam o plano, ordenadas por quanto mudariam (`deliberate --profile grill`);
- *"O que a síntese afirmou que ninguém sustentou?"* — auditoria offline que aponta
  afirmações sem lastro nas respostas (`audit`).

**Quanto custa.** Cada pergunta ao conselho: ~9 chamadas de API, 2 delas na cota do plano
GLM. Antes de gastar, `council cost --estimate` prevê as chamadas e os tokens da próxima
deliberação; depois, `council cost` mostra o acumulado por fornecedor, direto dos registros.
Ler, auditar e julgar é grátis e offline.

**Por que confiar.** Ninguém avalia o próprio texto; a identidade do autor é mascarada antes
do julgamento; a ordem dos candidatos é sorteada por avaliador; cada registro é selado — diz
que código, que configuração e que evidência produziram aquele resultado, e nunca é
reescrito; a síntese do presidente é auditável contra o que os membros de fato disseram. E
se a execução morre no meio, o que já foi pago fica salvo como parcial marcado — nada
desaparece em silêncio.

## Guia passo a passo

Uma volta completa pelo conselho, do setup ao encadeamento de deliberações. Os exemplos
são reais — vêm das sessões que estreiaram cada comando; os shas existem em `runs/`.

**1. Setup e sanidade** (uma vez):

```bash
python3 -m venv --without-pip .venv
curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env      # suas chaves
./bin/council doctor      # chaves, roster, perfis e o selo atual — tudo verde antes de gastar
```

**2. Primeira pergunta** (barata, ~9 chamadas): uma pergunta de resposta curta prova o
pipeline inteiro sem custo de teto:

```bash
./bin/council ask "Em uma frase: por que Borda normalizado em vez de soma de pontos?"
# → "Porque o Borda normalizado põe pontuações em uma escala comum…" (registro dcaefacfad61)
```

**3. Ler o registro, julgar às cegas:** o `ask` salva tudo em `runs/`. Confira se o voto
dos pares acerta o que você escolheria sem ver autoria:

```bash
./bin/council show dcaefacfad61    # consenso, cédulas, síntese, selo do produtor
./bin/council ab 74f19a --par gpt,glm   # duas respostas, sem autoria, ordem sorteada
./bin/council agreement            # acumula suas escolhas contra o Borda
```

**4. Auditar a síntese** (offline e grátis): o que o presidente afirmou que nenhuma
resposta sustentava:

```bash
./bin/council audit 74f19a         # termos específicos ausentes de todas as respostas
```

**5. Deliberar o próximo passo de um plano** (~9 chamadas, 2 GLM): acabou de executar
uma issue e quer decidir o que vem antes de commitar? Escreva o estado em um arquivo
— isso é o bundle — e pergunte ao `continuation`:

```bash
# estado-do-plano.md: onde o plano está, o que a execução entregou, o que pendura
./bin/council deliberate "Qual o proximo passo desta fase?" \
    --profile continuation --bundle estado-do-plano.md
# → [DECIDIDO] claude — confiança alta
#   dissidências: C e D defendem iniciar a Fase 2 antes da validação…
```

Com `--json`, o registro completo (decisão, candidatos, consensus, bundle selado) vai
para stdout. `ENCALHADO` em vez de `DECIDIDO` não é erro: é o conselho dividido se
declarando — trate como "suba ao operador".

**6. Auditar a deliberação contra a evidência** — a conferência do bundle é por sha256;
bundle de outra execução é recusado:

```bash
./bin/council audit 74f19a --bundle estado-do-plano.md
```

**7. Grilar um plano antes de comprometer código** (~9 chamadas por rodada): o perfil
`grill` produz questões ranqueadas por load-bearingness, com recomendações. Duas rodadas
reais do interrogatório que definiu o escopo da Fase 2:

```bash
./bin/council deliberate "Antes de desenhar a Fase 2, quais decisoes o operador precisa tomar?" \
    --profile grill --bundle escopo-fase2.md
# → registro e5957637d9ae: 26 questões em 7 seções

./bin/council deliberate "Quais sub-decisoes dentro de metrica, schema e sanitizacao ainda sao do operador?" \
    --profile grill --bundle escopo-fase2-r2.md --ref e5957637d9ae
# → registro 6656b23a66c7, encadeado à rodada anterior por run_refs
```

**8. Como MCP no Claude Code** (as mesmas três ferramentas, sem estado — a cadeia de
rodadas vive em quem chama):

```bash
claude mcp add council -- ~/llm-council/bin/council-mcp
# council_ask · council_debate · council_deliberate
```

Custo de referência: `ask` e `deliberate` ≈ 2N+1 chamadas (~9 com o roster atual), das
quais 2 GLM por questão saem da cota trimestral do coding plan. O gasto não precisa ser
contado à mão: `council cost` acumula o que já foi pago por provedor/modelo direto dos
registros (final e parcial separados; registro antigo com nota nomeada de subcontagem) e
`council cost --estimate --profile continuation` é o pré-voo da próxima deliberação —
chamadas por provedor pela aritmética da config, tokens pelas medianas do histórico;
sem histórico, exit 3 nomeado e nenhum número inventado. `audit`, `show`, `ab`,
`agreement` e `cost` são offline e grátis. O mapa completo da arquitetura, com os dois
caminhos (ask e deliberação), está em `docs/arquitetura.html`; o contrato do experimento
1-vs-N que abre a Fase 2 está selado em `docs/prereg/2026-08-27-experimento-1vsN.md`
(tag `prereg-1vsN`).

## Uso

```bash
# venv só por causa do SDK anthropic (o Debian aqui não traz ensurepip):
python3 -m venv --without-pip .venv
curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python
.venv/bin/python -m pip install -r requirements.txt

cp .env.example .env      # OPENAI_API_KEY / DEEPSEEK_API_KEY / ZAI_API_KEY / CLAUDE_API_KEY
./bin/council doctor      # confere chaves, roster e coerência
./bin/council models      # ids reais da sua conta em cada provedor
./bin/council ask "sua pergunta"
```

O progresso vai para stderr, a resposta final para stdout — então `council ask "..." > resposta.md`
salva só a resposta.

```bash
./bin/council ask "..." --json        # registro completo
./bin/council ask "..." --no-rank     # pula o estágio 2 (mais barato)
./bin/council ask "..." --members gpt,glm
./bin/council show                    # último registro salvo
```

### Deliberação com perfil

Além de perguntar, o conselho delibera: conselheiros com papéis, um bundle de
evidência, candidatos avaliados às cegas e uma decisão estruturada. Perfis vivem em
`[profiles.<nome>]` no `council.toml` — hoje `continuation` (decide o próximo passo
de um plano após uma execução) e `grill` (produz questões ranqueadas por
load-bearingness).

```bash
./bin/council deliberate "qual o proximo passo?" \
    --profile continuation --bundle resumo-da-execucao.md --json
./bin/council deliberate "teste deste plano" --profile grill --bundle plano.md
./bin/council audit --bundle resumo-da-execucao.md   # conferência do bundle por sha256
```

`--ref <sha>` encadeia deliberações (a anterior entra no registro pelo sha256); o
servidor MCP expõe `council_deliberate` com o mesmo contrato, sem estado — a cadeia
vive no chamador. Custo: ~2N+1 chamadas por deliberação; as 2 GLM por questão valem
para os perfis também.

### Auditoria da síntese

O presidente devolve texto novo. Nada verificava que ele só afirma o que os membros sustentaram.
`audit` procura na síntese os **termos específicos** — número, identificador, sigla, nome próprio —
que não aparecem em resposta nenhuma:

```bash
./bin/council audit                   # último registro, varredura offline e grátis
./bin/council audit 112012 --verify   # confere os candidatos com um conselheiro (1 chamada)
```

Duas ressalvas que definem o que isso é. **Não pontua sobreposição de palavras:** síntese boa
parafraseia, e "palavra longa ausente" sinalizava 185 de 188 termos em teste contra os registros
reais — puro ruído. Calibrado, fica em ~2% das frases, e o que sobra são identificadores de verdade.
E **acréscimo nem sempre é falha:** o próprio prompt do presidente manda corrigir o conselho quando
ele erra em bloco. O comando mostra o que ele pôs por conta própria; quem julga é você.

### Julgamento cego seu

O conselho afirma qualidade por voto dos pares. Isso nunca foi conferido contra o único juiz que
decide. `ab` mostra duas respostas de um registro **sem autoria, sem consenso e em ordem sorteada**,
e só revela depois que você escolhe:

```bash
./bin/council ab                      # último registro, os dois primeiros do consenso
./bin/council ab 5f8596 --par gpt,glm # registro e par específicos
./bin/council agreement --list        # quantas vezes você e o Borda concordaram
```

O veredito vai para `judgments/<sha12>-ab.json`, endereçado ao `sha256` do registro — que **não é
alterado**. Julgar de novo o mesmo registro exige `--redo`, e o veredito anterior fica encadeado
dentro do novo: um julgamento seu nunca some em silêncio.

### Como MCP no Claude Code

```bash
claude mcp add council -- ~/llm-council/bin/council-mcp
```

Expõe `council_ask` (só a síntese) e `council_debate` (respostas, consenso, divergências).
O launcher resolve cwd e interpretador sozinho, então pode ser chamado de qualquer lugar.

## O que ele faz diferente

**Estágio 1** — todos respondem em paralelo, sem se ver.

**Estágio 2** — cada um avalia os outros, e cegamento aqui é levado a sério:
- ninguém avalia a própria resposta (`exclude_self_rank`);
- os rótulos A/B/C são embaralhados **por avaliador** — sem isso todos veem a mesma ordem e o viés
  de posição contamina o resultado;
- autoidentificação no texto ("como modelo da X…") é mascarada antes do julgamento — senão o
  cegamento é ficção. Termo que aparece na sua pergunta **não** é mascarado: cegar não pode custar
  o assunto.

**Agregação** — Borda normalizado (0..1). Com auto-exclusão toda resposta aparece em N−1 cédulas do
mesmo tamanho, então a comparação é balanceada. Também sai a dispersão das posições: alta = conselho
dividido, e isso é dito na saída em vez de escondido atrás de uma síntese confiante.

**Estágio 3** — o presidente fica **fora** do conselho e recebe as respostas + a tabela agregada com
o ponto forte e a falha que cada avaliador apontou — não o texto cru dos rankings.

**Registro** — cada execução vira `runs/<data>-<sha>.json` com respostas, cédulas, mapa de rótulos,
seed, `sha256` do registro e o **selo do produtor**: commit do council, se a árvore estava suja,
hash de todo o fonte do pacote e hash da config resolvida. `council show` compara o selo com a
árvore atual e avisa quando divergem — sem isso, um registro antigo é ininterpretável depois de
qualquer edição em `prompts.py` ou no roster. Os prompts não são guardados em texto: são
reconstituíveis a partir do código selado mais as respostas. A execução sobrevive à morte do
processo: checkpoint por limite de estágio, interrupção (Ctrl-C/SIGTERM) grava um **parcial
marcado** com o que já foi pago e sai com exit 130 — e os leitores deixam parciais de fora. O
registro também carrega custo por estágio (`usage_by_stage`, `usage`/`latency_s` por cédula) e,
no decisor cego, o mapa `decision_aliases` (rótulo → id real). Campos novos são apenas aditivos;
registros antigos jamais são reescritos.

**Deliberação** — um perfil dá papel a cada conselheiro, bundle de evidência à rodada e formato
ao output: propostas ou questões viram candidatos destilados, ranqueados às cegas como sempre;
o presidente pode decidir em vez de sintetizar (`DECIDIDO | escolha | confiança | dissidências |
fundamentos`, com a decisão ilegível virando aviso nomeado, nunca invenção), e, com o conselho
dividido, o decisor é instruído a declarar `ENCALHADO` em vez de forjar vitória — a instrução
está no prompt; quem confere o resultado é você. O bundle entra no registro como sha256;
deliberações anteriores encadeiam por `run_refs`; no decisor cego os candidatos chegam ao
presidente como `Candidato A/B/...` e a escolha volta traduzida para o id real — e o mapa
rótulo → id fica gravado no registro (`decision_aliases`). O servidor MCP
segue sem estado — a cadeia de rodadas vive no chamador.

**Falhas** — provedor que cai vira aviso nomeado com o motivo, nunca um silêncio que parece consenso.
Truncamento por `max_tokens` é detectado e nomeado: modelo de raciocínio (DeepSeek v4-pro, medido em
4597 tokens de saída só para uma cédula) estoura teto baixo e a cédula some — sem essa instrumentação
isso se disfarça de "o modelo não seguiu o formato". Ajuste o teto por conselheiro em `params`.

## Configuração

Tudo em `council.toml`: provedores, roster, presidente, perfis de deliberação e ajustes. Cada provedor declara `api`:
`openai` (default — vale para OpenAI, DeepSeek e z.ai, todos por stdlib) ou `anthropic`, que passa
pelo SDK oficial. O SDK cuida de auth, versão de API, retries e tipos de erro; o adaptador cuida do
que ele não tem como adivinhar: **`temperature` fica fora** (o Opus 5 devolve 400 se ela vier),
`thinking` fica omitido de propósito (omitir já é adaptativo no Opus 5, e `{type:"adaptive"}`
quebraria num Haiku 4.5 — quem for para Opus 4.8/4.7 declara em `params`), blocos `thinking` não
entram na resposta, `stop_reason: "refusal"` vira falha explícita, e truncamento aqui é
`stop_reason: "max_tokens"`, não `"length"`. `params` por conselheiro passa campos extras direto no payload. Chaves só via `.env` ou ambiente —
nenhum valor é impresso em lugar nenhum.

**Pegadinha do ambiente:** um `export OPENAI_API_KEY=` vazio no `.bashrc` mascarava a chave real do
`.env`. O loader agora sobrescreve variável existente que esteja em branco — variável vazia não é
configuração, é ruído.

## Testes

```bash
.venv/bin/python test_offline.py   # ponta a ponta, sem rede (393 checagens)
```

Roda também no python do sistema; as checagens que exigem o SDK são puladas com aviso.
O workflow `offline` do GitHub Actions roda esta suíte a cada push e pull request.
