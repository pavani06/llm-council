"""Prompts dos estagios 2 e 3. Ficam isolados aqui porque sao a parte que voce vai querer editar."""

from __future__ import annotations

# Fonte unica dos criterios default (o golden da secao 15 e a prova de que o
# render com estes literais e byte-identico ao texto historico).
DEFAULT_CRITERIA = (
    "Correcao factual e ausencia de afirmacao inventada.",
    "Se responde ao que foi perguntado, e nao a uma versao mais facil da pergunta.",
    "Reconhecimento honesto do que nao se sabe — incerteza declarada vale mais que certeza falsa.",
    "Utilidade concreta: o leitor consegue agir.",
)


def ranking_prompt(question: str, labelled: dict[str, str], criteria=DEFAULT_CRITERIA) -> str:
    bloco = "\n\n".join(f"### Resposta {lbl}\n{txt}" for lbl, txt in sorted(labelled.items()))
    rotulos = ", ".join(sorted(labelled))
    criterios = "\n".join(f"{i}. {c}" for i, c in enumerate(criteria, start=1))
    return f"""Voce avalia respostas de outros sistemas a uma mesma pergunta. Voce nao sabe quem \
escreveu cada uma, e a sua propria resposta nao esta entre elas. Julgue apenas o conteudo.

PERGUNTA ORIGINAL:
{question}

RESPOSTAS (anonimas, ordem arbitraria):

{bloco}

Criterios, nesta ordem de peso:
{criterios}
Extensao, fluencia e formatacao nao contam. Penalize resposta longa que diz pouco.

Escreva primeiro a sua analise livre. Depois termine com EXATAMENTE estes dois blocos.\nOs dois cabecalhos vao em ingles, literalmente 'VERDICTS:' e 'FINAL RANKING:', mesmo\nque o resto da sua resposta esteja em portugues. Nao traduza, nao use negrito neles:

VERDICTS:
{chr(10).join(f"{l} | <o ponto mais forte, uma linha> | <a falha mais grave, uma linha>" for l in sorted(labelled))}

FINAL RANKING:
1. <rotulo>
2. <rotulo>
(continue ate ordenar todos: {rotulos})

Use so a letra do rotulo. Nao acrescente texto depois do ranking."""


def _tabela_consensus(alias: dict[str, str], consensus) -> str:
    """Bloco de avaliacao cruzada compartilhado entre presidente sintetizador e decisor."""
    if not consensus:
        return "AVALIACAO CRUZADA: nao houve — respostas insuficientes para ranqueamento cego."
    linhas = []
    for c in consensus:
        if not c.ballots:
            continue
        pro = c.strengths[0] if c.strengths else "-"
        con = c.weaknesses[0] if c.weaknesses else "-"
        linhas.append(
            f"- {alias.get(c.member, c.member)}: consenso {c.score:.2f} "
            f"(posicoes {c.positions}, dispersao {c.spread})\n"
            f"    a favor: {pro}\n"
            f"    contra:  {con}"
        )
    return (
        "AVALIACAO CRUZADA (cada resposta foi julgada as cegas pelos outros, "
        "sem auto-avaliacao; consenso 1.00 = sempre em primeiro):\n" + "\n".join(linhas)
    )


def chairman_prompt(question: str, answers: dict[str, str], consensus, *, blind: bool,
                    mode: str = "synthesizer", divided: bool = False) -> str:
    if mode == "decider":
        return decision_prompt(question, answers, consensus, divided=divided)
    if mode != "synthesizer":
        raise ValueError(f"modo de presidente desconhecido: '{mode}' (use synthesizer ou decider)")

    if blind:
        alias = {name: f"Resposta {chr(65 + i)}" for i, name in enumerate(_ordered(answers, consensus))}
    else:
        alias = {name: name for name in _ordered(answers, consensus)}

    corpo = "\n\n".join(f"### {alias[n]}\n{answers[n]}" for n in alias)
    tabela = _tabela_consensus(alias, consensus)

    return f"""Voce preside um conselho. Varios sistemas responderam a mesma pergunta e se avaliaram \
mutuamente as cegas. Sua tarefa nao e escolher um vencedor nem resumir: e produzir a melhor resposta \
possivel usando o que o conselho reuniu.

PERGUNTA ORIGINAL:
{question}

RESPOSTAS DO CONSELHO:

{corpo}

{tabela}

Como sintetizar:
- Onde o conselho concorda, afirme direto, sem citar quem disse.
- Onde discorda, essa e a informacao mais valiosa: diga qual e a divergencia e o que decide entre as \
opcoes. Nao faca media entre posicoes incompativeis.
- Uma boa ideia isolada em resposta mal colocada continua sendo uma boa ideia: aproveite.
- Se o conselho inteiro deixou passar algo que voce sabe estar errado, corrija e diga que corrigiu.
- Nao mencione estagios, ranking, rotulos ou o processo. Escreva a resposta final direta ao leitor, \
no idioma da pergunta.
- Se a evidencia nao sustenta uma conclusao unica, diga isso em vez de fabricar confianca."""


