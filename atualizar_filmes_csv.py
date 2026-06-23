"""
Atualização da base de FILMES no Notion a partir do CSV exportado do IMDb.

Este é o script PRINCIPAL para filmes. Ele lê os dados diretamente do arquivo CSV
(rápido e sem depender de APIs externas para os metadados) e os grava nas páginas
correspondentes do Notion, escrevendo apenas o que de fato mudou (detecção de delta).

Também permite SINCRONIZAR: adicionar ao Notion filmes que estão no CSV mas ainda
não foram cadastrados — perguntando, um a um, se você deseja incluí-los.

A "mecânica" do laço fica em core/runner.py; aqui ficam só as regras de filmes.
Para uma fonte alternativa (sem CSV), use o script de backup: atualizar_filmes_tmdb.py.
"""

from core import cli, config, csv_loader, diff, log, notion, runner, status
from core.bypass import BYPASS_FILMES

# As correções manuais (bypass) ficam centralizadas em core/bypass.py.


def _para_numero(valor, conversor):
    """Converte um texto do CSV em número, devolvendo None se a célula estiver vazia/inválida."""
    try:
        numero = conversor(valor)
    except (ValueError, TypeError):
        return None
    return numero if numero else None


def _tem_nota(dados: dict) -> bool:
    """Indica se você já avaliou o título no IMDb (coluna 'Your Rating' preenchida)."""
    return bool(dados.get(csv_loader.COL_YOUR_RATING, "").strip())


def _status_desejado(dados: dict, status_atual) -> str:
    """Calcula o Status do filme a partir da nota no IMDb e do status atual no Notion."""
    return status.decidir_status(
        _tem_nota(dados), status_atual,
        status.FILMES_OK_COM_NOTA, status.FILMES_OK_SEM_NOTA,
    )


def _extrair_filme(imdb_id: str, dados: dict) -> dict:
    """
    Lê os dados de um filme no CSV e aplica o bypass, devolvendo os valores já
    tratados. Usado tanto na atualização quanto na criação de páginas.
    """
    nota = _para_numero(dados.get(csv_loader.COL_RATING), float)
    ano = _para_numero(dados.get(csv_loader.COL_YEAR), int)
    duracao = _para_numero(dados.get(csv_loader.COL_RUNTIME), int)
    titulo = dados.get(csv_loader.COL_TITLE, "").strip()
    titulo_original = dados.get(csv_loader.COL_ORIGINAL_TITLE, "").strip()
    generos_str = dados.get(csv_loader.COL_GENRES, "")
    diretores_str = dados.get(csv_loader.COL_DIRECTORS, "")

    regras = BYPASS_FILMES.get(imdb_id, {})
    if "IMDb" in regras: nota = regras["IMDb"]
    if "Ano" in regras: ano = regras["Ano"]
    if "Duração" in regras: duracao = regras["Duração"]
    if "Título do Filme" in regras: titulo = regras["Título do Filme"]
    if "Título Original" in regras: titulo_original = regras["Título Original"]
    if "Gêneros" in regras: generos_str = regras["Gêneros"]
    if "Diretores" in regras: diretores_str = regras["Diretores"]

    return {
        "nota": nota,
        "ano": ano,
        "duracao": duracao,
        "titulo": titulo,
        "titulo_original": titulo_original,
        "generos": [g.strip() for g in generos_str.split(",") if g.strip()],
        "diretores": [d.strip() for d in diretores_str.split(",") if d.strip()],
    }


def _payload_filme(vals: dict, incluir_textuais: bool) -> dict:
    """Monta o dicionário de propriedades do Notion a partir dos valores extraídos."""
    propriedades = {
        "IMDb": {"number": vals["nota"]},
        "Ano": {"number": vals["ano"]},
        "Duração": {"number": vals["duracao"]},
    }
    if incluir_textuais:
        propriedades.update({
            "Título do Filme": {"title": [{"text": {"content": vals["titulo"]}}]},
            "Gêneros": {"multi_select": [{"name": g} for g in vals["generos"]]},
            "Diretores": {"multi_select": [{"name": d} for d in vals["diretores"]]},
            "Título Original": {"rich_text": [{"text": {"content": vals["titulo_original"]}}]},
        })
    return propriedades


