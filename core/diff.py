"""
Registro das alterações (antigo → novo) de cada item.

Em vez de apenas dizer "mudou / não mudou", estas funções comparam o valor novo
com o que já está no Notion e, quando diferem, acrescentam à lista `mudancas` uma
descrição legível (ex.: "Nota: 7.8 → 8.3"). A lista vazia significa "nada mudou".
"""


def _fmt(valor) -> str:
    """Formata um valor para exibição ('—' quando vazio; conjuntos viram lista)."""
    if valor is None or valor == "":
        return "—"
    if isinstance(valor, (set, list, tuple)):
        return ", ".join(sorted(valor)) if valor else "—"
    return str(valor)


def comparar_numero(mudancas: list, rotulo: str, novo, atual) -> None:
    """Registra a mudança de um campo numérico, se houver."""
    if novo != atual:
        mudancas.append(f"{rotulo}: {_fmt(atual)} → {_fmt(novo)}")


def comparar_texto(mudancas: list, rotulo: str, novo, atual) -> None:
    """Registra a mudança de um campo de texto (trata ''/None como equivalentes)."""
    if (novo or None) != (atual or None):
        mudancas.append(f"{rotulo}: {_fmt(atual)} → {_fmt(novo)}")


def comparar_conjunto(mudancas: list, rotulo: str, novo, atual) -> None:
    """Registra a mudança de um multi-select (ignora a ordem). `novo`=lista, `atual`=set."""
    if set(novo) != set(atual):
        mudancas.append(f"{rotulo}: {_fmt(set(atual))} → {_fmt(set(novo))}")