def _ordered(answers: dict[str, str], consensus) -> list[str]:
    if consensus:
        ordered = [c.member for c in consensus if c.member in answers]
        ordered += [n for n in answers if n not in ordered]
        return ordered
    return list(answers)


def decision_prompt(question: str, candidates: dict[str, str], consensus, *,
                    divided: bool = False) -> str:
    """Presidente-decisore: eleger o proximo passo (ou declarar impasse).

    A linha final segue a gramatica exata de council/structured.py: cinco campos
    separados por pipe, nenhum vazia ('nenhuma' e valor valido), cabecalho
    'DECISION:' so na linha do bloco.
    """
    if not candidates:
        raise ValueError("decision_prompt exige ao menos um candidato (recebeu vazio)")
    corpo = "\n\n".join(f"### {lbl}\n{txt}" for lbl, txt in sorted(candidates.items()))
    rotulos = ", ".join(sorted(candidates))
    tabela = _tabela_consensus({c: c for c in candidates}, consensus)

    if divided:
        impasse = (
            "O CONSELHO ESTA DIVIDIDO: o topo nao tem folga clara. Nesse caso o veredito e "
            "STATUS = ENCALHADO, a ESCOLHA e o rotulo menos pior, e os FUNDAMENTOS sintetizam "
            "o impasse (onde exatamente o conselho diverge e o que decidiria a disputa) em vez "
            "de forcar um vencedor."
        )
    else:
        impasse = (
            "Escolha pelo consenso e pela qualidade dos candidatos; so use ENCALHADO se "
            "nenhum candidato se sustenta."
        )

    return f"""Voce preside um conselho que precisa DECIDIR a proxima acao. Varios sistemas \
produziram candidatos e se avaliaram as cegas. Sua tarefa nao e resumir: e eleger um \
candidato — ou declarar impasse quando a evidencia nao sustenta eleicao nenhuma.

PERGUNTA ORIGINAL:
{question}

CANDIDATOS:

{corpo}

{tabela}

{impasse}

Responda com uma analise curta e termine com EXATAMENTE este bloco, nada depois dele:

DECISION:
STATUS | ESCOLHA | CONFIANCA | DISSIDENCIAS | FUNDAMENTOS

Regras do bloco, sem excecao:
- uma unica linha com cinco campos separados por ' | ';
- STATUS: DECIDIDO ou ENCALHADO;
- ESCOLHA: um destes rotulos: {rotulos};
- CONFIANCA: alta, media ou baixa;
- DISSIDENCIAS: quem sustenta o que, em uma linha; escreva 'nenhuma' quando nao houver;
- FUNDAMENTOS: a justificativa em uma linha.
- Nenhum campo pode ficar vazio — 'nenhuma' conta como valor. E nao escreva a palavra \
'DECISION' em nenhuma outra linha da resposta."""


_STAGE1_DIRETIVAS = {
    "questions": (
        "Responda com uma analise curta e termine com um bloco de interrogatorio no \
EXATO formato abaixo (ate 5 questoes, numeradas a partir de 1):\n\
QUESTIONS:\n\
1 | <pergunta de decisao, uma linha> | <sua recomendacao, uma linha>\n\
2 | <pergunta> | <recomendacao>\n\
Regras: pergunta que o operador decide, nao fato que se busca; nenhum campo vazio; \
nao escreva 'QUESTIONS' em nenhuma outra linha."
    ),
    "proposal": (
        "Responda com uma analise curta e termine com um bloco de proposta no EXATO \
formato abaixo:\n\
PROPOSAL:\n\
TITULO: <titulo curto da proposta, uma linha>\n\
CORPO:\n\
<justificativa e passos concretos, quantas linhas precisar>\n\
Regras: TITULO e CORPO nao podem ficar vazios; o CORPO e todo o texto ate o fim da \
resposta; nao escreva 'PROPOSAL' em nenhuma outra linha."
    ),
}


def stage1_user_prompt(question: str, bundle: str | None = None,
                       stage1_format: str = "prose") -> str:
    """Mensagem de user do estagio 1. Sem bundle e em prose devolve a pergunta
    inalterada — o payload do caminho sem perfil tem de ser byte-identico ao atual."""
    if stage1_format not in _STAGE1_DIRETIVAS and stage1_format != "prose":
        raise ValueError(
            f"stage1_format desconhecido: '{stage1_format}' (use prose, questions ou proposal)"
        )
    if not bundle and stage1_format == "prose":
        return question
    partes = []
    if bundle:
        partes.append(f"CONTEXTO (evidencia da deliberacao):\n{bundle}")
    direta = _STAGE1_DIRETIVAS.get(stage1_format)
    if direta:
        partes.append(direta)
    partes.append(f"PERGUNTA:\n{question}")
    return "\n\n".join(partes)