def construir_processador(client: notion.NotionClient, csv_db: dict, modo: str):
    """
    Cria a função que ATUALIZA um filme já existente no Notion: extrai os dados do
    CSV, compara com o que já está gravado e só escreve quando há diferença (delta).
    """

    def processar_item(imdb_id: str, page: dict) -> tuple:
        dados = csv_db.get(imdb_id)
        if not dados:
            return runner.FALHA, "ausente no CSV local"

        props = page.get("properties", {})
        propriedades = {}
        mudancas = []  # cada item: "Campo: antigo → novo"

        # Colunas de dados (modos COMPLETA e PARCIAL).
        if modo in ("COMPLETA", "PARCIAL"):
            vals = _extrair_filme(imdb_id, dados)
            propriedades.update(_payload_filme(vals, incluir_textuais=(modo == "COMPLETA")))
            diff.comparar_numero(mudancas, "Nota", vals["nota"], notion.ler_numero(props, "IMDb"))
            diff.comparar_numero(mudancas, "Ano", vals["ano"], notion.ler_numero(props, "Ano"))
            diff.comparar_numero(mudancas, "Duração", vals["duracao"], notion.ler_numero(props, "Duração"))
            if modo == "COMPLETA":
                diff.comparar_texto(mudancas, "Título", vals["titulo"], notion.ler_titulo(props, "Título do Filme"))
                diff.comparar_texto(mudancas, "Título Orig.", vals["titulo_original"], notion.ler_rich_text(props, "Título Original"))
                diff.comparar_conjunto(mudancas, "Gêneros", vals["generos"], notion.ler_multi_select(props, "Gêneros"))
                diff.comparar_conjunto(mudancas, "Diretores", vals["diretores"], notion.ler_multi_select(props, "Diretores"))

        # Coluna Status (modos COMPLETA e STATUS).
        if modo in ("COMPLETA", "STATUS"):
            status_atual = notion.ler_status(props, "Status")
            desejado = _status_desejado(dados, status_atual)
            propriedades["Status"] = {"status": {"name": desejado}}
            diff.comparar_texto(mudancas, "Status", desejado, status_atual)

        if not mudancas:
            return runner.INALTERADO, None

        if client.atualizar_pagina(page["id"], propriedades):
            return runner.SUCESSO, mudancas
        return runner.FALHA, "erro de escrita na API do Notion"

    return processar_item


def construir_criador(client: notion.NotionClient, csv_db: dict, icone: dict = None):
    """
    Cria a função que ADICIONA um filme novo ao Notion (página completa + URL),
    usada na sincronização. A URL garante que execuções futuras casem com este item.
    `icone` é reaproveitado de um item existente para padronizar o visual da base.
    """

    def criar_item(imdb_id: str, dados: dict) -> tuple:
        vals = _extrair_filme(imdb_id, dados)
        propriedades = _payload_filme(vals, incluir_textuais=True)
        url = dados.get(csv_loader.COL_URL, "").strip() or f"https://www.imdb.com/title/{imdb_id}/"
        propriedades["URL"] = {"url": url}
        # Item novo não tem status anterior: decide só pela presença de nota.
        propriedades["Status"] = {"status": {"name": _status_desejado(dados, None)}}

        if client.criar_pagina(propriedades, icone):
            return runner.SUCESSO, None
        return runner.FALHA, "erro ao criar a página no Notion"

    return criar_item


