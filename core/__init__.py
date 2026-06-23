"""
Pacote `core` — lógica compartilhada entre os scripts de atualização.

Cada módulo tem uma responsabilidade única e bem definida:

- config.py      Carrega e valida as credenciais do arquivo .env.
- notion.py      Cliente da API do Notion (paginação, busca, escrita + retry).
- tmdb.py        Cliente da API do TMDB (filmes e séries).
- csv_loader.py  Descoberta e leitura do arquivo CSV exportado do IMDb.
- bypass.py      Correções manuais (sobrescrita pontual de dados).
- status.py      Regra do Status (assistido / não assistido).
- diff.py        Registro das alterações (antigo → novo) de cada item.
- log.py         Gravação do arquivo de log de cada execução.
- cli.py         Menu interativo padronizado e relatório final no terminal.
- runner.py      Orquestra o laço de processamento (paginação, delta, kill-switch).

Os scripts na raiz do projeto (atualizar_filmes_csv.py, atualizar_series.py,
atualizar_filmes_tmdb.py) são apenas "entrypoints" curtos que combinam estas peças.
"""

import sys as _sys

# Em alguns terminais do Windows o code page padrão (cp1252) não consegue exibir
# emojis e acentos, o que quebraria os scripts com UnicodeEncodeError. Forçamos a
# saída para UTF-8 logo no carregamento do pacote, antes de qualquer impressão.
for _stream in (_sys.stdout, _sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
