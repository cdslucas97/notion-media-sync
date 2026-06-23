"""
Interface de linha de comando (CLI) padronizada.

Reúne tudo o que é exibido no terminal e lido do usuário, para que os três
scripts tenham exatamente o mesmo menu, o mesmo painel de progresso e o mesmo
relatório final. Cada script apenas informa a descrição dos modos.
"""

LARGURA = 60  # largura padrão das linhas decorativas


def exibir_cabecalho(titulo: str) -> None:
    """Imprime o cabeçalho de abertura do script."""
    print("=" * LARGURA)
    print(titulo)
    print("=" * LARGURA)


def _prompt_opcoes(opcoes: tuple) -> str:
    """Monta um texto natural a partir das opções: ('1','2','3') -> '1, 2 ou 3'."""
    return ", ".join(opcoes[:-1]) + f" ou {opcoes[-1]}"


def menu_interativo(descricao_completa: str, descricao_parcial: str, exemplo_ids: str,
                    descricao_status: str = "", permite_status: bool = True,
                    passo_inicial: int = 1) -> tuple:
    """
    Pergunta o TIPO de atualização e COMO processar a fila.

    Parâmetros:
        descricao_completa   O que o modo COMPLETA atualiza.
        descricao_parcial    O que o modo PARCIAL atualiza.
        exemplo_ids          Exemplos de IDs para o modo de lista específica.
        descricao_status     O que o modo STATUS atualiza (usado se permite_status).
        permite_status       Se True, exibe a opção de atualizar apenas o Status
                             (não faz sentido no backup, que não tem a nota do IMDb).
        passo_inicial        Número do primeiro passo exibido (os scripts de CSV já
                             usaram o passo 1 para a sincronização, então passam 2).

    Retorna a tupla (modo, pausar_blocos, tamanho_bloco, lista_ids).
    O modo pode ser "COMPLETA", "PARCIAL" ou "STATUS".
    """
    passo_tipo = passo_inicial
    passo_fluxo = passo_inicial + 1

    # ---- Tipo de atualização ----
    print(f"\n[PASSO {passo_tipo}] Selecione o tipo de atualização:")
    print(f"  [ 1 ] COMPLETA -> {descricao_completa}")
    print(f"  [ 2 ] PARCIAL  -> {descricao_parcial}")
    if permite_status:
        print(f"  [ 3 ] STATUS   -> {descricao_status}")

    opcoes_tipo = ("1", "2", "3") if permite_status else ("1", "2")
    mapa_modo = {"1": "COMPLETA", "2": "PARCIAL", "3": "STATUS"}
    while True:
        escolha = input(f"Digite {_prompt_opcoes(opcoes_tipo)}: ").strip()
        if escolha in opcoes_tipo:
            modo = mapa_modo[escolha]
            break
        print("❌ Entrada inválida.")

    # ---- Como processar a fila ----
    print(f"\n[PASSO {passo_fluxo}] Como deseja processar a fila?")
    print("  [ 1 ] Toda a base (processamento contínuo até o fim)")
    print("  [ 2 ] Toda a base (em blocos de 1 a 100, com pausa para confirmação)")
    print("  [ 3 ] Lista específica (informar os códigos IMDb manualmente)")

    opcoes_fluxo = ("1", "2", "3")
    while True:
        fluxo = input(f"Digite {_prompt_opcoes(opcoes_fluxo)}: ").strip()
        if fluxo in opcoes_fluxo:
            break
        print("❌ Entrada inválida.")

    lista_ids = []
    pausar_blocos = False
    tamanho_bloco = 100

    if fluxo == "3":
        print(f"\n📝 Informe os IDs do IMDb separados por vírgula (ex.: {exemplo_ids})")
        entrada = input("IDs: ").strip()
        # Mantém apenas códigos que começam com 'tt' (higieniza a entrada).
        lista_ids = [i.strip() for i in entrada.split(",") if i.strip().startswith("tt")]
        if not lista_ids:
            print("❌ Nenhum ID válido detectado. Encerrando.")
            raise SystemExit(1)
    else:
        pausar_blocos = (fluxo == "2")
        if pausar_blocos:
            tamanho_bloco = _perguntar_tamanho_bloco()

    return modo, pausar_blocos, tamanho_bloco, lista_ids


def confirmar(pergunta: str) -> bool:
    """Pergunta genérica de Sim/Não. Retorna True para 'S'."""
    while True:
        resposta = input(f"{pergunta} (S/N): ").strip().upper()
        if resposta in ("S", "N"):
            return resposta == "S"
        print("❌ Responda com S ou N.")


