"""Prompts dos estagios 2 e 3. Ficam isolados aqui porque sao a parte que voce vai querer editar."""

from __future__ import annotations


def ranking_prompt(question: str, labelled: dict[str, str]) -> str:
    bloco = "\n\n".join(f"### Resposta {lbl}\n{txt}" for lbl, txt in sorted(labelled.items()))
    rotulos = ", ".join(sorted(labelled))
    return f"""Voce avalia respostas de outros sistemas a uma mesma pergunta. Voce nao sabe quem \
escreveu cada uma, e a sua propria resposta nao esta entre elas. Julgue apenas o conteudo.

PERGUNTA ORIGINAL:
{question}

RESPOSTAS (anonimas, ordem arbitraria):

{bloco}

Criterios, nesta ordem de peso:
1. Correcao factual e ausencia de afirmacao inventada.
2. Se responde ao que foi perguntado, e nao a uma versao mais facil da pergunta.
3. Reconhecimento honesto do que nao se sabe — incerteza declarada vale mais que certeza falsa.
4. Utilidade concreta: o leitor consegue agir.
Extensao, fluencia e formatacao nao contam. Penalize resposta longa que diz pouco.

Escreva primeiro a sua analise livre. Depois termine com EXATAMENTE estes dois blocos:

VERDICTS:
{chr(10).join(f"{l} | <o ponto mais forte, uma linha> | <a falha mais grave, uma linha>" for l in sorted(labelled))}

FINAL RANKING:
1. <rotulo>
2. <rotulo>
(continue ate ordenar todos: {rotulos})

Use so a letra do rotulo. Nao acrescente texto depois do ranking."""


def chairman_prompt(question: str, answers: dict[str, str], consensus, *, blind: bool) -> str:
    if blind:
        alias = {name: f"Resposta {chr(65 + i)}" for i, name in enumerate(_ordered(answers, consensus))}
    else:
        alias = {name: name for name in _ordered(answers, consensus)}

    corpo = "\n\n".join(f"### {alias[n]}\n{answers[n]}" for n in alias)

    if consensus:
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
        tabela = (
            "AVALIACAO CRUZADA (cada resposta foi julgada as cegas pelos outros, "
            "sem auto-avaliacao; consenso 1.00 = sempre em primeiro):\n" + "\n".join(linhas)
        )
    else:
        tabela = "AVALIACAO CRUZADA: nao houve — respostas insuficientes para ranqueamento cego."

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
