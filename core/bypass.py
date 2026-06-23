"""
Sobrescrita manual (bypass) de dados — fonte única para os três scripts.

Use quando o IMDb/TMDB trouxer um dado errado ou incompleto: aqui você força o valor
correto sem precisar editar o CSV. A chave externa é o código IMDb (ex.: "tt0381061");
as chaves internas são os NOMES DAS COLUNAS do Notion.

⚠️ ATENÇÃO: as tabelas de Filmes e de Séries têm colunas diferentes — por isso há dois
dicionários separados. Use em cada um SOMENTE as chaves válidas listadas abaixo (uma
chave de série não tem efeito na tabela de filmes, e vice-versa).

FILMES (BYPASS_FILMES) — chaves válidas:
    "IMDb", "Ano", "Duração",
    "Título do Filme", "Título Original", "Gêneros", "Diretores"

SÉRIES (BYPASS_SERIES) — chaves válidas:
    "IMDb", "Categoria", "Temporadas", "Episódios", "Ano de Início", "Ano de Fim",
    "Título da Série", "Título Original", "Gêneros"

Para "Gêneros" e "Diretores", informe uma string separada por vírgulas (ex.:
"Ação, Comédia"). Para números, informe o número direto (ex.: 9.5 ou 2024).

Modelo:
    "tt1234567": {"IMDb": 9.5, "Gêneros": "Ação, Comédia"},
"""

# ----------------------------------------------------------------------
# FILMES — usado por atualizar_filmes_csv.py E por atualizar_filmes_tmdb.py.
# (Os dois escrevem na MESMA base de filmes do Notion, então compartilham os bypasses.)
# ----------------------------------------------------------------------
#
# ESQUELETO COMPLETO (copie, descomente e ajuste; remova as colunas que não usar):
#
#     "tt0000000": {
#         "IMDb": 9.5,                         # Number  — nota do IMDb
#         "Ano": 2024,                         # Number  — ano de lançamento
#         "Duração": 142,                      # Number  — duração em minutos
#         "Título do Filme": "Nome do Filme",  # Title   — título exibido
#         "Título Original": "Original Name",  # Text    — título no idioma original
#         "Gêneros": "Ação, Comédia",          # Multi-select — string separada por vírgulas
#         "Diretores": "Fulano, Ciclano",      # Multi-select — string separada por vírgulas
#     },
#
BYPASS_FILMES = {
    "tt8781928": {"Duração": 86},                          # Apollo: Reconstruindo a Jornada Espacial
    "tt0381061": {"Título do Filme": "007 - Cassino Royale"},
    "tt2379713": {"Título do Filme": "007 - Contra Spectre"},
}

# ----------------------------------------------------------------------
# SÉRIES — usado por atualizar_series.py.
# ----------------------------------------------------------------------
#
# ESQUELETO COMPLETO (copie, descomente e ajuste; remova as colunas que não usar):
#
#     "tt0000000": {
#         "IMDb": 8.9,                         # Number  — nota do IMDb
#         "Categoria": "Série",                # Select  — "Série" ou "Minissérie"
#         "Temporadas": 5,                     # Number  — total de temporadas
#         "Episódios": 51,                     # Number  — total de episódios
#         "Ano de Início": 2014,               # Number  — ano da 1ª temporada
#         "Ano de Fim": 2024,                  # Number  — ano de encerramento
#         "Título da Série": "Nome da Série",  # Title   — título exibido
#         "Título Original": "Original Name",  # Text    — título no idioma original
#         "Gêneros": "Crime, Drama",           # Multi-select — string separada por vírgulas
#     },
#
BYPASS_SERIES = {
    "tt0279600": {"Ano de Fim": 2011},   # Smallville
    "tt2395695": {"Ano de Fim": 2014},   # Cosmos: Uma Odisseia do Espaço-Tempo
    "tt11170862": {"Ano de Fim": 2020},  # Cosmos: Mundos Possíveis
    "tt2802850": {"Ano de Fim": 2024},   # Fargo
}