def _sincronizar(client: notion.NotionClient, csv_db: dict, passo: int) -> tuple:
    """
    PASSO de sincronização: descobre os filmes do CSV que faltam no Notion e, se
    houver, oferece adicioná-los antes de seguir para a atualização.

    Faz uma única varredura da base (IDs + total + ícone) e devolve
    (total, adicionados_log, falhas): o total de itens na base (reaproveitado pela
    atualização), a lista dos filmes adicionados e as falhas da adição (para o log).
    """
    print(f"\n[PASSO {passo}] Itens novos do CSV (ainda não cadastrados no Notion)")
    print("⏳ Mapeando a base do Notion...")
    ids_notion, total, icone = client.mapear_base()

    candidatos = []
    for imdb_id, row in csv_db.items():
        if imdb_id in ids_notion or not csv_loader.eh_filme(row):
            continue
        titulo = row.get(csv_loader.COL_TITLE, "").strip() or "(sem título)"
        ano = row.get(csv_loader.COL_YEAR, "").strip()
        tipo = row.get(csv_loader.COL_CATEGORY, "").strip()
        candidatos.append((imdb_id, row, f"{titulo} ({ano}) — {tipo}"))
    candidatos.sort(key=lambda c: c[2].lower())

    if not candidatos:
        print("✔️  Nenhum filme novo. Seguindo para a atualização.")
        return total, [], []

    print(f"🆕 Encontrei {len(candidatos)} filme(s) novo(s) no CSV.")
    if not cli.confirmar("Deseja revisá-los para adicionar agora?"):
        print("Pulando a adição. Seguindo para a atualização.")
        return total, [], []

    # O ícone (já obtido na varredura) padroniza o visual dos filmes novos.
    criar_item = construir_criador(client, csv_db, icone)
    adicionados_log, ignorados, sync_falhas = runner.sincronizar_novos(criar_item, candidatos)
    cli.imprimir_relatorio_sincronizacao(len(adicionados_log), ignorados, sync_falhas)
    # Os recém-adicionados também serão percorridos na atualização.
    return total + len(adicionados_log), adicionados_log, sync_falhas


def main() -> None:
    config.validar_credenciais("NOTION_TOKEN", "NOTION_DB_MOVIES")

    cli.exibir_cabecalho("🎬 ATUALIZAÇÃO DE FILMES - NOTION via CSV do IMDb")
    csv_db = csv_loader.carregar_csv(csv_loader.descobrir_arquivo_csv())
    client = notion.NotionClient(config.NOTION_DB_MOVIES)

    # PASSO 1: oferecer a adição de itens novos do CSV.
    total_base, adicionados_log, sync_falhas = _sincronizar(client, csv_db, passo=1)

    # PASSO 2 e 3: tipo de atualização e como processar a fila.
    modo, pausar, tamanho_bloco, lista_ids = cli.menu_interativo(
        descricao_completa="Atualiza tudo: Título, Nota, Ano, Duração, Gêneros, Diretores, Título Original, Status",
        descricao_parcial="Atualiza: Nota, Ano, Duração",
        descricao_status="Atualiza apenas: Status (assistido / não assistido)",
        exemplo_ids="tt0408236, tt8781928",
        passo_inicial=2,
    )

    # Atualizar itens já existentes (reaproveita o total já contado no PASSO 1).
    processar_item = construir_processador(client, csv_db, modo)

    sucessos, inalterados, sucessos_log, falhas = runner.processar_base(
        client, processar_item,
        pausar=pausar, tamanho_bloco=tamanho_bloco, lista_ids=lista_ids,
        nome_entidade="Filme", coluna_titulo="Título do Filme", total=total_base,
    )

    # O log da execução reúne adicionados (PASSO 1) + atualizados + todas as falhas.
    caminho_log = log.salvar_execucao(
        f"Atualização de FILMES (CSV) — modo {modo}", sucessos_log, sync_falhas + falhas,
        prefixo="filmes", adicionados_log=adicionados_log)
    cli.imprimir_relatorio(sucessos, inalterados, sucessos_log, falhas, caminho_log)


if __name__ == "__main__":
    main()
