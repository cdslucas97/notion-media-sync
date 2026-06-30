"""
Atualização da base de SÉRIES no Notion (híbrido CSV + TMDB).

As séries usam duas fontes de dados combinadas, sempre priorizando o CSV do IMDb:
- CSV do IMDb: nota, categoria (Série/Minissérie), gêneros, títulos e o Ano de Início.
- API do TMDB: número de temporadas, episódios e o Ano de Fim — dados que o CSV do
  IMDb não fornece de forma confiável. (Também serve de fallback para o Ano de Início
  caso a célula 'Year' do CSV esteja vazia.)

Também permite SINCRONIZAR: adicionar ao Notion séries que estão no CSV mas ainda não
foram cadastradas — perguntando, uma a uma, se você deseja incluí-las.

Como nos demais scripts, grava no Notion apenas o que mudou (detecção de delta).
A "mecânica" do laço fica em core/runner.py; aqui ficam só as regras de séries.
"""

import re

from core import cli, config, csv_loader, diff, log, notion, runner, status
from core.bypass import BYPASS_SERIES
from core.tmdb import TMDBClient

# ----------------------------------------------------------------------
# Padronização de categoria (o IMDb varia o rótulo conforme o idioma)
# ----------------------------------------------------------------------
DICIONARIO_CATEGORIA = {
    "Série de TV": "Série",
    "TV Series": "Série",
    "Minissérie de TV": "Minissérie",
    "TV Mini Series": "Minissérie",
    "Mini-Series": "Minissérie",
    "Minissérie de televisão": "Minissérie",
}

# As correções manuais (bypass) ficam centralizadas em core/bypass.py.


def _ano_de(data: str):
    """Extrai o ano (int) de uma data no formato 'AAAA-MM-DD'. Retorna None se vazio."""
    return int(data.split("-")[0]) if data else None


def _ano_do_csv(valor: str):
    """
    Extrai o ano (int) da coluna 'Year' do CSV do IMDb.

    A célula costuma trazer só o ano de início (ex.: '2005'), mas pode vir como
    intervalo (ex.: '2005–2010'); em ambos os casos pegamos o primeiro ano. Retorna
    None se a célula estiver vazia ou sem um ano de 4 dígitos.
    """
    achado = re.search(r"\d{4}", valor) if valor else None
    return int(achado.group(0)) if achado else None


def _tem_nota(dados: dict) -> bool:
    """Indica se você já avaliou a série no IMDb (coluna 'Your Rating' preenchida)."""
    return bool(dados.get(csv_loader.COL_YOUR_RATING, "").strip())


def _status_desejado(dados: dict, status_atual) -> str:
    """Calcula o Status da série a partir da nota no IMDb e do status atual no Notion."""
    return status.decidir_status(
        _tem_nota(dados), status_atual,
        status.SERIES_OK_COM_NOTA, status.SERIES_OK_SEM_NOTA,
    )


def _extrair_serie(imdb_id: str, dados: dict, tmdb_data: dict) -> dict:
    """
    Combina CSV (fonte primária) e TMDB e aplica o bypass, devolvendo os valores já
    tratados. Usado tanto na atualização quanto na criação de páginas.
    """
    try:
        nota = float(dados.get(csv_loader.COL_RATING, 0)) or None
    except (ValueError, TypeError):
        nota = None

    categoria_bruta = dados.get(csv_loader.COL_CATEGORY, "").strip()
    categoria = DICIONARIO_CATEGORIA.get(categoria_bruta, categoria_bruta) or None

    temporadas = tmdb_data.get("number_of_seasons")
    episodios = tmdb_data.get("number_of_episodes")

    # Ano de Início: CSV é a fonte primária; o TMDB só entra como fallback.
    ano_inicio = _ano_do_csv(dados.get(csv_loader.COL_YEAR, ""))
    if ano_inicio is None:
        ano_inicio = _ano_de(tmdb_data.get("first_air_date", ""))

    # Só registra "Ano de Fim" se a série estiver efetivamente encerrada.
    if tmdb_data.get("status", "") in ("Ended", "Canceled"):
        ano_fim = _ano_de(tmdb_data.get("last_air_date", ""))
    else:
        ano_fim = None

    titulo = dados.get(csv_loader.COL_TITLE, "").strip()
    titulo_original = dados.get(csv_loader.COL_ORIGINAL_TITLE, "").strip()
    generos_str = dados.get(csv_loader.COL_GENRES, "")

    regras = BYPASS_SERIES.get(imdb_id, {})
    if "IMDb" in regras: nota = regras["IMDb"]
    if "Categoria" in regras: categoria = regras["Categoria"]
    if "Temporadas" in regras: temporadas = regras["Temporadas"]
    if "Episódios" in regras: episodios = regras["Episódios"]
    if "Ano de Início" in regras: ano_inicio = regras["Ano de Início"]
    if "Ano de Fim" in regras: ano_fim = regras["Ano de Fim"]
    if "Título da Série" in regras: titulo = regras["Título da Série"]
    if "Título Original" in regras: titulo_original = regras["Título Original"]
    if "Gêneros" in regras: generos_str = regras["Gêneros"]

    return {
        "nota": nota or None,
        "categoria": categoria,
        "temporadas": temporadas or None,
        "episodios": episodios or None,
        "ano_inicio": ano_inicio or None,
        "ano_fim": ano_fim or None,
        "titulo": titulo,
        "titulo_original": titulo_original,
        "generos": [g.strip() for g in generos_str.split(",") if g.strip()],
    }


