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

CHAT_REAL = Endpoint.chat          # guardado antes de qualquer monkeypatch
CHAT_REAL_ANT = AnthropicEndpoint.chat

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

    orig_req, orig_chat = Endpoint._request, Endpoint.chat
    Endpoint._request = fake_request
    Endpoint.chat = CHAT_REAL   # a secao 1 trocou por mock e nao restaurou
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
        Endpoint._request, Endpoint.chat = orig_req, orig_chat

    ant = AnthropicEndpoint("anthropic", "https://api.anthropic.com", "k", unsupported=("temperature",))
    kw = ant._build("claude-opus-5", [{"role": "user", "content": "oi"}], 50000,
                    {"temperature": 0.5})
    check("temperature" not in kw, "adaptador anthropic tambem honra 'unsupported'")
    check(kw.get("max_tokens") == 50000, "teto de 50k chega ao anthropic")

    print("12) selo do produtor")
    import hashlib, json as _json, os as _os
    from council import provenance as pv

    selo = pv.seal(cfg, "0.1.0")
    for campo in ("version", "python", "git_commit", "git_dirty",
                  "code_sha256", "config_sha256", "config_source", "config"):
        check(campo in selo, f"selo tem '{campo}'")
    check(len(selo["code_sha256"]) == 64, "code_sha256 e um sha256 completo")

    # nenhum VALOR de chave pode entrar no retrato — so o nome da variavel
    blob = _json.dumps(selo, ensure_ascii=False)
    vazou = []
    for nome, valor in _os.environ.items():
        if len(valor) >= 16 and ("KEY" in nome or "TOKEN" in nome or "SECRET" in nome):
            if valor in blob:
                vazou.append(nome)
    check(not vazou, f"nenhum valor de credencial no selo (vazou: {vazou})")
    check("CLAUDE_API_KEY" in blob or "api_key_env" in blob,
          "mas o NOME da variavel e preservado, que e o que interessa")

    # o retrato reflete a config RESOLVIDA, nao o arquivo
    import copy as _copy
    cfg_menor = _copy.copy(cfg)
    cfg_menor.members = cfg.members[:2]
    check(pv.config_digest(cfg_menor) != pv.config_digest(cfg),
          "mudar o roster (ex.: --members) muda o config_sha256")

    snap = pv.config_snapshot(cfg)
    check([m["name"] for m in snap["council"]] == [m.name for m in cfg.members],
          "retrato lista o roster em ordem")
    check("temperature" in snap["settings"], "retrato inclui os settings")

    # code_digest reage a edicao de qualquer fonte do pacote
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "a.py").write_text("x = 1")
        h1 = pv.code_digest(d)
        (d / "a.py").write_text("x = 2")
        h2 = pv.code_digest(d)
        (d / "b.py").write_text("y = 1")
        h3 = pv.code_digest(d)
        check(h1 != h2, "editar um fonte muda o code_sha256")
        check(h2 != h3, "acrescentar um fonte muda o code_sha256")

    check(pv.compare({"code_sha256": "0" * 64}) != [], "compare() acusa codigo divergente")
    check(pv.compare({"code_sha256": pv.code_digest(), "git_dirty": False}) == [],
          "compare() fica calado quando bate")
    check(any("SUJA" in d for d in pv.compare({"git_dirty": True})),
          "compare() acusa arvore suja na execucao")

    # o selo entra no registro E no sha256 dele
    check(rec.producer.get("code_sha256"), "execucao gravou o selo no registro")
    import dataclasses as _dc
    r2 = _dc.replace(rec, producer={**rec.producer, "code_sha256": "1" * 64})
    check(r2.digest() != rec.digest(), "mudar o selo muda o sha256 do registro")

    print("13) julgamento cego A/B do operador")
    import random as _rnd, shutil as _sh, tempfile as _tmp
    from council import judgment as jd

    rec_falso = {
        "sha256": "a" * 64,
        "question": "Como acelerar a query?",
        "members": [{"name": "gpt", "provider": "openai", "model": "gpt-5.6-terra"},
                    {"name": "claude", "provider": "anthropic", "model": "claude-opus-5"},
                    {"name": "glm", "provider": "zai", "model": "glm-5.3"}],
        "stage1": [
            {"name": "gpt", "ok": True, "content": "Eu, o ChatGPT da OpenAI, sugiro indice."},
            {"name": "claude", "ok": True, "content": "Como Claude, da Anthropic, sugiro EXPLAIN."},
            {"name": "glm", "ok": False, "content": ""},
        ],
        "consensus": [{"member": "claude", "score": 0.9, "ballots": 2},
                      {"member": "gpt", "score": 0.4, "ballots": 2},
                      {"member": "glm", "score": 0.0, "ballots": 0}],
    }

    a, b, motivo = jd.escolher_par(rec_falso)
    check((a, b) == ("claude", "gpt"), f"par padrao = os dois primeiros do consenso ({a},{b})")
    check("margem" in motivo, "e diz por que esse par")
    try:
        jd.escolher_par(rec_falso, "gpt,glm")
        check(False, "par com resposta invalida deveria ser recusado")
    except jd.SemPar as e:
        check("glm" in str(e), f"recusa par com resposta que falhou ({e})")

    ops, mapa = jd.cegar(rec_falso, ("gpt", "claude"), _rnd.Random(7))
    juntos = " ".join(o["texto"] for o in ops)
    check(not any(t in juntos for t in ("ChatGPT", "OpenAI", "Claude", "Anthropic")),
          "autoria mascarada no texto apresentado")
    check(juntos.count("[modelo]") >= 4, "a mascara de fato substituiu")
    check(sorted(mapa.values()) == ["claude", "gpt"], "mapa slot->autor cobre o par")
    ordens = {tuple(jd.cegar(rec_falso, ("gpt", "claude"), _rnd.Random(i))[1].values()) for i in range(30)}
    check(len(ordens) == 2, f"a ordem de apresentacao varia entre execucoes ({ordens})")

    check(jd.concorda(rec_falso, "claude", "gpt") is True, "concorda: escolheu o melhor do Borda")
    check(jd.concorda(rec_falso, "gpt", "claude") is False, "discorda: escolheu o preterido")
    check(jd.concorda(rec_falso, "gpt", "inexistente") is None, "sem consenso comparavel -> None")

    with _tmp.TemporaryDirectory() as td:
        base = Path(td)
        runs, vers = base / "runs", base / "judgments"
        runs.mkdir()
        arq = runs / "r.json"
        arq.write_text(json.dumps(rec_falso, ensure_ascii=False), encoding="utf-8")
        antes_bytes = arq.read_bytes()

        mapa2 = {"1": "gpt", "2": "claude"}
        dest, ver = jd.gravar(vers, arq, rec_falso, mapa2, "2", "escolhi pela clareza", {"code_sha256": "z"})
        check(dest.name == "a" * 12 + "-ab.json", f"veredito endereçado pelo sha do registro ({dest.name})")
        check(ver["escolhido"] == "claude" and ver["preterido"] == "gpt", "resolve slot -> autor")
        check(ver["concorda_com_borda"] is True, "computa concordancia com o Borda")
        check(ver["nota"] == "escolhi pela clareza", "guarda o verbatim do operador")
        check(len(ver["sha256"]) == 64, "veredito tem sha256 proprio")
        check(arq.read_bytes() == antes_bytes,
              "REGISTRO SELADO INTACTO — julgar nao altera o artefato julgado")

        try:
            jd.gravar(vers, arq, rec_falso, mapa2, "1", "mudei de ideia", {})
            check(False, "segundo veredito sem --redo deveria ser recusado")
        except jd.JaJulgado as e:
            check("--redo" in str(e), f"recusa sobrescrever julgamento em silencio ({str(e)[:60]}…)")

        dest2, ver2 = jd.gravar(vers, arq, rec_falso, mapa2, "1", "mudei de ideia", {}, refazer=True)
        check(ver2["substitui"] is not None, "com --redo, o veredito anterior fica encadeado")
        check(ver2["substitui"]["nota"] == "escolhi pela clareza", "e o anterior preserva o verbatim")

        r = jd.apurar(vers)
        check(r["total"] == 1 and r["decididos"] == 1, f"apuracao conta o veredito ({r['total']})")
        check(r["taxa"] == 0.0, f"escolha 1 (gpt) discorda do Borda -> taxa 0.0 ({r['taxa']})")
        _sh.rmtree(vers, ignore_errors=True)
        check(jd.apurar(vers)["taxa"] is None, "sem vereditos, taxa e None e nao zero")

    print("14) auditoria da sintese contra o conselho")
    from council import audit as ad

    t = ad.termos_especificos
    check("subject_key" in t("registra o subject_key na tabela"), "pega snake_case")
    check("SIREAD" in t("usa registros SIREAD nao bloqueantes"), "pega SIGLA")
    check("40001" in t("aborta com 40001"), "pega numero")
    check("`reopen_when`" not in str(t("o campo `reopen_when` decide")) or
          "reopen_when" in t("o campo `reopen_when` decide"), "pega crase sem as aspas")
    check("Postgres" in t("o motor Postgres faz isso"), "pega nome proprio no meio da frase")
    check("Comparado" not in t("Comparado a outros, isso e melhor"),
          "NAO pega capitalizada que abre a frase")
    check(not (t("## (b) Fragilidades e contradicoes") & {"Fragilidades"}),
          "NAO pega palavra apos marcador markdown (era falso positivo real)")
    check("verificado" not in t("o resultado foi verificado depois"),
          "NAO pega palavra longa comum — era 185 de 188 alarmes antes da calibragem")
    longo = "`" + "x" * 80 + "`"
    check(not any(len(x) > 60 for x in t(longo)),
          "descarta crase longa demais (artefato de frase cortada ao meio)")
    check("cliente_id" in t("```sql\nCREATE INDEX ON t (cliente_id);\n```"),
          "enxerga dentro de bloco cercado, pelo identificador")

    base = {
        "question": "Como acelerar a query no Postgres?",
        "stage1": [
            {"name": "a", "ok": True, "content": "Use indice parcial; o campo status ajuda."},
            {"name": "b", "ok": True, "content": "Considere VACUUM e o custo de escrita."},
        ],
        "synthesis": {"content": "Use indice parcial com status. Rode VACUUM."},
    }
    a1 = ad.auditar(base)
    check(a1.acrescimos == [], f"termo sustentado por alguma resposta nao e sinalizado ({a1.acrescimos})")
    check(a1.membros == ["a", "b"], "lista quem respondeu")

    base2 = dict(base, synthesis={"content": "Use indice parcial. Ative o flag deferred_write."})
    a2 = ad.auditar(base2)
    check(len(a2.acrescimos) == 1 and "deferred_write" in a2.acrescimos[0].termos,
          f"termo ausente de todas as respostas e sinalizado ({a2.acrescimos})")

    base3 = dict(base, synthesis={"content": "No Postgres, use indice parcial."})
    check(ad.auditar(base3).acrescimos == [],
          "termo que veio da PERGUNTA nao conta como acrescimo do presidente")

    check(ad.auditar({"stage1": [], "synthesis": {"content": "x"}}).erro,
          "registro sem respostas nao e auditavel")
    check(ad.auditar({"stage1": base["stage1"], "synthesis": {}}).erro,
          "registro sem sintese nao e auditavel")
    check(ad.auditar(base).limpo, "auditoria sem acrescimo e sem erro e 'limpa'")

    v = ad.parse_verificacao("bla\n\nVEREDITOS:\n1 | ACRESCIMO | ninguem citou\n2 | SUSTENTADA | fonte A", 2)
    check(v[1][0] == "ACRESCIMO" and v[2][0] == "SUSTENTADA", f"parseia os vereditos ({v})")
    check("ninguem citou" in v[1][1], "guarda o motivo")
    check(ad.parse_verificacao("resposta fora de formato", 2) == {},
          "formato quebrado devolve vazio, nao inventa veredito")
    check(ad.parse_verificacao("VEREDITOS:\n9 | ACRESCIMO | fora do intervalo", 2) == {},
          "ignora indice fora do intervalo")

    print("15) golden: prompts byte a byte")
    from pathlib import Path as _P
    from council.prompts import chairman_prompt as _chair
    from council.prompts import ranking_prompt as _rank
    from council.ranking import Consensus as _Cons

    # Entrada FIXA: qualquer edicao em prompts.py muda o render e o golden acusa.
    FIX_Q = "Como acelerar esta query no Postgres?"
    # ranking_prompt recebe ROTULOS CEGOS (A/B/C), como _rank_one monta.
    RANK_ANS = {
        "A": "Use indice parcial no campo status.",
        "B": "Rode VACUUM e reescreva a query com LATERAL.",
        "C": "Meça com EXPLAIN ANALYZE antes de decidir.",
    }
    # chairman_prompt recebe respostas por NOME DE MEMBRO e consensus com os
    # mesmos nomes (engine.py:291-296) — fixture fora dessa forma congela uma
    # chamada que a producao jamais faz.
    CHAIR_ANS = {
        "gpt": "Use indice parcial no campo status.",
        "claude": "Rode VACUUM e reescreva a query com LATERAL.",
        "glm": "Meça com EXPLAIN ANALYZE antes de decidir.",
    }
    FIX_CONS = [
        _Cons(member="gpt", score=0.78, positions=[1, 2, 2], ballots=3, spread=0.47,
              strengths=["vai direto ao ponto"], weaknesses=["ignora o custo de escrita"]),
        _Cons(member="claude", score=0.72, positions=[2, 1, 1], ballots=3, spread=0.47,
              strengths=["mede antes de opinar"], weaknesses=["vago no comando concreto"]),
        _Cons(member="glm", score=0.31, positions=[3, 3, 3], ballots=3, spread=0.0,
              strengths=["unica ideia diferente"], weaknesses=["nao responde ao pedido"]),
    ]
    renders = {
        "ranking.txt": _rank(FIX_Q, RANK_ANS),
        "chairman-blind.txt": _chair(FIX_Q, CHAIR_ANS, FIX_CONS, blind=True),
        "chairman-open.txt": _chair(FIX_Q, CHAIR_ANS, FIX_CONS, blind=False),
    }

    def _divergencia(a: str, b: str) -> str:
        i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]),
                 min(len(a), len(b)))
        return (f"primeira divergencia no char {i}: golden "
                f"{a[max(0, i - 25):i + 25]!r} vs atual {b[max(0, i - 25):i + 25]!r}")

    gdir = _P(__file__).resolve().parent / "golden"
    for nome, texto in sorted(renders.items()):
        alvo = gdir / nome
        if alvo.is_file():
            base = alvo.read_bytes()
            atual = texto.encode("utf-8")
            check(base == atual,
                  f"{nome}: render atual identico ao golden (byte a byte)"
                  + ("" if base == atual
                     else f" — {_divergencia(base.decode('utf-8', 'replace'), texto)}"))
        else:
            gdir.mkdir(exist_ok=True)
            alvo.write_bytes(texto.encode("utf-8"))
            check(True, f"{nome}: baseline gravado (bootstrap)")

    print("18) parser estruturado (modulo folha)")
    from council.structured import parse_decision as _pd
    from council.structured import parse_proposal as _pp
    from council.structured import parse_questions as _pq

    # QUESTIONS bem-formado
    qs, e = _pq("analise livre\n\nQUESTIONS:\n1 | trocar o driver? | manter, o ganho nao paga\n2 | particionar? | sim, pela data", 3)
    check(e == "" and len(qs) == 2, f"duas questoes parseadas ({e})")
    check(qs[0] == {"id": "1", "pergunta": "trocar o driver?",
                    "recomendacao": "manter, o ganho nao paga"}, f"campos completos ({qs[0]})")
    # id fora do intervalo ignorado, como o parser de verificacao faz
    qs, _ = _pq("QUESTIONS:\n1 | a? | b\n9 | fora? | fora", 3)
    check(len(qs) == 1 and qs[0]["id"] == "1", f"id fora de max_n ignorado ({qs})")
    # variante real: cabecalho traduzido e negrito no numero
    qs, e = _pq("texto\n\n**PERGUNTAS:**\n**1** | usar indice parcial? | sim", 3)
    check(e == "" and qs[0]["pergunta"] == "usar indice parcial?", f"cabecalho traduzido e negrito ({e})")
    # linha pela metade (um pipe so) fica de fora, nao vira questao incompleta
    qs, e = _pq("QUESTIONS:\n1 | pergunta sem recomendacao", 3)
    check(qs == [] and "nenhuma linha" in e, f"linha destruida nao e questao ({e})")
    # sem bloco
    qs, e = _pq("resposta sem bloco algum", 3)
    check(qs == [] and "ausente" in e, f"bloco ausente e erro nomeado ({e})")

    # PROPOSAL bem-formado
    p, e = _pp("contexto\n\nPROPOSAL:\nTITULO: indice parcial em status\nCORPO:\nCriar indice onde status='ativo'.\nCusto de escrita sobe pouco.")
    check(e == "" and p["titulo"] == "indice parcial em status", f"titulo extraido ({e})")
    check("Criar indice" in p["corpo"] and "pouco." in p["corpo"], f"corpo multi-linha inteiro ({p['corpo'][:40]}…)")
    p, e = _pp("PROPOSTA:\n**TÍTULO:** x\n**CORPO:**\ny")
    check(e == "" and p["titulo"] == "x" and p["corpo"] == "y", f"variantes com acento e negrito ({e})")
    p, e = _pp("PROPOSAL:\nCORPO:\nsem titulo")
    check(p == {} and "TITULO ausente" in e, f"campo faltando e erro nomeado ({e})")

    # DECISION bem-formado
    d, e = _pd("bla\n\nDECISION:\nDECIDIDO | op2 | alta | nenhuma | consenso converge para op2", ["op1", "op2", "op3"])
    check(e == "" and d["status"] == "DECIDIDO" and d["escolha"] == "op2", f"decisao completa ({e})")
    check(d["confianca"] == "alta" and d["dissidencias"] == "nenhuma", "campos livres preservados")
    # pipe extra dentro de fundamentos nao destrroi o parse
    d, e = _pd("DECISION:\nENCALHADO | op1 | baixa | glm sustenta op3 | tabela|com|pipes", ["op1", "op3"])
    check(e == "" and d["fundamentos"] == "tabela|com|pipes", f"pipes extras ficam no ultimo campo ({d})")
    # variantes: cabecalho traduzido, minusculo, ponto final
    d, e = _pd("DECISAO:\ndecidido. | op1 | media | - | ok", ["op1"])
    check(e == "" and d["status"] == "DECIDIDO", f"minusculo e ponto tolerados ({e})")
    # status invalido
    d, e = _pd("DECISION:\nTALVEZ | op1 | alta | - | x", ["op1"])
    check(d == {} and "status invalido" in e, f"status fora da lista e erro nomeado ({e})")
    # escolha fora dos ids validos
    d, e = _pd("DECISION:\nDECIDIDO | op9 | alta | - | x", ["op1", "op2"])
    check(d == {} and "ids validos" in e, f"escolha invalida e erro nomeado ({e})")
    # formato quebrado devolve erro, nao inventa decisao
    d, e = _pd("DECISION:\ndecisao em prosa sem pipes", ["op1"])
    check(d == {} and "nenhuma linha" in e, "formato quebrado devolve erro, nao inventa decisao")
    d, e = _pd("sem bloco algum", ["op1"])
    check(d == {} and "ausente" in e, f"bloco DECISION ausente ({e})")

    # regressoes de probes adversariais (review): cabecalho e LINHA INTEIRA,
    # campo vazio invalida, id gigante nao derruba, acento e grafia aceitos
    qs, e = _pq("NOTQUESTIONS:\n1 | falsa? | falsa", 3)
    check(qs == [] and "ausente" in e, f"'NOTQUESTIONS:' nao abre bloco ({e})")
    qs, e = _pq("QUESTIONS:\n1 | |", 3)
    check(qs == [] and "nenhuma linha" in e, f"questao com campos vazios rejeitada ({e})")
    qs, e = _pq("QUESTIONS:\n" + "5" * 5000 + " | gigante? | x", 3)
    check(qs == [] and e, f"id de 5000 digitos nao derruba o parser ({e[:40]})")
    qs, e = _pq("QUESTÕES:\n1 | acento? | sim", 3)
    check(e == "" and len(qs) == 1, f"cabecalho acentuado aceito ({e})")
    p, e = _pp("COUNTERPROPOSAL:\nTITULO: falso\nCORPO:\nfalso")
    check(p == {} and "ausente" in e, f"'COUNTERPROPOSAL:' nao abre bloco ({e})")
    p, e = _pp("PROPOSAL:\nTITULO: \"\"\nCORPO: c")
    check(p == {} and "vazio" in e, f"titulo vazio e malformed ({e})")
    p, e = _pp("PROPOSAL:\nTITULO: t\nCORPO:")
    check(p == {} and "vazio" in e, f"corpo vazio e malformed ({e})")
    p, e = _pp("PROPOSAL:\nTITULO: t\nCORPO:\nproposta de verdade\n\nDECISION:\nDECIDIDO | op1 | a | b | c")
    check(e == "" and "DECISION" not in p["corpo"], f"corpo nao engole bloco DECISION posterior ({p['corpo'][-30:]})")
    d, e = _pd("INDECISION:\nDECIDIDO | op1 | alta | - | f", ["op1"])
    check(d == {} and "ausente" in e, f"'INDECISION:' nao abre bloco ({e})")
    d, e = _pd("DECISION:\nDECIDIDO | op1 | | |", ["op1"])
    check(d == {} and "nenhuma linha" in e, f"decisao com campos vazios rejeitada ({e})")
    d, e = _pd("DECISÃO:\nDECIDIDO | op1 | alta | nenhuma | ok", ["op1"])
    check(e == "" and d["status"] == "DECIDIDO", f"cabecalho acentuado de decisao aceito ({e})")

    # regressoes da segunda rodada de review: negrito com colon interno,
    # campos so-espaco/aspas-vazias, TITULO de espacos, bloco citado
    qs, e = _pq("**QUESTIONS**:\n1 | bold com colon? | sim", 3)
    check(e == "" and len(qs) == 1, f"'**QUESTIONS**:' abre bloco ({e})")
    qs, e = _pq("QUESTIONS:\n1 | a? |   ", 3)
    check(qs == [] and "nenhuma linha" in e, f"recomendacao so-espacos rejeitada ({e})")
    qs, e = _pq("QUESTIONS:\n1 |   | resposta", 3)
    check(qs == [] and "nenhuma linha" in e, f"pergunta so-espacos rejeitada ({e})")
    p, e = _pp("PROPOSAL:\nTITULO:   \nCORPO: c")
    check(p == {} and "TITULO vazio" in e, f"titulo de so-espacos nao vira CORPO ({e})")
    d, e = _pd("__DECISÃO__:\nDECIDIDO | op1 | alta | nenhuma | ok", ["op1"])
    check(e == "" and d["status"] == "DECIDIDO", f"'__DECISÃO__:' abre bloco ({e})")
    d, e = _pd("DECISION:\nDECIDIDO | op1 | alta | nenhuma | \"\"", ["op1"])
    check(d == {} and "nenhuma linha" in e, f"fundamentos '\"\"' e vazio semantico ({e})")
    d, e = _pd("DECISION:\nDECIDIDO | op1 | alta | nenhuma | **", ["op1"])
    check(d == {} and "nenhuma linha" in e, f"fundamentos '**' e vazio semantico ({e})")
    p, e = _pp("PROPOSAL:\nTITULO: t\nCORPO:\nseguir com o plano\n\n**DECISION**:\nDECIDIDO | op1 | a | b | c")
    check(e == "" and "DECISION" not in p["corpo"], f"'**DECISION**:' posterior termina o corpo ({p.get('corpo', e)[-25:]})")
    p, e = _pp("PROPOSAL:\nTITULO: t\nCORPO:\nveja QUESTIONS abaixo\n\nQUESTIONS:\n1 | falsa? | falsa")
    check(e == "" and p["corpo"] == "veja QUESTIONS abaixo",
          f"QUESTIONS citado como prosa nao termina o corpo ({p['corpo']!r})")
    qs, e = _pq("PROPOSAL:\nTITULO: t\nCORPO:\nveja QUESTIONS abaixo\n\nQUESTIONS:\n1 | falsa? | falsa", 3)
    check(len(qs) == 1 and qs[0]["pergunta"] == "falsa?",
          f"o bloco QUESTIONS real e que e parseado, nao a prosa ({qs})")
    d, e = _pd("PROPOSTA:\nTITULO: x\nCORPO:\ny\n\nDECISION:\nENCALHADO | op1 | baixa | glm | impasse", ["op1"])
    check(e == "" and d["status"] == "ENCALHADO", f"DECISION depois de PROPOSTA e achado ({e})")

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
