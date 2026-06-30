"""
Cliente da API do TMDB (The Movie Database).

O TMDB é usado em dois cenários:

- Séries: é a fonte de dados estruturais (número de temporadas, episódios e anos
  de início/fim), que o CSV do IMDb não fornece.
- Filmes (script de backup): é a fonte alternativa quando não se quer usar o CSV.

A busca acontece em dois passos: primeiro converte-se o ID universal do IMDb no
ID interno do TMDB (`/find`), depois buscam-se os detalhes completos (`/movie` ou
`/tv`).
"""

import sys
import time

import requests

API_BASE = "https://api.themoviedb.org/3"


class TMDBAuthError(Exception):
    """
    Erro de autenticação na API do TMDB (HTTP 401): chave inválida ou não autorizada.

    É levantado em vez de encerrar o processo na hora, para que o chamador decida o
    que fazer: abortar cedo com mensagem clara (validação no início) ou interromper
    o laço preservando o log do que já foi processado.
    """


class TMDBClient:
    """Encapsula as buscas de filmes e séries na API do TMDB."""

    def __init__(self, api_key: str, idioma: str = "pt-BR"):
        self.api_key = api_key
        self.idioma = idioma

    def verificar_chave(self) -> None:
        """
        Valida a chave do TMDB logo no início do script (fail-fast).

        Faz uma chamada leve ao endpoint `/configuration` (que exige autenticação).
        Se a chave for inválida ou não autorizada, `_get` levanta TMDBAuthError;
        aqui isso vira uma mensagem clara e o encerramento imediato — antes de
        começar a processar item por item, em vez de morrer no meio do laço.
        """
        try:
            self._get(f"{API_BASE}/configuration", {})
        except TMDBAuthError as erro:
            print(f"❌ ERRO: {erro}")
            sys.exit(1)

    def _get(self, url: str, params: dict, max_tentativas: int = 4) -> dict:
        """
        Faz um GET na API do TMDB com novas tentativas automáticas e devolve o JSON.

        - Em HTTP 401, a chave é inválida: levanta TMDBAuthError com mensagem clara
          (em vez de fazer todos os itens parecerem "não localizados"). Quem chama
          decide se aborta na hora ou interrompe preservando o log parcial.
        - Em HTTP 429 (limite de taxa), respeita o cabeçalho `Retry-After`.
        - Em erros 5xx (falha temporária), aguarda com backoff exponencial.
        """
        params = {**params, "api_key": self.api_key, "language": self.idioma}
        resposta = None

        for tentativa in range(1, max_tentativas + 1):
            resposta = requests.get(url, params=params, timeout=30)

            if resposta.status_code == 401:
                raise TMDBAuthError(
                    "a chave do TMDB (TMDB_API_KEY) é inválida ou não foi autorizada.\n"
                    "   Confira a chave em https://www.themoviedb.org/settings/api"
                )

            if resposta.status_code == 429:
                espera = int(resposta.headers.get("Retry-After", 2))
                time.sleep(espera)
                continue

            if 500 <= resposta.status_code < 600:
                time.sleep(2 ** tentativa)  # 2s, 4s, 8s...
                continue

            return resposta.json()

        # Esgotou as tentativas: devolve o último JSON para o chamador tratar.
        return resposta.json()

    def _encontrar_tmdb_id(self, imdb_id: str, chave_resultado: str):
        """
        Converte o ID do IMDb no ID interno do TMDB.

        `chave_resultado` indica onde procurar na resposta: "movie_results" para
        filmes ou "tv_results" para séries. Retorna o ID do TMDB ou None.
        """
        url = f"{API_BASE}/find/{imdb_id}"
        resultados = self._get(url, {"external_source": "imdb_id"})
        lista = resultados.get(chave_resultado, [])
        return lista[0]["id"] if lista else None

    def buscar_filme(self, imdb_id: str) -> dict | None:
        """
        Retorna os detalhes de um filme (incluindo a equipe técnica via `credits`)
        ou None se o filme não for encontrado no TMDB.
        """
        tmdb_id = self._encontrar_tmdb_id(imdb_id, "movie_results")
        if tmdb_id is None:
            return None

        # append_to_response=credits traz elenco e equipe na mesma chamada.
        return self._get(f"{API_BASE}/movie/{tmdb_id}", {"append_to_response": "credits"})

    def buscar_serie(self, imdb_id: str) -> dict | None:
        """
        Retorna os detalhes de uma série (temporadas, episódios, status, datas)
        ou None se a série não for encontrada no TMDB.
        """
        tmdb_id = self._encontrar_tmdb_id(imdb_id, "tv_results")
        if tmdb_id is None:
            return None

        return self._get(f"{API_BASE}/tv/{tmdb_id}", {})
