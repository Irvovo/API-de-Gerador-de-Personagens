# Documentação da API de Gerador de Personagens

API REST para cadastrar e gerenciar os elementos de um RPG: **armas**, **classes**, **fraquezas**, **habilidades** e **personagens**. Os personagens combinam os demais recursos, e a API também sorteia um personagem sozinha.

- **Versão:** 2.0.0
- **Tecnologias:** Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2, SQLite, JWT (PyJWT) e RBAC
- **Base URL local:** `http://localhost:8000/api/v1`
- **Documentação interativa (Swagger):** `http://localhost:8000/docs`
- **Contrato OpenAPI (JSON):** `http://localhost:8000/openapi.json`

---

## Sumário

1. [Como executar](#1-como-executar)
2. [Convenções gerais](#2-convenções-gerais)
3. [Autenticação e autorização](#3-autenticação-e-autorização)
4. [Formato dos erros](#4-formato-dos-erros)
5. [Recursos e campos](#5-recursos-e-campos)
6. [Referência dos endpoints](#6-referência-dos-endpoints)
7. [Personagem aleatório](#7-personagem-aleatório)
8. [Regras de negócio](#8-regras-de-negócio)
9. [Variáveis de ambiente](#9-variáveis-de-ambiente)
10. [Dados iniciais (seed)](#10-dados-iniciais-seed)
11. [Exemplo de uso completo](#11-exemplo-de-uso-completo)
12. [Servidor MCP (usar pelo Claude)](#12-servidor-mcp-usar-pelo-claude)

---

## 1. Como executar

### Local (Python)

```bash
python -m venv .venv
.venv\Scripts\activate                       # Windows (Linux/Mac: source .venv/bin/activate)
pip install -r src/api/requirements.txt
uvicorn src.api.main:app --reload
```

Ao iniciar, a API cria as tabelas do banco SQLite (`gerador_personagens.db`) e os dados iniciais, se o banco estiver vazio.

### Com Docker

```bash
cp .env.example .env          # PowerShell: Copy-Item .env.example .env
docker compose up --build
```

A API fica em `http://localhost:8000`. Veja o `README-DOCKER.md` para o passo a passo completo.

### Testes

```bash
pip install -r src/mcp_server/requirements.txt   # necessário para os testes do MCP
pytest                                           # 212 testes
```

---

## 2. Convenções gerais

| Item | Regra |
| ---- | ----- |
| Formato | JSON em requisições e respostas (`Content-Type: application/json` é **obrigatório** em `POST` e `PUT`, mesmo sem corpo; senão, `400`) |
| Prefixo | Todas as rotas ficam sob `/api/v1`, com os recursos no plural |
| IDs | Inteiros gerados pela API, a partir de 1 |
| Nomes de campos | `camelCase` nos corpos de entrada e saída (`classeId`, `habilidadeIds`, `accessToken`) |
| Atualização (`PUT`) | Substitui o registro inteiro: todos os campos devem ser enviados |
| Exclusão (`DELETE`) | Responde `204` sem corpo |
| Ordenação | Listagens ordenadas por `id` crescente |

### Paginação e filtro (todas as listagens)

| Parâmetro | Padrão | Regra |
| --------- | ------ | ----- |
| `pagina` | 1 | Inteiro ≥ 1 |
| `limite` | 10 | Inteiro de 1 a 100 |
| `nome` | — | Texto de 1 a 80 caracteres; filtra registros cujo nome **contém** o texto (sem diferenciar maiúsculas de minúsculas; só vale para letras sem acento) |

Resposta de uma listagem:

```json
{
  "itens": [ { "id": 1, "nome": "Espada longa", "dano": 25, "tipo": "corpo_a_corpo" } ],
  "pagina": 1,
  "limite": 10,
  "total": 3
}
```

`total` é a quantidade de registros em **todas** as páginas (já considerando o filtro `nome`).

---

## 3. Autenticação e autorização

Todas as rotas, exceto `POST /auth/login`, exigem um token JWT no cabeçalho:

```
Authorization: Bearer <accessToken>
```

### POST `/api/v1/auth/login` (público)

Corpo:

```json
{ "email": "admin@example.com", "senha": "Admin@123" }
```

| Campo | Regra |
| ----- | ----- |
| `email` | 3 a 254 caracteres (comparado sem diferenciar maiúsculas) |
| `senha` | 1 a 128 caracteres |

Resposta `200`:

```json
{ "accessToken": "<JWT>", "tokenType": "bearer", "expiresIn": 3600 }
```

`expiresIn` está em segundos (o token vale **60 minutos**). Credenciais erradas retornam `401` com a mesma mensagem, exista o e-mail ou não.

O token é assinado com HS256 e leva no corpo: `sub` (ID do usuário), `email`, `role`, `iat` e `exp`.

### GET `/api/v1/auth/me`

Retorna o usuário do token:

```json
{ "id": 1, "nome": "Administrador", "email": "admin@example.com", "role": "ADMIN" }
```

### Papéis (RBAC)

| Operação | ADMIN | MEMBER |
| -------- | :---: | :----: |
| `GET` (listar e buscar) | ✅ | ✅ |
| `POST` (criar) | ✅ | ✅ |
| `PUT` (atualizar) | ✅ | ✅ |
| `DELETE` (excluir) | ✅ | ❌ `403` |

Token ausente, malformado, expirado ou de um usuário que não existe mais retorna `401`.

---

## 4. Formato dos erros

**Todo** erro tem o mesmo formato (nunca o `{"detail": ...}` padrão do FastAPI):

```json
{
  "status": 404,
  "codigo": "ARMA_NAO_ENCONTRADA",
  "mensagem": "Não existe arma com o ID informado."
}
```

### 400 x 422

- **`400`: requisição malformada.** JSON inválido, `Content-Type` diferente de JSON, tipo errado no path ou na query (por exemplo, `/armas/abc`).
- **`422`: dados bem formados que violam alguma regra.** Tamanho, faixa, valor fora do enum, campo obrigatório ausente, `id` igual a 0, ou referência a um registro que não existe. A mensagem cita o campo, por exemplo: `Dados inválidos — nome: String should have at least 4 characters.`

### Códigos de erro

| Status | `codigo` | Quando acontece |
| ------ | -------- | --------------- |
| 400 | `REQUISICAO_INVALIDA` | JSON malformado, `Content-Type` incorreto, tipo errado em path/query |
| 401 | `NAO_AUTENTICADO` | Token ausente, inválido ou expirado; login com credenciais erradas |
| 403 | `ACESSO_NEGADO` | Papel sem permissão (`MEMBER` em `DELETE`) |
| 404 | `ARMA_NAO_ENCONTRADA` | `id` de arma inexistente |
| 404 | `CLASSE_NAO_ENCONTRADA` | `id` de classe inexistente |
| 404 | `FRAQUEZA_NAO_ENCONTRADA` | `id` de fraqueza inexistente |
| 404 | `HABILIDADE_NAO_ENCONTRADA` | `id` de habilidade inexistente |
| 404 | `PERSONAGEM_NAO_ENCONTRADO` | `id` de personagem inexistente |
| 404 | `ROTA_NAO_ENCONTRADA` | Rota que não existe |
| 405 | `METODO_NAO_PERMITIDO` | Método HTTP não suportado na rota |
| 409 | `RECURSO_EM_USO` | Excluir classe, arma, fraqueza ou habilidade vinculada a algum personagem |
| 422 | `DADOS_INVALIDOS` | Violação de regra de validação |
| 422 | `CLASSE_NAO_ENCONTRADA`, `ARMA_NAO_ENCONTRADA`, `FRAQUEZA_NAO_ENCONTRADA`, `HABILIDADE_NAO_ENCONTRADA` | `classeId`, `armaId`, `fraquezaId` ou `habilidadeIds` inexistentes ao criar/atualizar personagem |
| 422 | `SEM_CLASSES_CADASTRADAS`, `SEM_ARMAS_CADASTRADAS`, `SEM_FRAQUEZAS_CADASTRADAS`, `SEM_HABILIDADES_CADASTRADAS` | `POST /personagens/aleatorio` sem registros para sortear |
| 500 | `ERRO_INTERNO` | Falha inesperada (o detalhe técnico não é exposto) |

---

## 5. Recursos e campos

### Arma

| Campo | Tipo | Regra |
| ----- | ---- | ----- |
| `id` | inteiro | Gerado pela API (somente leitura) |
| `nome` | texto | 4 a 80 caracteres |
| `dano` | inteiro | 0 a 100 |
| `tipo` | texto | `corpo_a_corpo`, `distancia` ou `magica` |

### Classe

| Campo | Tipo | Regra |
| ----- | ---- | ----- |
| `id` | inteiro | Gerado pela API |
| `nome` | texto | 2 a 80 caracteres |
| `descricao` | texto | 10 a 500 caracteres |

### Fraqueza

| Campo | Tipo | Regra |
| ----- | ---- | ----- |
| `id` | inteiro | Gerado pela API |
| `nome` | texto | 2 a 80 caracteres |
| `descricao` | texto | 10 a 500 caracteres |

### Habilidade

| Campo | Tipo | Regra |
| ----- | ---- | ----- |
| `id` | inteiro | Gerado pela API |
| `nome` | texto | 2 a 80 caracteres |
| `tipo` | texto | `fisica`, `magica` ou `suporte` |
| `descricao` | texto | 10 a 500 caracteres |
| `dano` | inteiro | 0 a 100 (habilidades de suporte costumam ter 0) |

### Personagem

**Entrada** (`POST` e `PUT`): os relacionamentos vão por **ID**.

| Campo | Tipo | Regra |
| ----- | ---- | ----- |
| `nome` | texto | 2 a 80 caracteres |
| `classeId` | inteiro | ≥ 1; deve existir |
| `habilidadeIds` | lista de inteiros | Ao menos 1 item, **sem repetidos**; todos devem existir |
| `armaId` | inteiro | ≥ 1; deve existir |
| `fraquezaId` | inteiro | ≥ 1; deve existir |

**Saída**: os relacionamentos vêm completos (objetos aninhados), com as habilidades em ordem de `id`.

```json
{
  "id": 1,
  "nome": "Thorgar, o Implacável",
  "classe": { "id": 1, "nome": "Guerreiro", "descricao": "Classe especializada em combate físico e uso de armas." },
  "habilidades": [
    { "id": 2, "nome": "Golpe giratório", "tipo": "fisica", "descricao": "Gira a arma atingindo todos os inimigos próximos.", "dano": 30 },
    { "id": 5, "nome": "Investida brutal", "tipo": "fisica", "descricao": "Avança contra o inimigo com toda a força, derrubando-o no chão.", "dano": 45 }
  ],
  "arma": { "id": 5, "nome": "Machado de guerra", "dano": 55, "tipo": "corpo_a_corpo" },
  "fraqueza": { "id": 5, "nome": "Armadura pesada demais", "descricao": "O peso do equipamento reduz bastante a velocidade de movimento." }
}
```

---

## 6. Referência dos endpoints

Os cinco recursos (`armas`, `classes`, `fraquezas`, `habilidades`, `personagens`) têm as mesmas operações:

| Método | Rota | O que faz | Sucesso | Erros possíveis |
| ------ | ---- | --------- | ------- | --------------- |
| `POST` | `/{recurso}` | Cria | `201` + registro | 400, 401, 422 |
| `GET` | `/{recurso}` | Lista (paginada, filtro `nome`) | `200` + lista | 400, 401, 422 |
| `GET` | `/{recurso}/{id}` | Busca por ID | `200` + registro | 400, 401, 404, 422 |
| `PUT` | `/{recurso}/{id}` | Substitui todos os campos | `200` + registro | 400, 401, 404, 422 |
| `DELETE` | `/{recurso}/{id}` | Exclui (**só ADMIN**) | `204` | 400, 401, 403, 404, 422 e **409** (menos em personagens) |

Rotas específicas:

| Método | Rota | O que faz | Sucesso | Erros possíveis |
| ------ | ---- | --------- | ------- | --------------- |
| `POST` | `/auth/login` | Autentica e devolve o token (público) | `200` | 400, 401, 422 |
| `GET` | `/auth/me` | Usuário do token | `200` | 401 |
| `POST` | `/personagens/aleatorio` | Cria um personagem sorteado | `201` | 400, 401, 422 |

Total: **28 operações** documentadas no Swagger.

### Exemplos de corpo

**Criar arma** — `POST /api/v1/armas`

```json
{ "nome": "Machado de guerra", "dano": 55, "tipo": "corpo_a_corpo" }
```

**Criar habilidade** — `POST /api/v1/habilidades`

```json
{ "nome": "Raio gélido", "tipo": "magica", "descricao": "Dispara um raio de gelo que congela o alvo por um instante.", "dano": 35 }
```

**Criar personagem** — `POST /api/v1/personagens`

```json
{ "nome": "Lyra", "classeId": 3, "habilidadeIds": [1, 3], "armaId": 2, "fraquezaId": 1 }
```

**Erro de exclusão** — `DELETE /api/v1/classes/1` com a classe em uso:

```json
{
  "status": 409,
  "codigo": "RECURSO_EM_USO",
  "mensagem": "Não é possível excluir a classe: ela está vinculada a um ou mais personagens."
}
```

---

## 7. Personagem aleatório

`POST /api/v1/personagens/aleatorio` cria e salva um personagem com valores sorteados. A resposta é igual à de `POST /personagens` (`201` com o personagem completo).

**Corpo (opcional):**

```json
{ "nome": "Sir Teste" }
```

- Sem corpo, ou sem `nome`, a API gera um nome no formato `<Nome>, <epíteto>` (por exemplo, `Rurik, a Guardiã`). Há 16 nomes e 12 epítetos. O nome não é único, então pode se repetir.
- O `Content-Type: application/json` continua obrigatório, mesmo sem corpo.

**O que é sorteado** (distribuição uniforme, entre os registros que já existem):

- 1 classe, 1 arma e 1 fraqueza;
- entre 1 e 3 habilidades distintas (ou todas, se houver menos de 3 cadastradas).

**Erros:** se não houver nenhum registro de um dos tipos, retorna `422` e **não grava nada**. O código diz o que falta: `SEM_CLASSES_CADASTRADAS`, `SEM_ARMAS_CADASTRADAS`, `SEM_FRAQUEZAS_CADASTRADAS` ou `SEM_HABILIDADES_CADASTRADAS` (verificados nessa ordem; só o primeiro que falta é informado).

```bash
curl -X POST http://localhost:8000/api/v1/personagens/aleatorio \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json"
```

---

## 8. Regras de negócio

- **Integridade referencial.** Uma classe, arma, fraqueza ou habilidade que esteja ligada a algum personagem **não pode ser excluída** (`409 RECURSO_EM_USO`). Para apagar, primeiro exclua ou altere os personagens que a usam. O banco também impede, com chaves estrangeiras ativas, como segunda proteção.
- **Excluir um personagem** remove também seus vínculos com habilidades, mas não apaga as habilidades.
- **Habilidades do personagem.** A lista não pode estar vazia nem ter IDs repetidos. A API não limita a quantidade de habilidades ao criar ou atualizar manualmente; o sorteio usa no máximo 3.
- **Referências inexistentes.** Se `classeId`, `armaId`, `fraquezaId` ou algum item de `habilidadeIds` não existir, a resposta é `422` com o código do recurso (por exemplo, `CLASSE_NAO_ENCONTRADA`), e nada é gravado.
- **Sem consultas repetidas.** A listagem e a busca de personagens carregam classe, arma, fraqueza e habilidades com um número fixo de consultas ao banco, que não cresce com a quantidade de personagens.

---

## 9. Variáveis de ambiente

Todas são opcionais.

| Variável | Padrão | Uso |
| -------- | ------ | --- |
| `DATABASE_URL` | `sqlite:///./gerador_personagens.db` | Banco de dados |
| `JWT_SECRET` | valor de desenvolvimento | Chave que assina os tokens. **Troque fora do ambiente local** |
| `PBKDF2_ITERATIONS` | `600000` | Custo do hash de senha |
| `CORS_ORIGINS` | `*` | Origens permitidas no navegador, separadas por vírgula |
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_SENHA` | `admin@example.com` / `Admin@123` | Usuário ADMIN criado no seed |
| `SEED_MEMBER_EMAIL` / `SEED_MEMBER_SENHA` | `member@example.com` / `Member@123` | Usuário MEMBER criado no seed |

As senhas são guardadas como hash PBKDF2-SHA256 com salt aleatório. As senhas e a chave acima são **valores de desenvolvimento**.

---

## 10. Dados iniciais (seed)

Na primeira execução, com o banco vazio, a API cria:

- **Usuários:** o ADMIN e o MEMBER da tabela acima.
- **Classes:** Guerreiro, Mago, Arqueiro.
- **Armas:** Espada longa (25, corpo a corpo), Arco curto (20, distância), Cajado arcano (30, mágica).
- **Fraquezas:** Vulnerabilidade ao fogo, Vulnerabilidade à prata.
- **Habilidades:** Bola de fogo (mágica, 40), Golpe giratório (física, 30), Cura divina (suporte, 0).

O seed só roda em tabelas vazias; reiniciar a API não duplica nada.

---

## 11. Exemplo de uso completo

```bash
# 1) Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "senha": "Admin@123"}' | python -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

# 2) Listar classes
curl -s http://localhost:8000/api/v1/classes -H "Authorization: Bearer $TOKEN"

# 3) Criar uma arma
curl -s -X POST http://localhost:8000/api/v1/armas \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"nome": "Machado de guerra", "dano": 55, "tipo": "corpo_a_corpo"}'

# 4) Criar um personagem com IDs existentes
curl -s -X POST http://localhost:8000/api/v1/personagens \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"nome": "Lyra", "classeId": 3, "habilidadeIds": [1, 3], "armaId": 2, "fraquezaId": 1}'

# 5) Ou deixar a API sortear
curl -s -X POST http://localhost:8000/api/v1/personagens/aleatorio \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json"

# 6) Buscar, filtrar e paginar
curl -s "http://localhost:8000/api/v1/personagens?nome=lyra&pagina=1&limite=5" -H "Authorization: Bearer $TOKEN"

# 7) Excluir (só ADMIN) -> 204
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE http://localhost:8000/api/v1/personagens/1 \
  -H "Authorization: Bearer $TOKEN"
```

No PowerShell, use `Invoke-RestMethod` ou `curl.exe`; as aspas do JSON dão menos problema no Swagger (`/docs`).

---

## 12. Servidor MCP (usar pelo Claude)

O projeto inclui um servidor MCP (`src/mcp_server/server.py`) que deixa o Claude usar a API por conversa. Ele faz login sozinho com o usuário configurado e expõe **15 ferramentas**:

| Ferramenta | O que faz |
| ---------- | --------- |
| `quem_sou_eu` | Mostra o usuário e o papel usados nas chamadas |
| `listar` | Lista armas, classes, fraquezas, habilidades ou personagens (paginação e filtro) |
| `buscar` | Busca um registro por ID |
| `criar_arma`, `criar_classe`, `criar_fraqueza`, `criar_habilidade`, `criar_personagem` | Criam registros |
| `criar_personagem_aleatorio` | Cria um personagem sorteado (`nome` opcional) |
| `atualizar_arma`, `atualizar_classe`, `atualizar_fraqueza`, `atualizar_habilidade`, `atualizar_personagem` | Substituem todos os dados do registro |
| `excluir` | Exclui um registro (**destrutiva**; exige ADMIN) |

Configuração no Claude Desktop, variáveis e exemplos de pedidos: seção "Servidor MCP" do `README.md`. Versão em Docker: `README-DOCKER.md`.
