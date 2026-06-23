"""
Geração do arquivo de log de cada execução.

Salva, na pasta `logs/`, um arquivo com a lista completa dos itens atualizados e
exatamente o que mudou em cada um — além das falhas. Resolve o problema de "rodei
e o terminal rolou": o registro fica gravado e pode ser consultado depois.
"""

import os
from datetime import datetime

PASTA_LOGS = "logs"


def salvar_execucao(titulo: str, sucessos_log: list, falhas_log: list,
                    prefixo: str = "execucao", adicionados_log: list = None) -> str | None:
    """
    Grava o log da execução e devolve o caminho do arquivo (ou None se nada houve).

    `prefixo` vai no início do nome do arquivo para identificar de cara o tipo de
    execução (ex.: "filmes", "series"). `adicionados_log` é a lista de nomes dos itens
    adicionados (sincronização); `sucessos_log`, uma lista de tuplas (nome, [mudanças])
    dos itens atualizados; `falhas_log`, uma lista de strings descrevendo cada falha.
    """
    adicionados_log = adicionados_log or []
    if not adicionados_log and not sucessos_log and not falhas_log:
        return None

    os.makedirs(PASTA_LOGS, exist_ok=True)
    agora = datetime.now()
    caminho = os.path.join(PASTA_LOGS, f"{prefixo}_{agora:%Y-%m-%d_%H%M%S}.txt")

    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(f"{titulo}\n")
        arquivo.write(f"Execução em {agora:%d/%m/%Y %H:%M:%S}\n")
        arquivo.write("=" * 60 + "\n\n")

        if adicionados_log:
            arquivo.write(f"ADICIONADOS ({len(adicionados_log)})\n")
            arquivo.write("-" * 60 + "\n")
            for indice, nome in enumerate(adicionados_log, start=1):
                arquivo.write(f"{indice}. {nome}\n")
            arquivo.write("\n")

        arquivo.write(f"ATUALIZADOS ({len(sucessos_log)})\n")
        arquivo.write("-" * 60 + "\n")
        for indice, (nome, mudancas) in enumerate(sucessos_log, start=1):
            arquivo.write(f"{indice}. {nome}\n")
            for mudanca in mudancas:
                arquivo.write(f"    - {mudanca}\n")

        if falhas_log:
            arquivo.write(f"\nFALHAS ({len(falhas_log)})\n")
            arquivo.write("-" * 60 + "\n")
            for falha in falhas_log:
                arquivo.write(f"- {falha}\n")

    return caminho