def _payload_serie(vals: dict, incluir_textuais: bool) -> dict:
    """Monta o dicionário de propriedades do Notion a partir dos valores extraídos."""
    propriedades = {
        "IMDb": {"number": vals["nota"]},
        "Temporadas": {"number": vals["temporadas"]},
        "Episódios": {"number": vals["episodios"]},
        "Ano de Início": {"number": vals["ano_inicio"]},
        "Ano de Fim": {"number": vals["ano_fim"]},
    }
    # Categoria (Select) só entra no payload quando há um valor definido.
    if vals["categoria"]:
        propriedades["Categoria"] = {"select": {"name": vals["categoria"]}}
    if incluir_textuais:
        propriedades.update({
            "Título da Série": {"title": [{"text": {"content": vals["titulo"]}}]},
            "Gêneros": {"multi_select": [{"name": g} for g in vals["generos"]]},
            "Título Original": {"rich_text": [{"text": {"content": vals["titulo_original"]}}]},
        })
    return propriedades


def construir_processador(client: notion.NotionClient, tmdb: TMDBClient,
                          csv_db: dict, modo: str):
    """
    Cria a função que ATUALIZA uma série já existente: combina CSV e TMDB, compara
    com o que já está no Notion e só grava quando há diferença (delta).
    """

    def processar_item(imdb_id: str, page: dict) -> tuple:
        dados = csv_db.get(imdb_id)
        if not dados:
            return runner.FALHA, "ausente no CSV local"

        props = page.get("properties", {})
        propriedades = {}
        mudancas = []  # cada item: "Campo: antigo → novo"

        # Colunas de dados (COMPLETA e PARCIAL) — exigem o TMDB. No modo STATUS o
        # TMDB nem é consultado, pois só precisamos da nota (CSV) e do status atual.
        if modo in ("COMPLETA", "PARCIAL"):
            tmdb_data = tmdb.buscar_serie(imdb_id)
            if not tmdb_data:
                return runner.FALHA, "não localizado no TMDB"

            vals = _extrair_serie(imdb_id, dados, tmdb_data)
            propriedades.update(_payload_serie(vals, incluir_textuais=(modo == "COMPLETA")))
            diff.comparar_numero(mudancas, "Nota", vals["nota"], notion.ler_numero(props, "IMDb"))
            diff.comparar_numero(mudancas, "Temporadas", vals["temporadas"], notion.ler_numero(props, "Temporadas"))
            diff.comparar_numero(mudancas, "Episódios", vals["episodios"], notion.ler_numero(props, "Episódios"))
            diff.comparar_numero(mudancas, "Ano de Início", vals["ano_inicio"], notion.ler_numero(props, "Ano de Início"))
            diff.comparar_numero(mudancas, "Ano de Fim", vals["ano_fim"], notion.ler_numero(props, "Ano de Fim"))
            if vals["categoria"]:
                diff.comparar_texto(mudancas, "Categoria", vals["categoria"], notion.ler_select(props, "Categoria"))
            if modo == "COMPLETA":
                diff.comparar_texto(mudancas, "Título", vals["titulo"], notion.ler_titulo(props, "Título da Série"))
                diff.comparar_texto(mudancas, "Título Orig.", vals["titulo_original"], notion.ler_rich_text(props, "Título Original"))
                diff.comparar_conjunto(mudancas, "Gêneros", vals["generos"], notion.ler_multi_select(props, "Gêneros"))

        # Coluna Status (COMPLETA e STATUS).
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


def construir_criador(client: notion.NotionClient, tmdb: TMDBClient, csv_db: dict,
                      icone: dict = None):
    """
    Cria a função que ADICIONA uma série nova ao Notion (página completa + URL),
    usada na sincronização. A URL garante que execuções futuras casem com este item.
    `icone` é reaproveitado de um item existente para padronizar o visual da base.
    """

    def criar_item(imdb_id: str, dados: dict) -> tuple:
        tmdb_data = tmdb.buscar_serie(imdb_id)
        if not tmdb_data:
            return runner.FALHA, "não localizado no TMDB"

        vals = _extrair_serie(imdb_id, dados, tmdb_data)
        propriedades = _payload_serie(vals, incluir_textuais=True)
        url = dados.get(csv_loader.COL_URL, "").strip() or f"https://www.imdb.com/title/{imdb_id}/"
        propriedades["URL"] = {"url": url}
        # Item novo não tem status anterior: decide só pela presença de nota.
        propriedades["Status"] = {"status": {"name": _status_desejado(dados, None)}}

        if client.criar_pagina(propriedades, icone):
            return runner.SUCESSO, None
        return runner.FALHA, "erro ao criar a página no Notion"

    return criar_item


