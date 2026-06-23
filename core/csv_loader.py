"""
Leitura do arquivo CSV exportado do IMDb.

Responsável por localizar o arquivo `.csv` no diretório do projeto e carregá-lo
em memória como um dicionário indexado pelo código IMDb (coluna `Const`), o que
permite buscas instantâneas (O(1)) durante o processamento.

Os nomes das colunas seguem o padrão do export do IMDb e estão centralizados aqui
para facilitar ajustes caso o formato mude.
"""

import csv
import glob
import os
import sys
from datetime import datetime

# Pasta recomendada para guardar o histórico de exportações do IMDb.
PASTA_DADOS = "data"

# ----------------------------------------------------------------------
# Nomes das colunas no CSV do IMDb (padrão da exportação)
# ----------------------------------------------------------------------
COL_ID = "Const"               # Identificador IMDb (ex.: tt0903747) — chave do dicionário
COL_TITLE = "Title"            # Título (traduzido conforme a região do IMDb)
COL_ORIGINAL_TITLE = "Original Title"
COL_RATING = "IMDb Rating"
COL_YEAR = "Year"
COL_RUNTIME = "Runtime (mins)"
COL_GENRES = "Genres"
COL_DIRECTORS = "Directors"
COL_CATEGORY = "Title Type"    # Filme, Série de TV, Minissérie etc.
COL_URL = "URL"                # Link do título no IMDb (usado ao criar a página no Notion)
COL_YOUR_RATING = "Your Rating"  # Sua nota no IMDb — se preenchida, você assistiu

# Valores de "Title Type" (em PT e EN) que identificam uma SÉRIE no CSV do IMDb.
TIPOS_SERIE = {
    "série de tv", "tv series",
    "minissérie de tv", "tv mini series", "mini-series", "minissérie de televisão",
    "minissérie", "série",
}


def eh_serie(row: dict) -> bool:
    """Indica se a linha do CSV é uma série (ou minissérie), pelo 'Title Type'."""
    return row.get(COL_CATEGORY, "").strip().lower() in TIPOS_SERIE


def eh_filme(row: dict) -> bool:
    """Indica se a linha do CSV é um filme (qualquer tipo que não seja série)."""
    tipo = row.get(COL_CATEGORY, "").strip()
    return bool(tipo) and not eh_serie(row)


def descobrir_arquivo_csv() -> str:
    """
    Localiza o CSV mais recente a ser usado como fonte de dados.

    Procura primeiro na pasta `data/` (local recomendado para guardar o histórico
    de exportações do IMDb) e, como fallback, na raiz do projeto. Havendo vários
    arquivos, escolhe automaticamente o mais recente (pela data de modificação) e
    informa qual foi selecionado, para que o usuário confirme se é o esperado.
    """
    os.makedirs(PASTA_DADOS, exist_ok=True)

    # Prioriza a subpasta data/; só olha a raiz se a subpasta estiver vazia.
    arquivos = glob.glob(os.path.join(PASTA_DADOS, "*.csv")) or glob.glob("*.csv")

    if not arquivos:
        print("❌ ERRO: nenhum arquivo .csv foi encontrado.")
        print(f"👉 Exporte sua lista do IMDb e salve o .csv na pasta '{PASTA_DADOS}/'.")
        print("   (Veja a seção 'Exportar o CSV do IMDb' no README.md.)")
        sys.exit(1)

    # Seleciona o arquivo modificado mais recentemente.
    mais_recente = max(arquivos, key=os.path.getmtime)
    data_mod = datetime.fromtimestamp(os.path.getmtime(mais_recente)).strftime("%d/%m/%Y %H:%M")
    print(f"✔️  CSV mais recente detectado: '{mais_recente}' (modificado em {data_mod})")
    return mais_recente


def carregar_csv(caminho: str) -> dict:
    """
    Lê o CSV e devolve um dicionário {imdb_id: linha} para buscas rápidas.

    Usa o encoding 'utf-8-sig' para lidar com o BOM que o Excel costuma inserir.
    """
    base = {}
    print(f"\n⏳ Lendo o banco de dados local: {caminho}...")

    with open(caminho, mode="r", encoding="utf-8-sig") as arquivo:
        leitor = csv.DictReader(arquivo)
        for linha in leitor:
            imdb_id = linha.get(COL_ID)
            if imdb_id:
                base[imdb_id] = linha

    print(f"✔️  Base local carregada: {len(base)} registros indexados.")
    return base
