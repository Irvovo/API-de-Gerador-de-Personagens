# SPEC.md — API de Gerador de Personagens (extensões ao contrato)

Complementa o contrato `api_gerador_personagens.json` (Apidog) com as decisões de arquitetura e as
extensões de Autenticação/ORM. Regras de código: `STYLEGUIDE.md`. Roteiro: `PLAN.md`.

## Decisões de arquitetura

| ID | Decisão |
| -- | ------- |
| D1 | **Formato de erro:** schema `ApiError` do contrato (`status`, `codigo`, `mensagem`). Confirmado pelo usuário em 15/11/2026 ("pode fazer o que achar melhor"). A alternativa RFC 9457 foi descartada. |
| D2 | **Paths:** `/api/v1/{recurso}` e `/api/v1/{recurso}/{id}`, no plural. Os paths `/v1/api/...` e `/api/v1/fraqueza` do export são erros de digitação. |
| D3 | **IDs:** inteiro autoincremento (`int64`, mínimo 1). |
| D4 | **Paginação:** `itens`, `pagina`, `limite`, `total`. Query params `pagina` (padrão 1, mín. 1), `limite` (padrão 10, 1–100) e `nome` (1–80, "contém", sem diferenciar maiúsculas). Ordenação por `id` crescente. |
| D5 | **400 x 422:** `400` = requisição malformada (JSON inválido, `Content-Type` diferente de JSON, tipo errado em path/query como `id=abc`). `422` = dados bem formados que violam regras (`minLength`, `maximum`, `enum`, `required`, `id=0`, referência inexistente). |
| D6 | **Referência inexistente em Personagem:** `422` com `codigo` específico (`CLASSE_NAO_ENCONTRADA` etc.). |
| D7 | **Exclusão de recurso em uso:** Classe, Arma, Fraqueza ou Habilidade vinculada a personagem retorna `409 RECURSO_EM_USO`. |
| D8 | **RBAC:** `GET`/`POST`/`PUT` = ADMIN e MEMBER; `DELETE` = somente ADMIN. Só `POST /api/v1/auth/login` é público. |
| D9 | **Hash de senha:** `hashlib.pbkdf2_hmac` (SHA-256, salt aleatório de 16 bytes, 600 000 iterações por padrão), formato `pbkdf2_sha256$iter$salt$hash`. |
| D10 | **Banco:** SQLite em arquivo; nos testes, SQLite em memória com `StaticPool`; `PRAGMA foreign_keys=ON` em toda conexão. |
| D11 | **Personagem aleatório (extensão):** `POST /api/v1/personagens/aleatorio` sorteia classe, arma, fraqueza e de 1 a 3 habilidades entre os registros existentes e grava o personagem. Detalhes na seção "Extensões ao contrato (Personagem aleatório)". Confirmado pelo usuário em 15/11/2026 ("Pois crie então"). |

## Extensões ao contrato (Auth)

- `POST /api/v1/auth/login` — body `{ "email", "senha" }`. `200`: `{ "accessToken", "tokenType": "bearer", "expiresIn": 3600 }` (`expiresIn` em segundos). Credenciais inválidas: `401`.
- `GET /api/v1/auth/me` — `200`: `{ "id", "nome", "email", "role" }`. Sem token, inválido ou expirado: `401`.
- JWT (HS256): `sub` (ID do usuário, string), `email`, `role`, `iat`, `exp`. Validade de 60 minutos. Segredo em `JWT_SECRET`.
- Todas as rotas de recursos declaram `401`; `DELETE` declara também `403`; `DELETE` de Classe/Arma/Fraqueza/Habilidade declara `409`.

## Extensões ao contrato (Personagem aleatório)

