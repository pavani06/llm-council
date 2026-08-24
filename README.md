# council

Vários LLMs de provedores diferentes respondem a mesma pergunta, avaliam-se **às cegas**, e um
presidente sintetiza. CLI + servidor MCP.

Stdlib pura para OpenAI, DeepSeek e z.ai. O provedor Anthropic usa o **SDK oficial**
(`anthropic`) — única dependência, e só ela precisa do venv.

Conselho atual: `gpt-5.6-terra`, `deepseek-v4-pro`, `claude-opus-5`, `glm-5.3` (coding plan);
presidente `gpt-5.6-sol`, de fora do conselho.

Derivado do `llm-council` do Karpathy, com as correções que a versão original não tem: cegamento
que de fato cega, agregação por Borda em vez de ranking descartado, e falha nunca silenciosa.

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
reconstituíveis a partir do código selado mais as respostas.

**Falhas** — provedor que cai vira aviso nomeado com o motivo, nunca um silêncio que parece consenso.
Truncamento por `max_tokens` é detectado e nomeado: modelo de raciocínio (DeepSeek v4-pro, medido em
4597 tokens de saída só para uma cédula) estoura teto baixo e a cédula some — sem essa instrumentação
isso se disfarça de "o modelo não seguiu o formato". Ajuste o teto por conselheiro em `params`.

## Configuração

Tudo em `council.toml`: provedores, roster, presidente e ajustes. Cada provedor declara `api`:
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
.venv/bin/python test_offline.py   # ponta a ponta, sem rede (53+ checagens)
```

Roda também no python do sistema; as checagens que exigem o SDK são puladas com aviso.
