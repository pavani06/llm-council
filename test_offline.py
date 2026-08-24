"""Teste ponta a ponta sem rede: substitui o provedor por respostas sinteticas.
Valida cegamento, auto-exclusao, embaralhamento, parsing de cedula, Borda e registro."""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from council import config as cfgmod
from council.engine import Council, save_run
from council.providers import AnthropicEndpoint, Endpoint, Reply, Usage
from council.ranking import parse_ballot

FALHAS = []


def check(cond, msg):
    print(("  ok    " if cond else "  FALHA ") + msg)
    if not cond:
        FALHAS.append(msg)


RESPOSTAS = {
    "gpt-5.6-terra": "Resposta do GPT: use indice parcial.",
    "deepseek-v4-pro": "Resposta do DeepSeek: use indice parcial e VACUUM.",
    "glm-5.3": "Resposta do GLM: reescreva a query.",
    "claude-opus-5": "Resposta do Claude: meça antes com EXPLAIN ANALYZE.",
}

VISTOS = []


def fake_chat(self, model, messages, **kw):
    prompt = messages[0]["content"]
    VISTOS.append((model, prompt))
    if "FINAL RANKING" in prompt:
        labels = sorted(set(re.findall(r"### Resposta ([A-Z])", prompt)))
        verd = "\n".join(f"{l} | forte de {l} | fraco de {l}" for l in labels)
        rank = "\n".join(f"{i + 1}. {l}" for i, l in enumerate(labels))
        return Reply(ok=True, content=f"analise\n\nVERDICTS:\n{verd}\n\nFINAL RANKING:\n{rank}",
                     usage=Usage(10, 10))
    if "preside um conselho" in prompt:
        return Reply(ok=True, content="SINTESE FINAL", usage=Usage(50, 20))
    return Reply(ok=True, content=RESPOSTAS.get(model, "?"), usage=Usage(5, 5))