- `POST /api/v1/personagens/aleatorio` — ADMIN e MEMBER (D8). Cria um personagem com valores sorteados e responde `201` com o schema `Personagem` completo (igual a `POST /api/v1/personagens`).
- **Body opcional:** `{ "nome": "..." }` (2–80 caracteres, como em `CreatePersonagemDTO`). Sem body, ou sem `nome`, a API gera um nome no formato `<Nome>, <epíteto>` (ex.: `Thorgar, o Implacável`). Nomes não são únicos, então podem se repetir. O `Content-Type: application/json` continua obrigatório (D5), mesmo sem body.
- **Sorteio (distribuição uniforme):** 1 classe, 1 arma, 1 fraqueza e uma quantidade de habilidades entre 1 e `min(3, total cadastrado)`, todas distintas. O limite de 3 vem do `maxItems` de `Personagem.habilidades` no contrato de saída.
- **Recursos faltando:** se não houver ao menos 1 registro de cada tipo, `422` e nada é gravado. `codigo`: `SEM_CLASSES_CADASTRADAS`, `SEM_ARMAS_CADASTRADAS`, `SEM_FRAQUEZAS_CADASTRADAS` ou `SEM_HABILIDADES_CADASTRADAS`; a checagem segue essa ordem e reporta só o primeiro que falta.
- **Erros declarados:** `400`, `401`, `422`.
- **Testabilidade:** a fonte de aleatoriedade é uma dependência (`get_aleatorio`, devolve `random.Random`), substituível nos testes por uma instância com semente fixa.
- **MCP:** ferramenta `criar_personagem_aleatorio` (Fase 13), parâmetro opcional `nome`.

## Notas de implementação

- Códigos de erro adicionais: `ROTA_NAO_ENCONTRADA` (404 de rota), `METODO_NAO_PERMITIDO` (405), `ERRO_HTTP` (demais `HTTPException`).
- `expiresIn` fica em segundos (60 min = 3600).
- E-mail do login é comparado sem diferenciar maiúsculas.
- O filtro `nome` usa `LIKE` com escape de curingas; no SQLite a comparação sem diferenciar maiúsculas só vale para letras ASCII (`lower()` do SQLite não trata acentos).
- Exclusão: o ORM usa `passive_deletes="all"` nos lados inversos para não desvincular personagens sozinho; a rota checa o uso antes e o banco (FK) é a rede de segurança.
- O middleware JSON exige `Content-Type: application/json` em todo `POST`/`PUT`.

## Divergências do export do Apidog a corrigir (para o `[Spec Auditor]`)

1. **Paths:** `/v1/api/classes/{id}`, `/v1/api/fraqueza/{id}`, `/v1/api/personagens` e `/v1/api/personagens/{id}` (devem ser `/api/v1/...`); listagem de fraquezas em `/api/v1/fraqueza` (singular, deve ser `/api/v1/fraquezas`).
2. **Schemas de saída mais rígidos que os DTOs:** `Personagem.nome` (mín. 5 x 2), `Fraqueza.descricao` (5–100 x 10–500), `Habilidade.dano` (mín. 1 x 0), `Habilidade.nome` (mín. 4 x 2) e `Personagem.habilidades` (`maxItems` 3 na saída, sem limite equivalente em `habilidadeIds`). A API implementada **não** limita a 3 habilidades; decidir se o limite passa a valer na entrada ou se sai do schema.
3. **Bodies e respostas inline** (`{"type": "object", "properties": {}}`) em POST/GET de habilidades, classes, fraquezas e personagens, em vez de `$ref` para os Data Schemas (critério 3 do `[Spec Auditor]`).
4. **Exemplos desatualizados ou incoerentes:** PUT `/personagens/{id}` com `classe`/`habilidades`/`arma`/`fraqueza` aninhados em vez de `classeId`/`habilidadeIds`/`armaId`/`fraquezaId`; `ListaPersonagens` com `pagina` e `total` irreais; itens de `ListaFraquezas` e `ListaPersonagens` sem `id`; descrição "Identificador da arma" repetida nos PUT de classe, fraqueza e personagem.
5. **Status ausentes:** PUT de classes, fraquezas e personagens sem `404`; GET/DELETE de habilidades, classes, fraquezas e personagens sem `400`/`422`.
6. **Tags:** operações de armas sem `tags` (a tag `Arma` não existe na lista).
7. **Metadados:** `info.title` ("Módulo predefinido") e `info.description` vazios; `securitySchemes` ausente.
8. **Segurança e erros:** sem `401`, `403` e `409`, sem as rotas de `/auth`, e respostas reutilizáveis `Requisição inválida` e `Dados inválidos` com schema vazio (deveriam referenciar `ApiError`).
