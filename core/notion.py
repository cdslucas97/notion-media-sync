"""
Cliente da API do Notion.

Concentra toda a comunicação com o Notion em um só lugar:

- `NotionClient`: classe associada a uma base (database) específica. Sabe contar
  registros, paginar a base, buscar uma página por ID do IMDb e atualizar uma
  página. Todas as requisições passam por um mecanismo de retry que respeita o
  limite de taxa (HTTP 429) e tenta novamente em erros temporários do servidor.

- Funções `ler_*`: extraem o valor já gravado em uma propriedade da página. São
  usadas pela "detecção de delta" — comparar o dado novo com o que já existe no
  Notion para só escrever quando algo realmente mudou.
"""

import re
import sys
import time

import requests

from core import config

# Endpoint base da API do Notion.
API_BASE = "https://api.notion.com/v1"


def _request_com_retry(metodo: str, url: str, *, json: dict = None,
                       max_tentativas: int = 4) -> requests.Response:
    """
    Executa uma requisição HTTP com novas tentativas automáticas.

    - Em HTTP 429 (limite de taxa), respeita o cabeçalho `Retry-After`.
    - Em erros 5xx (falha temporária do servidor), aguarda com backoff exponencial.
    - Nos demais casos, devolve a resposta imediatamente (o chamador decide o que fazer).
    """
    headers = config.headers_notion()
    resposta = None

    for tentativa in range(1, max_tentativas + 1):
        resposta = requests.request(metodo, url, headers=headers, json=json, timeout=30)

        if resposta.status_code == 429:
            espera = int(resposta.headers.get("Retry-After", 2))
            time.sleep(espera)
            continue

        if 500 <= resposta.status_code < 600:
            time.sleep(2 ** tentativa)  # 2s, 4s, 8s...
            continue

        return resposta

    # Esgotou as tentativas: devolve a última resposta para o chamador tratar.
    return resposta