def main():
    Endpoint.chat = fake_chat
    AnthropicEndpoint.chat = fake_chat  # senao 'claude' sairia para a rede
    cfg = cfgmod.load(Path(__file__).parent / "council.toml")
    cfg.has_key = lambda p: True

    print("1) execucao completa")
    rec = Council(cfg).run("Como acelerar esta query?")
    check(rec.synthesis.get("content") == "SINTESE FINAL", "estagio 3 sintetizou")
    n = len(cfg.members)
    check(len(rec.stage1) == n, f"{n} respostas no estagio 1 (foi {len(rec.stage1)})")
    check(len(rec.stage2) == n, f"{n} cedulas no estagio 2 (foi {len(rec.stage2)})")

    print("2) auto-exclusao")
    for b in rec.stage2:
        check(b["ranker"] not in b["order_members"],
              f"{b['ranker']} fora da propria cedula ({b['order_members']})")
        check(len(b["label_to_member"]) == n - 1,
              f"{b['ranker']} avaliou {n - 1} candidatos (foi {len(b['label_to_member'])})")

    print("3) cegamento no estagio 2")
    for model, prompt in VISTOS:
        if "FINAL RANKING" not in prompt:
            continue
        vazou = [t for t in ("GPT", "DeepSeek", "GLM", "Claude", "gpt-5.6", "deepseek-v4", "glm-5.3", "claude-opus") if t in prompt]
        check(not vazou, f"prompt de ranking sem marca (vazou: {vazou})")
        check("[modelo]" in prompt, "autoidentificacao foi mascarada no prompt de ranking")

    print("4) Borda balanceado")
    por_membro = {c["member"]: c["ballots"] for c in rec.consensus}
    check(len(set(por_membro.values())) == 1, f"mesmo numero de cedulas por resposta: {por_membro}")
    check(all(0.0 <= c["score"] <= 1.0 for c in rec.consensus), "scores normalizados 0..1")

    print("5) presidente cego")
    chair = [p for m, p in VISTOS if "preside um conselho" in p][0]
    vazou = [t for t in ("gpt-5.6", "deepseek-v4", "glm-5.3", "claude-opus") if t in chair]
    check(not vazou, f"prompt do presidente sem marca (vazou: {vazou})")
    check("consenso" in chair, "presidente recebeu tabela de consenso agregada")
    check("FINAL RANKING" not in chair, "presidente NAO recebeu texto cru de ranking")

    print("6) registro com sha256")
    out = save_run(rec, Path("/tmp/council-test-runs"))
    data = json.loads(out.read_text())
    check(len(data["sha256"]) == 64, "sha256 gravado")
    check(data["question"] == "Como acelerar esta query?", "pergunta preservada")

    print("7) parsing de cedula")
    o, v, e = parse_ballot("bla\nFINAL RANKING:\n1. Response B\n2. A\n3. C", ["A", "B", "C"])
    check(o == ["B", "A", "C"], f"aceita 'Response B' e 'A' (foi {o})")
    o, v, e = parse_ballot("sem ranking nenhum", ["A", "B"])
    check(o == [] and bool(e), "cedula ilegivel rejeitada, nao inventada")
    o, v, e = parse_ballot("FINAL RANKING:\n1. A", ["A", "B", "C"])
    check(o == ["A", "B", "C"] and "parcial" in e, f"cedula parcial sinalizada ({e})")

    # formatos que modelo real produz — o descarte da cedula do deepseek na primeira
    # rodada ao vivo veio daqui, nao de erro do modelo.
    reais = [
        ("negrito + portugues", "FINAL RANKING:\n1. **Resposta B**\n2. **Resposta A**\n3. **Resposta C**", ["B", "A", "C"]),
        ("cabecalho traduzido", "CLASSIFICACAO FINAL:\n1. Resposta C\n2. Resposta B\n3. Resposta A", ["C", "B", "A"]),
        ("cabecalho em negrito", "**FINAL RANKING:**\n1. C\n2. B\n3. A", ["C", "B", "A"]),
        ("rotulo minusculo", "FINAL RANKING:\n1. b\n2. c\n3. a", ["B", "C", "A"]),
        ("parenteses", "FINAL RANKING:\n1) A\n2) C\n3) B", ["A", "C", "B"]),
    ]
    for nome, txt, esperado in reais:
        o, v, e = parse_ballot(txt, ["A", "B", "C"])
        check(o == esperado, f"{nome}: {o} (esperado {esperado})")
    o, v, e = parse_ballot("VEREDITOS:\nA | forte | fraco\n\nFINAL RANKING:\n1. A\n2. B", ["A", "B"])
    check(v.get("A") == ("forte", "fraco"), f"veredictos com cabecalho traduzido ({v})")

    print("8) mapas de rotulo por avaliador")
    for b in rec.stage2:
        print(f"        {b['ranker']:<10} {b['label_to_member']}")

    print("8b) scrub nao apaga termo que a propria pergunta usa")
    from council.ranking import identity_terms, scrub_identity
    from council.config import Member
    membros = [Member("gpt", "openai", "gpt-5.6-terra")]
    termos = identity_terms(membros)
    t1, h1 = scrub_identity("O GPT sugere indice.", termos, "Como acelerar a query?")
    check("[modelo]" in t1 and "GPT" not in t1, f"mascara quando a pergunta nao cita ({t1})")
    t2, h2 = scrub_identity("O GPT sugere indice.", termos, "O GPT e melhor que o Claude?")
    check("GPT" in t2, f"preserva termo citado na pergunta ({t2})")
    t3, _ = scrub_identity("GPT-5.6 e bom", termos, "qualquer coisa")
    check("GPT" not in t3, f"pega o id do modelo tambem ({t3})")

    print("9) falha de conselheiro nao derruba a execucao")

    def chat_com_falha(self, model, messages, **kw):
        p = messages[0]["content"]
        if model == "glm-5.3" and "FINAL RANKING" not in p and "preside" not in p:
            return Reply(ok=False, error="429 rate limit")
        return fake_chat(self, model, messages, **kw)

    Endpoint.chat = chat_com_falha
    AnthropicEndpoint.chat = chat_com_falha
    rec2 = Council(cfg).run("outra pergunta")
    check(rec2.synthesis.get("ok"), "sintese ocorre com 1 conselheiro fora")
    check(any("glm" in w and "429" in w for w in rec2.warnings),
          f"falha reportada: {rec2.warnings}")
    restantes = len([x for x in rec2.stage1 if x.get("ok")])
    if restantes >= 3:
        check(len(rec2.stage2) == restantes,
              f"com {restantes} respostas o estagio 2 segue rodando ({len(rec2.stage2)} cedulas)")
        check(all(len(b["label_to_member"]) == restantes - 1 for b in rec2.stage2),
              "cedulas reduzidas ao conjunto que respondeu")
    else:
        check(any("estagio 2 pulado" in w for w in rec2.warnings),
              f"com {restantes} respostas o estagio 2 e pulado explicitamente")

    # e o limiar em si, testado direto: 2 respostas validas -> estagio 2 pulado
    cfg_min = cfgmod.load(Path(__file__).parent / "council.toml")
    cfg_min.has_key = lambda p: True
    cfg_min.members = cfg_min.members[:2]
    rec3 = Council(cfg_min).run("pergunta curta")
    check(any("estagio 2 pulado" in w for w in rec3.warnings),
          f"limiar: com 2 conselheiros o estagio 2 e pulado ({rec3.warnings})")

    print("10) adaptador Anthropic (SDK oficial)")
    from types import SimpleNamespace as NS

    ep = AnthropicEndpoint("anthropic", "https://api.anthropic.com", "chave-falsa")
    kw = ep._build("claude-opus-5",
                   [{"role": "system", "content": "SYS"}, {"role": "user", "content": "oi"}],
                   4096, None)
    check("temperature" not in kw, "NAO manda temperature (Opus 5 devolve 400 se vier)")
    check("thinking" not in kw, "NAO manda thinking (omitir = adaptativo no Opus 5)")
    check(kw.get("max_tokens") == 4096, "max_tokens presente (obrigatorio na Messages API)")
    check(kw.get("system") == "SYS" and len(kw["messages"]) == 1,
          "system sai do array de mensagens para o campo proprio")
    kw2 = ep._build("claude-opus-5", [{"role": "user", "content": "oi"}], 4096,
                    {"temperature": 1.0, "thinking": {"type": "adaptive"}})
    check(kw2.get("temperature") == 1.0 and kw2.get("thinking"),
          "temperature/thinking entram se o operador pedir em [params]")

    resp = NS(content=[NS(type="thinking", thinking="hmm"), NS(type="text", text="resposta")],
              usage=NS(input_tokens=7, output_tokens=3), stop_reason="end_turn",
              _request_id="req_123")
    r = AnthropicEndpoint._parse_sdk(resp, 0.0)
    check(r.ok and r.content == "resposta", "extrai so o bloco de texto")
    check(r.reasoning == "hmm", "guarda o thinking separado, fora da resposta")
    check(r.usage.prompt_tokens == 7 and r.usage.completion_tokens == 3, "mapeia input/output_tokens")
    check(r.request_id == "req_123", "guarda o request_id para suporte")

    recusa = AnthropicEndpoint._parse_sdk(
        NS(content=[], usage=NS(input_tokens=1, output_tokens=0), stop_reason="refusal",
           stop_details=NS(category="cyber", explanation="nao"), _request_id=""), 0.0)
    check(not recusa.ok and "recusa" in recusa.error,
          f"recusa (sucesso HTTP) vira falha explicita: {recusa.error}")

    trunc = AnthropicEndpoint._parse_sdk(
        NS(content=[NS(type="text", text="parcial")], usage=NS(input_tokens=1, output_tokens=9),
           stop_reason="max_tokens", _request_id=""), 0.0)
    check(trunc.ok and trunc.truncated,
          "stop_reason='max_tokens' e reconhecido como truncamento (nao 'length')")
    check(Reply(ok=True, finish="length").truncated, "'length' segue valendo nos OpenAI-compativeis")
    check(not Reply(ok=True, finish="stop").truncated, "'stop' nao e truncamento")

    try:
        import anthropic as _a
        cli = ep._client(30.0, 2)
        check(type(cli).__name__ == "Anthropic", "monta o cliente do SDK oficial")
        check(cli.api_key == "chave-falsa", "chave chega ao cliente")
        check(AnthropicEndpoint._describe(_a.NotFoundError.__new__(_a.NotFoundError)).startswith("modelo"),
              "erros tipados viram mensagem especifica")
    except ImportError:
        print("  pulado  SDK anthropic ausente neste interpretador (rode com .venv/bin/python)")

    print("11) declaracao de parametros por provedor")
    capturado = {}

    class FakeResp:
        @staticmethod
        def read():
            return b'{"choices":[{"message":{"content":"ok"},"finish_reason":"stop"}],"usage":{}}'

    def fake_request(self, path, payload, timeout, method="POST"):
        capturado.clear()
        capturado.update(payload or {})
        return FakeResp()

    orig = Endpoint._request
    Endpoint._request = fake_request
    try:
        oai = Endpoint("openai", "https://x/v1", "k",
                       max_tokens_field="max_completion_tokens", unsupported=("temperature",))
        r = oai.chat("gpt-5.6-terra", [{"role": "user", "content": "oi"}],
                     temperature=0.3, max_tokens=50000, retries=0)
        check(r.ok, "chamada monta e responde")
        check("max_tokens" not in capturado, "nao manda max_tokens onde o modelo o recusa")
        check(capturado.get("max_completion_tokens") == 50000,
              f"usa max_completion_tokens ({capturado.get('max_completion_tokens')})")
        check("temperature" not in capturado, "remove temperature declarada como nao suportada")

        padrao = Endpoint("deepseek", "https://y/v1", "k")
        padrao.chat("m", [{"role": "user", "content": "oi"}], temperature=0.3, max_tokens=50000, retries=0)
        check(capturado.get("max_tokens") == 50000, "provedor sem declaracao segue com max_tokens")
        check(capturado.get("temperature") == 0.3, "e mantem temperature")
    finally:
        Endpoint._request = orig

    ant = AnthropicEndpoint("anthropic", "https://api.anthropic.com", "k", unsupported=("temperature",))
    kw = ant._build("claude-opus-5", [{"role": "user", "content": "oi"}], 50000,
                    {"temperature": 0.5})
    check("temperature" not in kw, "adaptador anthropic tambem honra 'unsupported'")
    check(kw.get("max_tokens") == 50000, "teto de 50k chega ao anthropic")

    print()
    if FALHAS:
        print(f"{len(FALHAS)} FALHA(S):")
        for f in FALHAS:
            print("  - " + f)
        return 1
    print("todos os testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
