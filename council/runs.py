"""Convencao de nome do diretorio de registros.

Modulo folha (so stdlib): existe para que "o que e um parcial" tenha um dono
unico. O engine escreve parciais nos limites de estagio; CLI, MCP e o
julgamento leem o mesmo diretorio e precisam deixar parciais de fora do que
tratam como registro. Sufixo repetido em quatro lugares vira, no primeiro
descuido, parcial entrando em denominador de experimento.
"""

from __future__ import annotations

import os
from pathlib import Path

PARTIAL_SUFFIX = "-partial.json"


def stamp_for(started_at: str) -> str:
    """Carimbo do nome de arquivo a partir do started_at do registro."""
    return started_at.replace(":", "").replace("-", "")


def partial_path(runs_dir: Path, started_at: str, resumed: bool = False) -> Path:
    """Parcial de UMA execucao deste processo.

    O carimbo tem granularidade de segundo: sozinho, ele colide quando dois
    bracos comecam no mesmo segundo (o experimento 1-vs-N roda bracos em
    paralelo) e um apagaria o parcial do outro. O pid separa os dois. Contra o
    registro final nao ha colisao possivel: final termina em <sha12>.json.

    resumed=True: parcial de uma execucao retomada (`--resume`). Sem o sufixo,
    um resume aberto no mesmo segundo e processo do original colidiria com o
    parcial referenciado — sobrescrevendo-o em voo e apagando-o no finalize,
    exatamente o arquivo que o resume existe por contrato preservar.
    """
    meio = "-r" if resumed else ""
    return runs_dir / f"{stamp_for(started_at)}-{os.getpid()}{meio}{PARTIAL_SUFFIX}"


def final_runs(runs_dir: Path) -> list[Path]:
    """Registros finais em ordem de nome; parciais ficam de fora."""
    if not runs_dir.is_dir():
        return []
    return sorted(p for p in runs_dir.glob("*.json")
                  if not p.name.endswith(PARTIAL_SUFFIX))
