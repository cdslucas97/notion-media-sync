"""
Atualização da base de FILMES no Notion a partir da API do TMDB.

>>> SCRIPT DE BACKUP <<<
Use este script apenas quando o script principal (atualizar_filmes_csv.py) não
puder ser usado — por exemplo, se você não tiver o CSV do IMDb em mãos. Aqui os
metadados vêm da API do TMDB, sem depender de nenhum arquivo local.

Observação importante: o TMDB fornece a NOTA dele (vote_average), que é gravada na
coluna "IMDb" do Notion por compatibilidade de schema. Esse valor NÃO é idêntico à
nota oficial do IMDb — por isso o script via CSV é o preferido para a nota.

Como nos demais scripts, grava no Notion apenas o que mudou (detecção de delta).
"""

from core import cli, config, diff, log, notion, runner
from core.bypass import BYPASS_FILMES
from core.tmdb import TMDBClient

# ----------------------------------------------------------------------
# Padronização de gêneros (alinha os nomes do TMDB às tags do seu Notion)
# ----------------------------------------------------------------------
DICIONARIO_GENEROS = {
    "Crime": "Policial",
    "Thriller": "Suspense",
    "Música": "Musical",
    "Cinema TV": "Filme para TV",
}


def construir_processador(client: notion.NotionClient, tmdb: TMDBClient, modo: str):
    """Cria a função que processa um único filme usando o TMDB como fonte."""

    def processar_item(imdb_id: str, page: dict) -> tuple:
        dados = tmdb.buscar_filme(imdb_id)
        if not dados:
            return runner.FALHA, "não localizado no TMDB"

        props = page.get("properties", {})

        # --- Campos numéricos ---
        nota_bruta = dados.get("vote_average", 0.0)
        nota = round(nota_bruta, 1) if nota_bruta else None
        ano = int(dados["release_date"].split("-")[0]) if dados.get("release_date") else None
        duracao = dados.get("runtime") or None

        # Bypass manual (mesmos dados do script principal de filmes).
        regras = BYPASS_FILMES.get(imdb_id, {})
        if "IMDb" in regras: nota = regras["IMDb"]
        if "Ano" in regras: ano = regras["Ano"]
        if "Duração" in regras: duracao = regras["Duração"]

        propriedades = {
            "IMDb": {"number": nota},
            "Ano": {"number": ano},
            "Duração": {"number": duracao},
        }

        mudancas = []  # cada item: "Campo: antigo → novo"
        diff.comparar_numero(mudancas, "Nota", nota, notion.ler_numero(props, "IMDb"))
        diff.comparar_numero(mudancas, "Ano", ano, notion.ler_numero(props, "Ano"))
        diff.comparar_numero(mudancas, "Duração", duracao, notion.ler_numero(props, "Duração"))

        # --- Campos textuais (apenas no modo COMPLETA) ---
        if modo == "COMPLETA":
            titulo = dados.get("title", "")
            titulo_original = dados.get("original_title", "")

            generos = [
                DICIONARIO_GENEROS.get(g["name"], g["name"])
                for g in dados.get("genres", [])
            ]
            crew = dados.get("credits", {}).get("crew", [])
            diretores = [c["name"] for c in crew if c.get("job") == "Director"]

            # Bypass de campos textuais (string separada por vírgulas vira lista).
            if "Título do Filme" in regras: titulo = regras["Título do Filme"]
            if "Título Original" in regras: titulo_original = regras["Título Original"]
            if "Gêneros" in regras:
                generos = [g.strip() for g in regras["Gêneros"].split(",") if g.strip()]
            if "Diretores" in regras:
                diretores = [d.strip() for d in regras["Diretores"].split(",") if d.strip()]

            propriedades.update({
                "Título do Filme": {"title": [{"text": {"content": titulo}}]},
                "Gêneros": {"multi_select": [{"name": g} for g in generos]},
                "Diretores": {"multi_select": [{"name": d} for d in diretores]},
                "Título Original": {"rich_text": [{"text": {"content": titulo_original}}]},
            })

            diff.comparar_texto(mudancas, "Título", titulo, notion.ler_titulo(props, "Título do Filme"))
            diff.comparar_texto(mudancas, "Título Orig.", titulo_original, notion.ler_rich_text(props, "Título Original"))
            diff.comparar_conjunto(mudancas, "Gêneros", generos, notion.ler_multi_select(props, "Gêneros"))
            diff.comparar_conjunto(mudancas, "Diretores", diretores, notion.ler_multi_select(props, "Diretores"))

        if not mudancas:
            return runner.INALTERADO, None

        if client.atualizar_pagina(page["id"], propriedades):
            return runner.SUCESSO, mudancas
        return runner.FALHA, "erro de escrita na API do Notion"

    return processar_item


def main() -> None:
    config.validar_credenciais("NOTION_TOKEN", "NOTION_DB_MOVIES", "TMDB_API_KEY")

    cli.exibir_cabecalho("🎬 ATUALIZAÇÃO DE FILMES - NOTION via TMDB (BACKUP)")

    # Este script não usa CSV: não há como adicionar itens novos (sincronizar) nem
    # determinar o Status (sem a nota do IMDb). Por isso não há PASSO de sincronização
    # e a opção STATUS fica oculta.
    modo, pausar, tamanho_bloco, lista_ids = cli.menu_interativo(
        descricao_completa="Atualiza: Título, Nota, Ano, Duração, Gêneros, Diretores, Título Original",
        descricao_parcial="Atualiza: Nota, Ano, Duração",
        exemplo_ids="tt0408236, tt8781928",
        permite_status=False,
    )

    client = notion.NotionClient(config.NOTION_DB_MOVIES)
    tmdb = TMDBClient(config.TMDB_API_KEY)
    processar_item = construir_processador(client, tmdb, modo)

    sucessos, inalterados, sucessos_log, falhas = runner.processar_base(
        client, processar_item,
        pausar=pausar, tamanho_bloco=tamanho_bloco, lista_ids=lista_ids,
        nome_entidade="Filme", coluna_titulo="Título do Filme",
    )

    caminho_log = log.salvar_execucao(
        f"Atualização de FILMES (TMDB/backup) — modo {modo}", sucessos_log, falhas, prefixo="filmes_tmdb")
    cli.imprimir_relatorio(sucessos, inalterados, sucessos_log, falhas, caminho_log)


if __name__ == "__main__":
    main()
