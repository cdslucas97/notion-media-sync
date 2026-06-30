"""
Orquestrador do processamento.

Contém o laço genérico que é igual nos três scripts: percorrer a base do Notion
(ou uma lista específica de IDs), chamar a função de processamento de cada item,
contabilizar os resultados, respeitar o limite de taxa e abortar em caso de muitas
falhas seguidas.

A parte que muda de um script para outro — *como* cada item é transformado — é
recebida como uma função (`processar_item`). Assim, o entrypoint cuida apenas da
regra de negócio específica, e toda a "mecânica" do laço fica aqui.

`processar_item(imdb_id, page)` deve retornar uma tupla `(status, info)`:
    status -> SUCESSO, INALTERADO ou FALHA (constantes deste módulo)
    info   -> lista das mudanças (quando SUCESSO), motivo da falha (quando FALHA)
              ou None (quando INALTERADO)
"""

import time

from core import cli, notion
from core.tmdb import TMDBAuthError

# Status possíveis devolvidos por `processar_item`.
SUCESSO = "SUCCESS"
INALTERADO = "UNCHANGED"
FALHA = "FAILURE"

# Pausa entre escritas para respeitar o limite de taxa do Notion (~3 req/s).
PAUSA_ENTRE_ESCRITAS = 1
# Aborta a execução após esta quantidade de falhas consecutivas (proteção).
LIMITE_FALHAS_CONSECUTIVAS = 10


def processar_base(client: notion.NotionClient, processar_item, *, pausar: bool,
                   tamanho_bloco: int, lista_ids: list,
                   nome_entidade: str, coluna_titulo: str, total: int = None) -> tuple:
    """
    Executa o processamento e devolve (sucessos, inalterados, sucessos_log, falhas_log).

    `sucessos_log` é uma lista de (nome, [mudanças]); `falhas_log`, de strings.
    `total` é o tamanho da base, se já conhecido (os scripts de CSV o obtêm na
    varredura de sincronização e o repassam, evitando uma segunda contagem). Quando
    None (caso do backup), a rota de base completa conta a base por conta própria.
    Encaminha para a rota de "lista específica" ou de "base completa" conforme
    `lista_ids` esteja preenchida ou não.
    """
    estado = {"sucessos": 0, "inalterados": 0, "consecutivos": 0}
    sucessos_log = []
    falhas_log = []

    # As listas de log são mutadas dentro das rotas; se um erro de autenticação do
    # TMDB interromper o laço no meio, o que já foi acumulado é preservado e ainda
    # vai para o arquivo de log (em vez de o script morrer sem registrar nada).
    try:
        if lista_ids:
            _rota_lista_especifica(client, processar_item, lista_ids,
                                   nome_entidade, estado, sucessos_log, falhas_log)
        else:
            _rota_base_completa(client, processar_item, pausar, tamanho_bloco,
                                nome_entidade, coluna_titulo, estado, sucessos_log, falhas_log, total)
    except TMDBAuthError as erro:
        print(f"\n🛑 INTERROMPIDO: {erro}")
        print("   O log do que já foi processado até aqui será salvo mesmo assim.")

    return estado["sucessos"], estado["inalterados"], sucessos_log, falhas_log


def _avaliar_resultado(status: str, info, nome_log: str,
                       estado: dict, sucessos_log: list, falhas_log: list) -> None:
    """Imprime o desfecho de um item e atualiza os contadores/registros compartilhados."""
    if status == SUCESSO:
        mudancas = info or []
        print(f"[{' | '.join(mudancas)}] - [Atualizado]")
        sucessos_log.append((nome_log, mudancas))
        estado["sucessos"] += 1
        estado["consecutivos"] = 0
    elif status == INALTERADO:
        print("[Inalterado - nada a escrever]")
        estado["inalterados"] += 1
        estado["consecutivos"] = 0
    else:  # FALHA
        print(f"[Falha: {info}]")
        falhas_log.append(f"{nome_log} ({info})")
        estado["consecutivos"] += 1


def _rota_lista_especifica(client, processar_item, lista_ids,
                           nome_entidade, estado, sucessos_log, falhas_log) -> None:
    """Processa apenas os IDs informados manualmente pelo usuário."""
    print(f"\n🚀 Processamento direcionado: {len(lista_ids)} item(ns).")
    print("-" * cli.LARGURA)

    for contador, imdb_id in enumerate(lista_ids, start=1):
        print(f"{nome_entidade} {contador:04d} - ID [{imdb_id}]...", end=" ", flush=True)

        page = client.buscar_por_imdb_id(imdb_id)
        if not page:
            print("[Falha: não localizado no Notion]")
            falhas_log.append(f"{imdb_id} (ausente no Notion)")
        else:
            status, info = processar_item(imdb_id, page)
            _avaliar_resultado(status, info, imdb_id, estado, sucessos_log, falhas_log)

        # Cada iteração faz ao menos uma busca no Notion, então sempre pausa.
        time.sleep(PAUSA_ENTRE_ESCRITAS)