class NotionClient:
    """Encapsula as operações sobre uma base (database) específica do Notion."""

    def __init__(self, database_id: str):
        self.database_id = database_id
        self._url_query = f"{API_BASE}/databases/{database_id}/query"

    def contar_total(self) -> int | str:
        """
        Percorre a base inteira somando os registros (telemetria do painel de progresso).
        Retorna a contagem ou a string "Desconhecido" em caso de falha.
        """
        total = 0
        cursor = None
        has_more = True

        while has_more:
            payload = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor

            resposta = _request_com_retry("POST", self._url_query, json=payload)
            if resposta.status_code != 200:
                return "Desconhecido"

            dados = resposta.json()
            total += len(dados.get("results", []))
            has_more = dados.get("has_more", False)
            cursor = dados.get("next_cursor")

        return total

    def buscar_bloco(self, tamanho: int, cursor: str = None) -> tuple:
        """
        Busca um lote paginado de páginas da base.
        Retorna (lista_de_paginas, proximo_cursor, ainda_ha_mais).
        """
        payload = {"page_size": tamanho}
        if cursor:
            payload["start_cursor"] = cursor

        resposta = _request_com_retry("POST", self._url_query, json=payload)
        if resposta.status_code != 200:
            print("❌ Erro fatal na comunicação com a API do Notion.")
            sys.exit(1)

        dados = resposta.json()
        return dados.get("results", []), dados.get("next_cursor"), dados.get("has_more", False)

    def buscar_por_imdb_id(self, imdb_id: str) -> dict | None:
        """
        Busca direcionada: encontra a página cuja propriedade 'URL' contém o ID do IMDb.
        Usada no modo "Lista Específica". Retorna a página ou None se não existir.

        O filtro `contains` do Notion casa por substring, então um ID curto (ex.:
        'tt123') poderia trazer também páginas de um ID maior ('tt1234'). Por isso
        confirmamos a correspondência EXATA do código extraído antes de devolver.
        """
        payload = {
            "filter": {"property": "URL", "url": {"contains": imdb_id}},
            "page_size": 10,
        }
        resposta = _request_com_retry("POST", self._url_query, json=payload)
        if resposta.status_code == 200:
            for pagina in resposta.json().get("results", []):
                if extrair_imdb_id(pagina) == imdb_id:
                    return pagina
        return None

    def atualizar_pagina(self, page_id: str, propriedades: dict) -> bool:
        """
        Aplica um PATCH em uma página, gravando as propriedades informadas.
        Retorna True em caso de sucesso (HTTP 200).
        """
        url = f"{API_BASE}/pages/{page_id}"
        resposta = _request_com_retry("PATCH", url, json={"properties": propriedades})
        return resposta.status_code == 200

    def criar_pagina(self, propriedades: dict, icone: dict = None) -> bool:
        """
        Cria uma nova página (linha) na base, com as propriedades informadas.
        Usado para adicionar ao Notion títulos que existem no CSV mas ainda não
        estão cadastrados. Se `icone` for fornecido, a página nasce com esse ícone.
        Retorna True em caso de sucesso (HTTP 200).
        """
        url = f"{API_BASE}/pages"
        corpo = {"parent": {"database_id": self.database_id}, "properties": propriedades}
        if icone:
            corpo["icon"] = icone
        resposta = _request_com_retry("POST", url, json=corpo)
        return resposta.status_code == 200

    def mapear_base(self) -> tuple:
        """
        Percorre a base inteira UMA única vez e devolve (ids, total, icone):

        - ids:   conjunto dos códigos IMDb já cadastrados (para descobrir, junto com
                 o CSV, quais itens ainda faltam no Notion);
        - total: número de páginas na base (alimenta o painel de progresso, sem
                 precisar de uma segunda varredura só para contar);
        - icone: o ícone de uma página existente (reaproveitado ao criar itens novos),
                 ou None se nenhuma página tiver ícone.

        Faz numa só leitura o que antes exigia três (contar + coletar IDs + amostrar ícone).
        """
        ids = set()
        total = 0
        icone = None
        cursor = None
        has_more = True

        while has_more:
            bloco, cursor, has_more = self.buscar_bloco(100, cursor)
            for page in bloco:
                total += 1
                imdb_id = extrair_imdb_id(page)
                if imdb_id:
                    ids.add(imdb_id)
                if icone is None and page.get("icon"):
                    icone = page["icon"]

        return ids, total, icone


# ----------------------------------------------------------------------
# Leitura de propriedades (usada na detecção de delta)
# ----------------------------------------------------------------------
def extrair_imdb_id(page: dict) -> str | None:
    """Extrai o código IMDb (ex.: 'tt0903747') do campo 'URL' de uma página."""
    try:
        url = page["properties"]["URL"]["url"]
    except (KeyError, TypeError):
        return None
    if not url:
        return None
    achado = re.search(r"tt\d+", url)
    return achado.group(0) if achado else None


def ler_numero(props: dict, nome: str):
    """Lê o valor atual de uma propriedade do tipo Number."""
    return (props.get(nome) or {}).get("number")


def ler_titulo(props: dict, nome: str) -> str:
    """Lê o texto atual de uma propriedade do tipo Title."""
    arr = (props.get(nome) or {}).get("title", [])
    return arr[0]["plain_text"] if arr else ""


def ler_rich_text(props: dict, nome: str) -> str:
    """Lê o texto atual de uma propriedade do tipo Rich Text."""
    arr = (props.get(nome) or {}).get("rich_text", [])
    return arr[0]["plain_text"] if arr else ""


def ler_multi_select(props: dict, nome: str) -> set:
    """Lê as tags de uma propriedade Multi-Select como conjunto (ignora a ordem)."""
    arr = (props.get(nome) or {}).get("multi_select", [])
    return {item["name"] for item in arr}


def ler_select(props: dict, nome: str):
    """Lê o nome da opção atual de uma propriedade do tipo Select (ou None)."""
    valor = (props.get(nome) or {}).get("select")
    return valor.get("name") if valor else None


def ler_status(props: dict, nome: str):
    """Lê o nome da opção atual de uma propriedade do tipo Status (ou None)."""
    valor = (props.get(nome) or {}).get("status")
    return valor.get("name") if valor else None
