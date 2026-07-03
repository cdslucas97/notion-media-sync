# Projeto: Notion Media Sync

## Objetivo final
Sistema unificado de rastreamento de mídias consumidas (Filmes, Séries, Livros, Jogos)
com o Notion como plataforma consolidada de consulta ("segundo cérebro"). Prioridade
absoluta: mínimo esforço manual recorrente. Simplicidade > completude. Custo zero.

## Arquitetura alvo (padrão unificado)
[Fonte com API] → normalizar → ID estável → diff contra Notion → gravar só o delta

- Um núcleo compartilhado (cliente Notion + lógica de delta + logging) — JÁ EXISTE (ver abaixo)
- Um adaptador por domínio: Trakt (filmes/séries), Hardcover (livros), Steam (jogos)
- Entrypoints finos por domínio consumindo o mesmo núcleo
- Enriquecimento por chamada individual SOMENTE em inserts (nunca N+1 na base inteira)

## Ambiente
- Pasta do projeto: C:\src\notion-media-sync (renomeada; nome antigo: notion-imdb-sync)
- Windows + PowerShell. Python 3.14 em venv local (.venv) — Agendador/Actions devem
  usar C:\src\notion-media-sync\.venv\Scripts\python.exe
- requirements.txt validado como completo: apenas requests e python-dotenv
  (cliente Notion é caseiro sobre requests — não há SDK do Notion)
- Credenciais em .env (NOTION_TOKEN, NOTION_DB_MOVIES, NOTION_DB_SERIES, TMDB_API_KEY),
  protegido por .gitignore

## Estado atual do código (legado a evoluir — mapa real)
- core/ modular já existente:
  config.py (credenciais/validação) · notion.py (cliente API Notion + retry) ·
  tmdb.py (cliente TMDB) · csv_loader.py (descoberta/leitura do CSV mais recente) ·
  bypass.py (correções manuais por ID) · status.py (regra do Status) ·
  diff.py (registro antigo→novo) · log.py (log por execução) ·
  cli.py (menus interativos e relatório) · runner.py (laço: paginação, delta,
  kill-switch após 10 falhas seguidas)
- Entrypoints atuais: atualizar_filmes_csv.py (principal) ·
  atualizar_series.py (CSV + TMDB) · atualizar_filmes_tmdb.py (backup sem CSV)
- Fluxo atual: CSV exportado do IMDb (pasta data/, usa o mais recente) → casa por
  código IMDb (coluna URL) → grava só o delta. TMDB enriquece séries
  (temporadas, episódios, anos) e serve de backup para filmes.
- Execução atual exige ~6 interações manuais (menus) — a eliminar.
- Base atual: 1.121 filmes no Notion · ~140 séries · CSV com 1.270 registros
  (filmes + séries juntos; cada script filtra o que lhe interessa)

## Databases no Notion (colunas exatas)
### Tabela de Filmes
Título do Filme (Title, PT-BR) | URL (URL; link IMDb = chave) | IMDb (Number, nota do
site) | Ano (Number) | Duração (Number, min) | Gêneros (Multi-select, PT-BR) |
Diretores (Multi-select) | Título Original (Text) | Status (tipo Status) |
Tag (interna do usuário — NUNCA tocar)

### Tabela de Séries
Título da Série (Title, PT-BR) | URL (URL) | Categoria (Select: Série/Minissérie) |
Gêneros (Multi-select, PT-BR) | IMDb (Number) | Ano de Início (Number) |
Ano de Fim (Number) | Temporadas (Number) | Episódios (Number) |
Título Original (Text) | Status (tipo Status)

## Comportamentos do sistema atual que DEVEM ser preservados
- Status é propriedade tipo "Status" do Notion: opções NÃO podem ser criadas via API
  (já existem, criadas à mão). Opções exatas:
  Filmes: Não Assistido · Reassistir · Na Fila · Assistido
  Séries: Não Assistido · Assistindo · Na Fila · Última Temporada Assistida · Assistido
- Regra de Status protege estados intencionais: nunca rebaixar Reassistir, Assistindo,
  Última Temporada Assistida. Lógica completa em core/status.py — REUTILIZAR, não recriar.
