# council

Vários LLMs de provedores diferentes respondem a mesma pergunta, avaliam-se **às cegas**, e um
presidente sintetiza. CLI + servidor MCP. **Zero dependências** — só a stdlib do Python 3.11+.

Derivado do `llm-council` do Karpathy, com as correções que a versão original não tem: cegamento
que de fato cega, agregação por Borda em vez de ranking descartado, e falha nunca silenciosa.

## Uso

```bash
cp .env.example .env      # preencha OPENAI_API_KEY / DEEPSEEK_API_KEY / ZAI_API_KEY
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

### Como MCP no Claude Code

```bash
claude mcp add council -- python3 -m council.mcp_server
```

Expõe `council_ask` (só a síntese) e `council_debate` (respostas, consenso, divergências).
Rode a partir de `~/llm-council`, ou aponte `COUNCIL_CONFIG` para o `council.toml`.

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

**Registro** — cada execução vira `runs/<data>-<sha>.json` com prompts, respostas, cédulas, mapa de
rótulos, seed e `sha256` do registro. Fixe `seed` no TOML para reproduzir uma rodada.

**Falhas** — provedor que cai vira aviso nomeado com o motivo, nunca um silêncio que parece consenso.

## Configuração

Tudo em `council.toml`: provedores (qualquer endpoint OpenAI-compatível), roster, presidente e
ajustes. `params` por conselheiro passa campos extras direto no payload. Chaves só via `.env` ou
ambiente — nenhum valor é impresso em lugar nenhum.

## Testes

```bash
python3 test_offline.py    # ponta a ponta, sem rede
```