def _sincronizar(client: notion.NotionClient, tmdb: TMDBClient, csv_db: dict, passo: int) -> tuple:
    """
    PASSO de sincronização: descobre as séries do CSV que faltam no Notion e, se
    houver, oferece adicioná-las antes de seguir para a atualização.

    Faz uma única varredura da base (IDs + total + ícone) e devolve
    (total, adicionados_log, falhas): o total de itens na base (reaproveitado pela
    atualização), a lista das séries adicionadas e as falhas da adição (para o log).
    """
    print(f"\n[PASSO {passo}] Itens novos do CSV (ainda não cadastrados no Notion)")
    print("⏳ Mapeando a base do Notion...")
    ids_notion, total, icone = client.mapear_base()

    candidatos = []
    for imdb_id, row in csv_db.items():
        if imdb_id in ids_notion or not csv_loader.eh_serie(row):
            continue
        titulo = row.get(csv_loader.COL_TITLE, "").strip() or "(sem título)"
        ano = row.get(csv_loader.COL_YEAR, "").strip()
        tipo = row.get(csv_loader.COL_CATEGORY, "").strip()
        candidatos.append((imdb_id, row, f"{titulo} ({ano}) — {tipo}"))
    candidatos.sort(key=lambda c: c[2].lower())

    if not candidatos:
        print("✔️  Nenhuma série nova. Seguindo para a atualização.")
        return total, [], []

    print(f"🆕 Encontrei {len(candidatos)} série(s) nova(s) no CSV.")
    if not cli.confirmar("Deseja revisá-las para adicionar agora?"):
        print("Pulando a adição. Seguindo para a atualização.")
        return total, [], []

    # O ícone (já obtido na varredura) padroniza o visual das séries novas.
    criar_item = construir_criador(client, tmdb, csv_db, icone)
    adicionados_log, ignorados, sync_falhas = runner.sincronizar_novos(criar_item, candidatos)
    cli.imprimir_relatorio_sincronizacao(len(adicionados_log), ignorados, sync_falhas)
    # As recém-adicionadas também serão percorridas na atualização.
    return total + len(adicionados_log), adicionados_log, sync_falhas


def main() -> None:
    config.validar_credenciais("NOTION_TOKEN", "NOTION_DB_SERIES", "TMDB_API_KEY")

    cli.exibir_cabecalho("📺 ATUALIZAÇÃO DE SÉRIES - NOTION (CSV do IMDb + TMDB)")
    csv_db = csv_loader.carregar_csv(csv_loader.descobrir_arquivo_csv())
    client = notion.NotionClient(config.NOTION_DB_SERIES)
    tmdb = TMDBClient(config.TMDB_API_KEY)
    # Valida a chave do TMDB já no início: falha cedo e com mensagem clara, em vez de
    # morrer no meio do laço (este script depende do TMDB para os dados das séries).
    tmdb.verificar_chave()

    # PASSO 1: oferecer a adição de itens novos do CSV.
    total_base, adicionados_log, sync_falhas = _sincronizar(client, tmdb, csv_db, passo=1)

    # PASSO 2 e 3: tipo de atualização e como processar a fila.
    modo, pausar, tamanho_bloco, lista_ids = cli.menu_interativo(
        descricao_completa="Atualiza tudo: Títulos, Gêneros, Nota, Categoria, Temporadas, Episódios, Anos, Status",
        descricao_parcial="Atualiza: Nota, Categoria, Temporadas, Episódios e Anos",
        descricao_status="Atualiza apenas: Status (assistido / não assistido)",
        exemplo_ids="tt0903747, tt1475582",
        passo_inicial=2,
    )

    # Atualizar itens já existentes (reaproveita o total já contado no PASSO 1).
    processar_item = construir_processador(client, tmdb, csv_db, modo)

    sucessos, inalterados, sucessos_log, falhas = runner.processar_base(
        client, processar_item,
        pausar=pausar, tamanho_bloco=tamanho_bloco, lista_ids=lista_ids,
        nome_entidade="Série", coluna_titulo="Título da Série", total=total_base,
    )

    # O log da execução reúne adicionadas (PASSO 1) + atualizadas + todas as falhas.
    caminho_log = log.salvar_execucao(
        f"Atualização de SÉRIES — modo {modo}", sucessos_log, sync_falhas + falhas,
        prefixo="series", adicionados_log=adicionados_log)
    cli.imprimir_relatorio(sucessos, inalterados, sucessos_log, falhas, caminho_log)


if __name__ == "__main__":
    main()