def _perguntar_tamanho_bloco() -> int:
    """Pergunta quantos itens processar por bloco (limite de 100 imposto pelo Notion)."""
    while True:
        try:
            tamanho = int(input("\nQuantos itens por bloco? (informe um número de 1 a 100): ").strip())
            if 1 <= tamanho <= 100:
                return tamanho
            print("❌ Valor fora do intervalo. O Notion aceita de 1 a 100 itens por lote.")
        except ValueError:
            print("❌ Digite um número inteiro.")


def imprimir_progresso(processados: int, total) -> None:
    """Exibe o painel de progresso entre blocos."""
    restantes = total - processados if isinstance(total, int) else "Desconhecido"
    print("\n" + "-" * LARGURA)
    print(f"📋  PROGRESSO  ·  Processados: {processados}  ·  Restantes: {restantes}  ·  Total: {total}")
    print("-" * LARGURA)


def confirmar_proximo_lote(tamanho: int) -> bool:
    """Pergunta se o usuário autoriza processar o próximo bloco. Retorna True/False."""
    while True:
        resposta = input(f"Autorizar o próximo lote de {tamanho} itens? (S/N): ").strip().upper()
        if resposta in ("S", "N"):
            return resposta == "S"
        print("❌ Comando não reconhecido. Digite 'S' ou 'N'.")


def _linha_relatorio(rotulo: str, valor) -> None:
    """
    Imprime uma linha 'rótulo ......... valor' com o valor alinhado em coluna fixa.
    O alinhamento é feito sobre o texto (sem emojis no meio), para não depender da
    largura de emojis — que varia entre terminais e desalinharia a coluna.
    """
    print(f"  {rotulo:.<32} {valor}")


# No relatório de tela, lista no máximo esta quantidade de itens atualizados
# (o arquivo de log guarda a lista completa, sem corte).
MAX_LISTAGEM_RELATORIO = 30


def imprimir_relatorio(sucessos: int, inalterados: int, sucessos_log: list,
                       falhas: list, caminho_log: str = None) -> None:
    """Imprime o relatório de auditoria ao final da execução."""
    print("\n" + "=" * LARGURA)
    print("📊  RELATÓRIO DE EXECUÇÃO DA SESSÃO")
    print("=" * LARGURA)
    _linha_relatorio("Atualizados com sucesso ", sucessos)
    _linha_relatorio("Inalterados (já em dia) ", inalterados)
    _linha_relatorio("Falhas / não processados ", len(falhas))

    if sucessos_log:
        print("\n--- Itens atualizados e o que mudou ---")
        for indice, (nome, mudancas) in enumerate(sucessos_log[:MAX_LISTAGEM_RELATORIO], start=1):
            print(f"  {indice:>3}. {nome}")
            for mudanca in mudancas:
                print(f"        - {mudanca}")
        restantes = len(sucessos_log) - MAX_LISTAGEM_RELATORIO
        if restantes > 0:
            print(f"  ... e mais {restantes} item(ns) — veja o log completo.")

    if falhas:
        print("\n--- Entradas não processadas ---")
        for falha in falhas:
            print(f"  - {falha}")

    if caminho_log:
        print(f"\n📄 Log detalhado salvo em: {caminho_log}")
    print("=" * LARGURA)


def perguntar_adicionar(indice: int, total: int, descricao: str) -> str:
    """
    Pergunta se um item novo deve ser adicionado ao Notion.
    Retorna 'S' (sim), 'N' (não), 'T' (adicionar todos os restantes) ou 'C' (cancelar).
    """
    print(f"\n[{indice}/{total}] {descricao}")
    while True:
        resposta = input("Adicionar ao Notion? [S]im / [N]ão / [T]odos / [C]ancelar: ").strip().upper()
        if resposta in ("S", "N", "T", "C"):
            return resposta
        print("❌ Responda com S, N, T ou C.")


def imprimir_relatorio_sincronizacao(adicionados: int, ignorados: int, falhas: list) -> None:
    """Imprime o relatório ao final da sincronização de itens novos."""
    print("\n" + "=" * LARGURA)
    print("📊  RELATÓRIO DE SINCRONIZAÇÃO (ITENS NOVOS)")
    print("=" * LARGURA)
    _linha_relatorio("Adicionados ao Notion ", adicionados)
    _linha_relatorio("Ignorados (você não quis) ", ignorados)
    _linha_relatorio("Falhas ", len(falhas))

    if falhas:
        print("\n--- Detalhamento das falhas ---")
        for falha in falhas:
            print(f"  - {falha}")
    print("=" * LARGURA)