def _rota_base_completa(client, processar_item, pausar, tamanho_bloco,
                        nome_entidade, coluna_titulo, estado, sucessos_log, falhas_log,
                        total=None) -> None:
    """Percorre toda a base do Notion, em blocos paginados."""
    # Reaproveita o total já conhecido (da varredura de sincronização); se não houver,
    # conta a base por conta própria (caso do script de backup, que não sincroniza).
    if total is None:
        total = client.contar_total()

    if total == "Desconhecido":
        print("⚠️ Não foi possível contar a base. Seguindo sem o total no painel.")
    else:
        print(f"✔️  Base remota mapeada: {total} registro(s) no Notion.")

    print(f"\n🚀 Iniciando processamento contínuo...")

    contador = 1
    cursor = None
    has_more = True

    while has_more:
        bloco, cursor, has_more = client.buscar_bloco(tamanho_bloco, cursor)
        if not bloco:
            break

        for page in bloco:
            titulo = notion.ler_titulo(page.get("properties", {}), coluna_titulo) or "Título Desconhecido"
            imdb_id = notion.extrair_imdb_id(page)

            if not imdb_id:
                print(f"{nome_entidade} {contador:04d} - {titulo} - [Falha: URL inválida no Notion]")
                falhas_log.append(f"{titulo} (URL inválida no Notion)")
                estado["consecutivos"] += 1
                contador += 1
                # Uma base só de URLs inválidas também deve disparar o aborto.
                if estado["consecutivos"] >= LIMITE_FALHAS_CONSECUTIVAS:
                    print(f"\n🛑 ABORTO DE SEGURANÇA: {LIMITE_FALHAS_CONSECUTIVAS} falhas consecutivas.")
                    return
                continue

            print(f"{nome_entidade} {contador:04d} - {titulo}...", end=" ", flush=True)
            status, info = processar_item(imdb_id, page)
            _avaliar_resultado(status, info, titulo, estado, sucessos_log, falhas_log)

            # Aborta se houver falhas demais em sequência (evita "queimar" a base).
            if estado["consecutivos"] >= LIMITE_FALHAS_CONSECUTIVAS:
                print(f"\n🛑 ABORTO DE SEGURANÇA: {LIMITE_FALHAS_CONSECUTIVAS} falhas consecutivas.")
                return

            contador += 1
            # Só pausa quando houve tentativa de escrita; itens inalterados passam direto.
            if status in (SUCESSO, FALHA):
                time.sleep(PAUSA_ENTRE_ESCRITAS)

        # Pausa para confirmação entre blocos (somente no modo "em blocos").
        if has_more and pausar:
            cli.imprimir_progresso(contador - 1, total)
            if not cli.confirmar_proximo_lote(tamanho_bloco):
                print("Operação encerrada pelo usuário.")
                return


def sincronizar_novos(criar_item, candidatos: list) -> tuple:
    """
    Pergunta, um a um, se cada candidato deve ser adicionado ao Notion e o cria.
    Retorna (adicionados_log, ignorados, falhas_log), onde `adicionados_log` é a
    lista dos nomes efetivamente adicionados (para o relatório e o log).

    Parâmetros:
        criar_item  Função `criar_item(imdb_id, row)` que cria a página no Notion e
                    devolve (status, mensagem). status: SUCESSO ou FALHA.
        candidatos  Lista (não vazia) de tuplas (imdb_id, row, descricao).
    """
    adicionados_log = []
    ignorados = 0
    falhas_log = []
    print("-" * cli.LARGURA)

    adicionar_todos = False
    total = len(candidatos)

    for indice, (imdb_id, row, descricao) in enumerate(candidatos, start=1):
        # Pede confirmação, a menos que o usuário já tenha escolhido "Todos".
        if not adicionar_todos:
            escolha = cli.perguntar_adicionar(indice, total, descricao)
            if escolha == "C":
                print("Sincronização cancelada pelo usuário. Itens restantes não foram adicionados.")
                break
            if escolha == "N":
                ignorados += 1
                continue
            if escolha == "T":
                adicionar_todos = True

        print(f"  ➕ Adicionando: {descricao}...", end=" ", flush=True)
        status, mensagem = criar_item(imdb_id, row)
        if status == SUCESSO:
            print("[Adicionado]")
            adicionados_log.append(descricao)
        else:
            print(f"[Falha: {mensagem}]")
            falhas_log.append(f"{descricao} ({mensagem})")

        time.sleep(PAUSA_ENTRE_ESCRITAS)

    return adicionados_log, ignorados, falhas_log
