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

    print("10) adaptador Anthropic (Messages API)")
    ep = AnthropicEndpoint("anthropic", "https://api.anthropic.com", "chave-falsa")
    h = ep._headers()
    check("x-api-key" in h and "Authorization" not in h, "usa x-api-key, nao Bearer")
    check(h.get("anthropic-version") == "2023-06-01", "manda anthropic-version")
    pay = ep._payload("claude-opus-5",
                      [{"role": "system", "content": "SYS"}, {"role": "user", "content": "oi"}],
                      4096, 0.3, None)
    check("temperature" not in pay, "NAO manda temperature (Opus 5 devolve 400 se vier)")
    check(pay.get("max_tokens") == 4096, "max_tokens presente (obrigatorio na Messages API)")
    check(pay.get("system") == "SYS" and len(pay["messages"]) == 1,
          "system sai do array de mensagens para o campo proprio")
    pay2 = ep._payload("claude-opus-5", [{"role": "user", "content": "oi"}], 4096, 0.3,
                       {"temperature": 1.0})
    check(pay2.get("temperature") == 1.0, "temperature entra se o operador pedir em [params]")

    corpo = {"content": [{"type": "thinking", "thinking": "hmm"},
                         {"type": "text", "text": "resposta"}],
             "usage": {"input_tokens": 7, "output_tokens": 3}, "stop_reason": "end_turn"}
    r = AnthropicEndpoint._parse_anthropic(corpo, 0.0, 1)
    check(r.ok and r.content == "resposta", "extrai so o bloco de texto")
    check(r.reasoning == "hmm", "guarda o thinking separado, fora da resposta")
    check(r.usage.prompt_tokens == 7 and r.usage.completion_tokens == 3, "mapeia input/output_tokens")
    rec_ = AnthropicEndpoint._parse_anthropic(
        {"stop_reason": "refusal", "stop_details": {"category": "cyber", "explanation": "nao"},
         "content": [], "usage": {}}, 0.0, 1)
    check(not rec_.ok and "recusa" in rec_.error, f"recusa (HTTP 200) vira falha explicita: {rec_.error}")

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