- Premissa do Status: usuário avalia tudo que consome (nota existente = assistido;
  watchlist sem nota = na fila / não assistido).
- core/bypass.py: correções manuais por ID IMDb sobrescrevem QUALQUER fonte.
  Todo adaptador novo DEVE aplicar o bypass após o enriquecimento.
- Sincronização NUNCA apaga itens do Notion; só adiciona/atualiza. Remoções são manuais.
- Itens novos herdam o ícone de uma página existente da base (visual padronizado).
- Gêneros/Diretores/Categoria: tags de Select/Multi-select criadas automaticamente
  pelo script conforme escreve.
- Números gravados puros (formatação de casas decimais é configuração do Notion).

## Fatos técnicos validados (não redescobrir)
- Trakt API: GET 1.000 chamadas/5min; POST/PUT/DELETE 1/segundo; tratar HTTP 429
- Endpoints bulk: /sync/ratings, /sync/history, /sync/watchlist (paginados, extended=full)
- /sync/last_activities = curto-circuito: se nada mudou, encerra com 1 GET
- extended=full de show inclui: aired_episodes, first_aired, status, genres (EN), ids
- extended=full NÃO inclui: diretores, temporadas, ano de fim, título PT-BR, flag minissérie
- Nota "IMDb" do Trakt = nota da comunidade Trakt (número diferente da nota do site IMDb)
- TMDB com language=pt-BR + append_to_response=credits preenche TODAS as lacunas acima
  em 1 chamada por título (título PT, diretores, temporadas, last_air_date, type=Miniseries)
- Gêneros: Trakt entrega slugs EN → traduzir via dicionário estático no código (zero API)
- Conta Trakt free: 100k histórico, 10k ratings, 250 watchlist — folga de décadas
- OAuth Trakt: renovar token SOMENTE quando expirado (há rate limit não documentado
  em reautenticações)
- Hardcover: API GraphQL gratuita (https://api.hardcover.app/v1/graphql), token
  estático, EM BETA (pode mudar sem aviso)
- Steam Web API: oficial, gratuita, estável. PSN: só API não-oficial (psnawp).
  Switch: sem API viável — manual por decisão

## Restrições invioláveis
- Custo zero (sem serviços pagos, sem VIP)
- Ambiente: Windows. Linguagem: Python. Dependências novas só com aprovação do usuário
- Nunca reintroduzir padrão N+1 sobre a base inteira (trauma: 20+ min de execução)
- Sem scrapers de sites sem API. Sem browser automation. Sem middleware no-code
- Benchmark de aceite: sincronização completa < 2 minutos; execução sem mudanças = 1 GET
- Backup local JSON dos dados crus do Trakt a cada sync com mudanças (anti lock-in),
  retenção dos últimos 10
- Nenhuma credencial em texto plano no repositório

## Decisões já tomadas
- Fonte da verdade filmes/séries: Trakt (substitui CSV do IMDb; gatilho = avaliar no app)
- Enriquecimento: TMDB pt-BR, só em inserts + re-enriquecimento periódico restrito a
  séries com status "returning series"
- Livros: Hardcover como fonte (greenfield — usuário não registra leituras hoje)
- Jogos: Steam automático; PlayStation experimental (psnawp, nunca pilar);
  Switch manual por decisão explícita
- Agendamento: Task Scheduler primeiro; GitHub Actions depois (mesmo repositório)

## Estado real da Fase 0 (corrigido após leitura do README/código)
- Núcleo modular JÁ EXISTE e está saudável (delta engine validada: execução repetida
  produz "Inalterado - nada a escrever"). O que resta da Fase 0:
  (1) modo não-assistido via flags/config substituindo as ~6 interações do cli.py;
  (2) interface formal de adaptador de fonte (fetch() → itens normalizados com ID estável);
  (3) plugar o fluxo CSV nessa interface como prova da abstração.

## Decisão PENDENTE (perguntar ao usuário quando relevante)
- Coluna "IMDb" (nota): proxy Trakt (grátis, vem no bulk) vs OMDb API só para itens
  novos + congelar as notas legadas
