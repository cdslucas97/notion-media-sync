"""
Regra de negócio da coluna "Status" (assistido / não assistido).

A presença de uma nota sua no IMDb (coluna "Your Rating" do CSV) indica que você
assistiu ao título. A partir disso, o status é ajustado — mas sem sobrescrever os
status que você definiu de propósito (ex.: "Reassistir", "Assistindo").

Lógica (ver tabelas no README):
- COM nota:  se o status atual já é um dos "ok com nota", mantém; senão -> "Assistido".
- SEM nota:  se o status atual já é um dos "ok sem nota", mantém; senão -> "Não Assistido".
"""

ASSISTIDO = "Assistido"
NAO_ASSISTIDO = "Não Assistido"

# ----------------------------------------------------------------------
# Conjuntos de status que NÃO devem ser sobrescritos, por tabela.
# ----------------------------------------------------------------------
# Filmes
FILMES_OK_COM_NOTA = {"Assistido", "Reassistir"}
FILMES_OK_SEM_NOTA = {"Não Assistido", "Na Fila"}

# Séries (protege também os estados "em andamento / em dia", nos dois sentidos)
SERIES_OK_COM_NOTA = {"Assistido", "Assistindo", "Última Temporada Assistida"}
SERIES_OK_SEM_NOTA = {"Não Assistido", "Na Fila", "Assistindo", "Última Temporada Assistida"}


def decidir_status(tem_nota: bool, status_atual, ok_com_nota: set, ok_sem_nota: set) -> str:
    """
    Calcula o status desejado para um item.

    Devolve o próprio `status_atual` quando ele já é aceitável (nada a fazer), ou o
    novo status ("Assistido" / "Não Assistido") quando deve ser ajustado. Status atual
    vazio (None) nunca está nos conjuntos, então sempre recebe um valor definido.
    """
    if tem_nota:
        return status_atual if status_atual in ok_com_nota else ASSISTIDO
    return status_atual if status_atual in ok_sem_nota else NAO_ASSISTIDO
