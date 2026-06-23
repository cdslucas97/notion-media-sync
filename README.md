# 🎬 Automação Notion + IMDb

Mantém atualizadas automaticamente as suas bases de **Filmes** e **Séries** no
[Notion](https://www.notion.so/), preenchendo nota, ano, duração, gêneros,
diretores, temporadas, episódios e mais — a partir do CSV exportado do
[IMDb](https://www.imdb.com/) e da API do [TMDB](https://www.themoviedb.org/).

> **Nunca usou nada parecido?** Sem problema. Este guia foi escrito passo a passo,
> do zero, sem assumir conhecimento técnico. Siga as seções na ordem.

---

## 🧭 Como funciona (em 1 minuto)

1. Você mantém no Notion duas tabelas (uma de filmes, outra de séries). Cada linha
   tem o **link do IMDb** do título.
2. Você exporta a sua lista do IMDb num arquivo **`.csv`** e salva na pasta do projeto.
3. Você roda um script. Ele lê o CSV, encontra cada título no Notion (pelo link) e
   **preenche as colunas automaticamente**.
4. Nas próximas vezes, ele atualiza **só o que mudou** — então é bem rápido.

A "fonte da verdade" dos dados é **sempre o CSV do IMDb**. O TMDB é usado só para
informações que o IMDb não fornece (número de temporadas, episódios e o ano de
encerramento das séries).

---

## ✅ Antes de começar, você vai precisar de

- [ ] **Python 3.10 ou superior** instalado ([download](https://www.python.org/downloads/) —
      no Windows, marque a opção **"Add Python to PATH"** durante a instalação).
- [ ] Uma conta no **Notion**.
- [ ] Uma conta no **TMDB** (gratuita) — usada pelas séries e pelo script de backup.
- [ ] Cerca de **15 minutos** para a configuração inicial (só na primeira vez).

---

## 📚 Índice

1. [Instalação](#1-instalação)
2. [Configurar o Notion](#2-configurar-o-notion)
3. [Obter a chave do TMDB](#3-obter-a-chave-do-tmdb)
4. [Preencher o arquivo `.env`](#4-preencher-o-arquivo-env)
5. [Exportar o CSV do IMDb](#5-exportar-o-csv-do-imdb)
6. [Rodar os scripts](#6-rodar-os-scripts)
7. [Adicionar itens novos do CSV](#-adicionar-itens-novos-do-csv-passo-1)
8. [Status automático](#-status-automático-assistido--não-assistido)
9. [Entendendo os scripts](#-entendendo-os-scripts)
10. [Estrutura do projeto](#-estrutura-do-projeto)
11. [Solução de problemas](#-solução-de-problemas)
12. [Bypass manual](#-bypass-manual-correções-pontuais)

---

## 1. Instalação

Abra o terminal (no Windows, use o **PowerShell**) **na pasta do projeto** e rode,
um comando por vez:

```bash
# 1. Crie um ambiente virtual (uma "caixinha" isolada para as dependências)
python -m venv .venv

# 2. Ative o ambiente
#    Windows (PowerShell):
.venv\Scripts\Activate.ps1
#    Linux / macOS:
source .venv/bin/activate

# 3. Instale as dependências do projeto
pip install -r requirements.txt
```

> ✔️ **Como sei que deu certo?** Após ativar o ambiente, o início da linha do
> terminal passa a mostrar `(.venv)`. Você só precisa **ativar o ambiente** (passo 2)
> nas próximas vezes que for usar — os passos 1 e 3 são só na primeira vez.

---

## 2. Configurar o Notion

São quatro pequenas tarefas: **(2.1)** criar uma integração, **(2.2)** montar as
tabelas, **(2.3)** conectar a integração às tabelas e **(2.4)** copiar os IDs.

### 2.1 — Criar a integração (gera o seu "token")

A integração é o "crachá" que dá ao script permissão para escrever no seu Notion.

1. Acesse **https://www.notion.so/my-integrations**.
2. Clique em **➕ New integration** (Nova integração).
3. Dê um nome (ex.: `Automação IMDb`), escolha o seu workspace e clique em **Save**.
4. Na tela seguinte, copie o **Internal Integration Secret** (Segredo interno).
   - É um texto longo começando com `ntn_` ou `secret_`.
   - **Guarde-o** — será o valor de `NOTION_TOKEN` mais adiante.

### 2.2 — Montar as tabelas (bases de dados)

Você vai criar **duas bases de dados** no Notion: uma para filmes e outra para séries.
No Notion, "base de dados" é simplesmente uma **tabela**. Siga os passos abaixo para
cada uma.

#### a) Criar a tabela

1. No Notion, crie uma **página nova** (botão **+ New page**, na barra lateral).
2. Dê um nome à página (ex.: `Filmes`).
3. No corpo da página, digite `/` e escolha **Table - Full page**
   (em português, **Tabela - Página inteira**). Pronto: você tem uma tabela vazia.

> Uma tabela nova já vem com duas colunas de exemplo (geralmente `Name` e `Tags`).
> Você vai **renomear/ajustar** essas e **adicionar** as demais nos próximos passos.

#### b) Configurar a coluna de título

Toda tabela tem **uma** coluna especial do tipo **Title** (Título) — ela não pode ser
apagada, só renomeada. Clique no cabeçalho da coluna `Name` e renomeie para:

- **`Título do Filme`** (na base de filmes) ou **`Título da Série`** (na base de séries).

#### c) Adicionar as demais colunas

Para cada coluna da lista abaixo: clique no **`+`** à direita dos cabeçalhos
(**+ New property** / **+ Nova propriedade**), digite o **nome exato** e escolha o
**tipo** indicado.

> ⚠️ **Os nomes precisam ser idênticos** aos da tabela (com acentos e maiúsculas
> exatamente como mostrado) — é assim que o script encontra cada campo. Se uma coluna
> já existir com outro nome, basta renomeá-la.

**Base de FILMES**

| Nome da coluna (exato) | Tipo no Notion | O que guarda |
|---|---|---|
| `Título do Filme` | Title (Título) | Nome do filme |
| `URL` | URL | Link do filme no IMDb (ver nota abaixo) |
| `IMDb` | Number (Número) | Nota do IMDb |
| `Ano` | Number | Ano de lançamento |
| `Duração` | Number | Duração em minutos |
| `Gêneros` | Multi-select (Multisseleção) | Gêneros (uma ou várias tags) |
| `Diretores` | Multi-select | Diretor(es) |
| `Título Original` | Text (Texto) | Título no idioma original |
| `Status` | Status | Assistido / não assistido (ver nota abaixo) |

**Base de SÉRIES**

| Nome da coluna (exato) | Tipo no Notion | O que guarda |
|---|---|---|
| `Título da Série` | Title | Nome da série |
| `URL` | URL | Link da série no IMDb (ver nota abaixo) |
| `Categoria` | Select (Seleção) | `Série` ou `Minissérie` |
| `Gêneros` | Multi-select | Gêneros (uma ou várias tags) |
| `IMDb` | Number | Nota do IMDb |
| `Ano de Início` | Number | Ano da 1ª temporada |
| `Ano de Fim` | Number | Ano de encerramento (só se já terminou) |
| `Temporadas` | Number | Total de temporadas |
| `Episódios` | Number | Total de episódios |
| `Título Original` | Text | Título no idioma original |
| `Status` | Status | Em que ponto você está (ver nota abaixo) |

#### A coluna `Status` e suas opções

`Status` é uma propriedade do **tipo Status** do Notion (com os grupos *A fazer /
Em andamento / Concluídos*). **Diferente de Select/Multi-select, as opções de um
Status NÃO podem ser criadas pela API** — então você precisa criá-las uma vez, à mão,
no Notion. Crie exatamente estas opções:

**Filmes:** `Não Assistido` · `Reassistir` · `Na Fila` · `Assistido`
**Séries:** `Não Assistido` · `Assistindo` · `Na Fila` · `Última Temporada Assistida` · `Assistido`

Como o script decide o `Status` está explicado na seção
[Status automático](#-status-automático-assistido--não-assistido).

#### Notas importantes

- 💡 **A coluna `URL` é a chave de tudo.** Ela deve conter o link do título no IMDb,
  por exemplo `https://www.imdb.com/title/tt0903747/`. O script lê o código `tt…`
  desse link para casar a linha do Notion com a linha do CSV. **Sem o link, a linha é
  ignorada.** É a única coluna que você preenche manualmente; o resto o script preenche.
- 🏷️ **Select e Multi-select:** você **não** precisa criar as opções (tags) à mão.
  O script cria automaticamente as tags de `Gêneros`, `Diretores` e `Categoria`
  conforme vai escrevendo.
- 🔢 **Number:** o script grava o número puro. Se quiser exibir casas decimais (ex.:
  na nota `IMDb`), ajuste isso nas opções da coluna no Notion — não afeta o script.
- 🔁 **Pode reaproveitar tabelas que você já tem.** Não precisa começar do zero: basta
  garantir que as colunas existam com **estes nomes e tipos** (renomeie as que diferirem).

### 2.3 — Conectar a integração às tabelas

Mesmo tendo o token, a integração ainda **não enxerga** suas tabelas até você
liberá-las explicitamente. Para cada uma das duas bases:

1. Abra a base no Notion.
2. Clique em **•••** (três pontos, canto superior direito).
3. Vá em **Connections** (Conexões) → **Connect to** e selecione a integração que
   você criou (ex.: `Automação IMDb`).

> ⚠️ **Esqueceu deste passo?** É a causa nº 1 de erro. Sem conectar, o script recebe
> "não localizado / sem permissão" mesmo com o token correto.

### 2.4 — Copiar os IDs das bases

Cada base tem um identificador único na sua URL. Abra a base no navegador e olhe o endereço:

```
https://www.notion.so/SEU_WORKSPACE/<ESTE_PEDAÇO_DE_32_CARACTERES>?v=...
                                     └────────── é o ID da base ──────────┘
```

- O ID são os **32 caracteres** logo após a última barra `/` e **antes** do `?v=`.
- Anote o da base de **filmes** (vira `NOTION_DB_MOVIES`) e o da base de **séries**
  (vira `NOTION_DB_SERIES`).

---

## 3. Obter a chave do TMDB

1. Crie uma conta gratuita em **https://www.themoviedb.org/**.
2. Acesse **https://www.themoviedb.org/settings/api**.
3. Solicite uma chave de uso pessoal (**Developer**) e copie a **API Key (v3 auth)**.
   - Esse será o valor de `TMDB_API_KEY`.

---

## 4. Preencher o arquivo `.env`

O `.env` é onde ficam as suas chaves secretas. Há um modelo pronto (`.env.example`).

1. Faça uma cópia do modelo com o nome `.env`:
   ```bash
   cp .env.example .env
   ```
   (No Windows, se preferir, copie e cole o arquivo e renomeie para `.env`.)
2. Abra o `.env` em qualquer editor de texto e cole os valores que você coletou:

   ```dotenv
   NOTION_TOKEN=ntn_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   NOTION_DB_MOVIES=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   NOTION_DB_SERIES=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TMDB_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

> 🔒 O `.env` **nunca** é enviado ao Git (já está protegido no `.gitignore`).
> Não compartilhe esse arquivo com ninguém.

---

## 5. Exportar o CSV do IMDb

Os scripts de filmes e séries leem os dados de um arquivo `.csv` exportado do IMDb:

1. Faça login no **https://www.imdb.com/**.
2. Abra a lista que quer exportar — sua **Watchlist**, uma lista personalizada ou
   **Your Ratings** (Suas Avaliações).
3. Clique no menu **•••** (ou no botão **Export**) e escolha **Export**.
4. O IMDb baixa um arquivo `.csv` (o nome costuma ser uma sequência aleatória, como
   `ls012345678.csv`). **Salve esse arquivo na pasta `data/`** do projeto.
5. Pode acumular vários exports ali — o script **usa sempre o mais recente**
   (pela data do arquivo) e informa no início qual foi escolhido, por exemplo:
   ```
   ✔️  CSV mais recente detectado: 'data/ls012345678.csv' (modificado em 23/06/2026 21:14)
   ```

> 💡 O mesmo CSV traz filmes **e** séries. Cada script aproveita só as linhas que lhe
> interessam, então não é preciso separar.
>
> 🗂️ Manter o histórico na pasta `data/` é proposital: serve de backup e permite
> reprocessar um estado anterior se precisar. Os arquivos não vão para o Git.

---

## 6. Rodar os scripts

Com o ambiente ativo (lembra do `(.venv)`?), o `.env` preenchido e o CSV na pasta:

```bash
python atualizar_filmes_csv.py     # Filmes (principal)
python atualizar_series.py         # Séries
python atualizar_filmes_tmdb.py    # Filmes via TMDB (backup — só se não tiver o CSV)
```

Os scripts seguem o **mesmo fluxo**, em três passos:

**Passo 1 — Itens novos do CSV** (só nos scripts que usam CSV)

O script verifica se há filmes/séries no CSV que ainda não estão no Notion. Se houver,
ele pergunta se você quer adicioná-los (ver [Adicionar itens novos](#-adicionar-itens-novos-do-csv-passo-1)).
Se não houver — ou após adicioná-los — segue direto para os próximos passos.

**Passo 2 — Tipo de atualização** (dos itens já existentes)

| Opção | O que atualiza |
|---|---|
| **COMPLETA** | Tudo: títulos, gêneros, diretores, números **e o `Status`**. |
| **PARCIAL** | Só os campos numéricos (nota, ano, duração / temporadas, episódios, anos). |
| **STATUS** | **Apenas a coluna `Status`** (ver [Status automático](#-status-automático-assistido--não-assistido)). |

> A opção **STATUS** não aparece no script de backup TMDB (ele não tem acesso à sua
> nota do IMDb, que é o que define o status).

**Passo 3 — Como processar a fila**

| Opção | Quando usar |
|---|---|
| **Toda a base (contínuo)** | O caso normal: processa tudo de uma vez. |
| **Toda a base (em blocos)** | Faz uma pausa a cada N itens (de 1 a 100) e pede confirmação para seguir. |
| **Lista específica** | Você digita só os códigos `tt…` que quer atualizar. |

Ao final, aparece um **relatório**: quantos foram atualizados, quantos já estavam em
dia (pulados), **a lista dos itens atualizados com o que mudou** (ex.: `Nota: 7.8 → 8.3`)
e o detalhe das falhas. O registro **completo** de cada execução também é salvo em um
arquivo na pasta `logs/` (ex.: `logs/filmes_2026-06-23_2145.txt`) — incluindo os itens
**adicionados** (Passo 1) e os **atualizados** (Passos 2-3) — assim você não perde nada
quando o terminal rola.

> ⚡ **Por que a 2ª vez é tão mais rápida?** O script compara cada título com o que já
> está no Notion e **só escreve o que mudou**. Numa base já sincronizada, quase tudo é
> pulado em segundos.

---

## ➕ Adicionar itens novos do CSV (Passo 1)

Logo ao iniciar, o script compara o CSV com a sua base do Notion. Se encontrar filmes/
séries que estão no CSV **mas ainda não existem no Notion**, ele avisa e pergunta se
você quer adicioná-los — assim você não precisa cadastrar o nome e a URL à mão:

```
🆕 Encontrei 8 filme(s) novo(s) no CSV.
Deseja revisá-los para adicionar agora? (S/N): S

[1/8] Duna: Parte Dois (2024) — Filme
Adicionar ao Notion? [S]im / [N]ão / [T]odos / [C]ancelar:
```

Se você responder **N** à primeira pergunta (ou se não houver itens novos), o script
segue direto para a atualização (Passos 2 e 3).

- **S** adiciona só este item · **N** pula · **T** adiciona todos os restantes sem
  perguntar · **C** cancela o restante.
- Os itens são criados **já preenchidos** (título, nota, gêneros, URL etc.) — você não
  precisa digitar nada.
- O script de filmes só oferece filmes; o de séries, só séries.
- 🎨 Os novos itens **herdam o ícone** de uma página já existente na base, mantendo o
  visual padronizado (funciona com os "Ícones" embutidos do Notion). Se a base estiver
  vazia, o item nasce sem ícone e passa a herdá-lo nas próximas sincronizações.

> 🛡️ **E os itens que eu não quero?** A confirmação item a item existe justamente
> para isso: basta responder **N**. E se um título que você removeu do Notion ainda
> aparece aqui, é porque ele continua na sua última exportação do IMDb — **remova-o da
> sua lista no IMDb e exporte o CSV de novo**; aí ele deixa de ser oferecido.

> ℹ️ A sincronização **não apaga** nada: ela só adiciona. Remoções continuam sendo
> feitas por você, no IMDb (e refletidas no próximo export) e/ou diretamente no Notion.

---

## 👁️ Status automático (assistido / não assistido)

O script ajusta a coluna `Status` com base na sua **nota no IMDb**: se a coluna
"Your Rating" do CSV está preenchida, você assistiu ao título. Mas ele **nunca
sobrescreve um status que você marcou de propósito** (como `Reassistir`).

O `Status` é atualizado no modo **COMPLETA** (junto com o resto) ou no modo **STATUS**
(sozinho, sem mexer em mais nada). O modo **PARCIAL** não toca no `Status`.

**Filmes**

| Nota no IMDb | Status atual | Resultado |
|---|---|---|
| Tem nota | `Assistido` ou `Reassistir` | mantém |
| Tem nota | qualquer outro (`Não Assistido`, `Na Fila`, vazio) | → **`Assistido`** |
| Sem nota | `Não Assistido` ou `Na Fila` | mantém |
| Sem nota | qualquer outro (`Assistido`, `Reassistir`, vazio) | → **`Não Assistido`** |

**Séries** (protege também os estados "em andamento / em dia")

| Nota no IMDb | Status atual | Resultado |
|---|---|---|
| Tem nota | `Assistido`, `Assistindo` ou `Última Temporada Assistida` | mantém |
| Tem nota | `Não Assistido`, `Na Fila` ou vazio | → **`Assistido`** |
| Sem nota | `Não Assistido`, `Na Fila`, `Assistindo` ou `Última Temporada Assistida` | mantém |
| Sem nota | `Assistido` ou vazio | → **`Não Assistido`** |

> ⚠️ **Premissa importante:** isto assume que você **dá nota a tudo que assiste**.
> Um item marcado `Assistido` mas **sem** nota no IMDb seria rebaixado para
> `Não Assistido`. Se às vezes você assiste sem avaliar, dê a nota no IMDb antes de rodar.
>
> 🎬 Para um item recém-adicionado (sincronização), o status já nasce certo: com nota
> → `Assistido`; sem nota → `Não Assistido`.

---

## 🧩 Entendendo os scripts

| Script | Para quê | Fonte dos dados |
|---|---|---|
| **`atualizar_filmes_csv.py`** | Filmes (principal) | CSV do IMDb |
| **`atualizar_filmes_tmdb.py`** | Filmes (backup, quando não há CSV) | API do TMDB |
| **`atualizar_series.py`** | Séries | CSV do IMDb **+** API do TMDB |

> **Por que dois scripts de filmes?** O `..._csv.py` é o preferido: usa a nota oficial
> do IMDb e não depende de nenhuma API. O `..._tmdb.py` é só um _backup_ para quando
> você não tem o CSV — e usa a nota do **TMDB**, que difere um pouco da do IMDb.

---

## 🗂️ Estrutura do projeto

```
notion-imdb-sync/
├── core/                      # Lógica compartilhada (cada arquivo, uma função)
│   ├── config.py             #   Credenciais do .env e validação
│   ├── notion.py             #   Cliente da API do Notion (+ retry) e leitura de campos
│   ├── tmdb.py               #   Cliente da API do TMDB
│   ├── csv_loader.py         #   Descoberta e leitura do CSV do IMDb
│   ├── bypass.py             #   Correções manuais (sobrescrita de dados)
│   ├── status.py             #   Regra do Status (assistido / não assistido)
│   ├── diff.py               #   Registro das alterações (antigo → novo)
│   ├── log.py                #   Gravação do log de cada execução
│   ├── cli.py                #   Menu padronizado e relatório
│   └── runner.py             #   Laço de processamento (paginação, delta, kill-switch)
├── atualizar_filmes_csv.py    # Entrypoint: filmes via CSV (principal)
├── atualizar_filmes_tmdb.py   # Entrypoint: filmes via TMDB (backup)
├── atualizar_series.py        # Entrypoint: séries (CSV + TMDB)
├── data/                      # Onde você salva os CSVs do IMDb (usa-se o mais recente)
├── logs/                      # Logs de cada execução (gerados automaticamente)
├── requirements.txt
├── .env.example               # Modelo de configuração (copie para .env)
└── README.md
```

---

## 🩺 Solução de problemas

| Mensagem / sintoma | Causa provável e solução |
|---|---|
| `ERRO DE CONFIGURAÇÃO: variáveis ausentes` | Alguma variável do `.env` está vazia. Reveja a [seção 4](#4-preencher-o-arquivo-env). |
| `Nenhum arquivo .csv foi encontrado` | O export do IMDb não está na pasta `data/`. Veja a [seção 5](#5-exportar-o-csv-do-imdb). |
| `não localizado no Notion` (lista específica) | O `tt…` não existe na base, **ou** a base não foi conectada à integração ([2.3](#23--conectar-a-integração-às-tabelas)). |
| `URL inválida no Notion` | A linha não tem um link do IMDb válido na coluna `URL`. |
| `não localizado no TMDB` | O título não existe no TMDB (raro) ou a `TMDB_API_KEY` está incorreta. |
| Erro 401 / 404 / falha de escrita | Token errado, **ou** a base não foi compartilhada com a integração ([2.3](#23--conectar-a-integração-às-tabelas)). |
| `python` não é reconhecido (Windows) | O Python não foi adicionado ao PATH. Reinstale marcando **"Add Python to PATH"**. |
| Aborto após 10 falhas seguidas | Proteção automática. Confira credenciais e os nomes exatos das colunas ([2.2](#22--montar-as-tabelas-bases-de-dados)). |

---

## 🔒 Bypass manual (correções pontuais)

Quando o IMDb/TMDB traz um dado errado, você pode forçar o valor correto **sem editar
o CSV**. Todas as correções ficam centralizadas em **`core/bypass.py`**, que tem dois
dicionários — porque as colunas de filmes e de séries são diferentes:

```python
# core/bypass.py
BYPASS_FILMES = {
    "tt8781928": {"Duração": 86},
    "tt0381061": {"Título do Filme": "007 - Cassino Royale"},
}
BYPASS_SERIES = {
    "tt2802850": {"Ano de Fim": 2024},  # Fargo
}
```

- A chave externa é o **código IMDb** (ex.: `tt0381061`); as chaves internas são os
  **nomes das colunas** do Notion. O valor informado sobrescreve o que veio da fonte.
- `BYPASS_FILMES` vale para **os dois** scripts de filmes (principal e backup), já que
  ambos escrevem na mesma base. `BYPASS_SERIES` vale para as séries.
- Use em cada dicionário apenas as colunas daquela tabela — o próprio `core/bypass.py`
  lista as chaves válidas de cada um. Para `Gêneros`/`Diretores`, informe uma string
  separada por vírgulas (ex.: `"Ação, Comédia"`).
