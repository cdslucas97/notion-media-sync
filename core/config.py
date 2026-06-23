"""
Configuração central do projeto.

Carrega as credenciais do arquivo `.env` (mantido fora do controle de versão) e
oferece uma função para validar, logo no início de cada script, se as variáveis
necessárias realmente foram preenchidas. Assim o usuário recebe um erro claro em
vez de uma falha confusa no meio da execução.
"""

import os
import sys

from dotenv import load_dotenv

# Lê o arquivo .env e injeta as variáveis no ambiente do processo.
load_dotenv()

# ----------------------------------------------------------------------
# Credenciais e identificadores (lidos do .env)
# ----------------------------------------------------------------------
NOTION_TOKEN = os.getenv("NOTION_TOKEN")        # Token secreto da integração do Notion
NOTION_DB_MOVIES = os.getenv("NOTION_DB_MOVIES")  # ID da base de Filmes no Notion
NOTION_DB_SERIES = os.getenv("NOTION_DB_SERIES")  # ID da base de Séries no Notion
TMDB_API_KEY = os.getenv("TMDB_API_KEY")        # Chave (v3) da API do TMDB

# Versão da API do Notion. Centralizada aqui para ser ajustada em um só lugar.
NOTION_VERSION = "2022-06-28"


def headers_notion() -> dict:
    """Monta os cabeçalhos HTTP exigidos em toda requisição à API do Notion."""
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def validar_credenciais(*nomes: str) -> None:
    """
    Garante que as variáveis de ambiente informadas estão preenchidas.

    Recebe os nomes das variáveis obrigatórias para o script atual (ex.:
    "NOTION_TOKEN", "TMDB_API_KEY"). Se alguma estiver faltando, exibe uma
    mensagem explicativa e encerra o programa antes de qualquer chamada de API.
    """
    faltando = [nome for nome in nomes if not os.getenv(nome)]

    if faltando:
        print("❌ ERRO DE CONFIGURAÇÃO: as seguintes variáveis estão ausentes no arquivo .env:")
        for nome in faltando:
            print(f"   - {nome}")
        print("\n👉 Verifique o arquivo .env (use o .env.example como modelo) e a seção")
        print("   'Configuração' do README.md.")
        sys.exit(1)
