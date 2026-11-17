# PLAN.md — API de Gerador de Personagens v2 (SQLAlchemy 2.0 ORM + JWT/RBAC)

> Roteiro elaborado pelo `[Tech Lead]`. Fontes: `STYLEGUIDE.md`, `AGENTS.md`, `api_gerador_personagens.json` (export do Apidog) e README publicado no Apidog.
> `STYLEGUIDE.md`, `AGENTS.md` e este plano já estão adaptados para a **API de Gerador de Personagens** (recursos `Arma`, `Classe`, `Fraqueza`, `Habilidade` e `Personagem`).
> O `SPEC.md` foi criado na Fase 0 com as decisões, as extensões de Autenticação/ORM e as divergências do export do Apidog.
> O `[Backend Coder]` executa apenas os passos pedidos no prompt e marca `[x]` ao concluir.

---

## Decisões de arquitetura

| ID | Decisão | Status |
| -- | ------- | ------ |
| D1 | **Formato de erro.** Padrão adotado (também no `STYLEGUIDE.md`, seção 3.1): schema `ApiError` do contrato (`status`, `codigo`, `mensagem`). Alternativa: RFC 9457 (`type`, `title`, `status`, `detail`, `instance`, `invalidParams`), exigida pela versão original do STYLEGUIDE do professor, que exigiria atualizar o `ApiError` no Apidog e alterar a seção 3.1 do `STYLEGUIDE.md`. Se a alternativa for escolhida, apenas a Fase 5 do plano muda. | Definido (confirmado em 15/11/2026) |
| D2 | **Paths.** Todas as rotas seguem o README: `/api/v1/{recurso}` e `/api/v1/{recurso}/{id}`, no plural. Os paths `/v1/api/...` e `/api/v1/fraqueza` do export são tratados como erro de digitação. | Definido |
| D3 | **IDs.** `integer` autoincremento (`int64`, mínimo 1), conforme o contrato (e o `STYLEGUIDE.md`, seção 3.4). | Definido |
| D4 | **Paginação.** Formato do contrato: `itens`, `pagina`, `limite`, `total`. Query params `pagina` (default 1, mín. 1), `limite` (default 10, 1–100) e `nome` (1–80, filtro "contém", sem diferenciar maiúsculas). Ordenação estável por `id` crescente. | Definido |
| D5 | **400 x 422.** `400`: requisição malformada (JSON inválido, tipo errado em path/query, como `id=abc`). `422`: dados bem formados que violam regras (`minLength`, `maximum`, `enum`, `required`, referência inexistente). | Definido |
| D6 | **Referências inexistentes no Personagem.** `classeId`, `armaId`, `fraquezaId` ou um item de `habilidadeIds` inexistentes retornam `422`, com `codigo` específico (`CLASSE_NAO_ENCONTRADA` etc.). O contrato de POST/PUT de personagem não declara `404`. | Definido |
| D7 | **Exclusão de recurso em uso.** Excluir Classe, Arma, Fraqueza ou Habilidade vinculada a algum personagem retorna `409` com `codigo: RECURSO_EM_USO`. O STYLEGUIDE prevê `409` (seção 3.1), mas ele precisa ser adicionado ao Apidog. | Definido |
| D8 | **RBAC.** `GET`, `POST` e `PUT`: `ADMIN` e `MEMBER`. `DELETE`: somente `ADMIN`. Todas as rotas de recursos exigem JWT; apenas `POST /api/v1/auth/login` é pública. | Definido |
| D9 | **Hash de senha.** `hashlib.pbkdf2_hmac` (SHA-256, salt aleatório, iterações configuráveis) da biblioteca padrão, para não adicionar dependência fora da lista do STYLEGUIDE. | Definido |
| D10 | **Banco.** `sqlite:///./gerador_personagens.db` em execução normal. Nos testes, SQLite em memória com `StaticPool`. `PRAGMA foreign_keys=ON` ativado por evento de conexão. | Definido |
| D11 | **Personagem aleatório.** `POST /api/v1/personagens/aleatorio` sorteia classe, arma, fraqueza e 1 a 3 habilidades entre os registros existentes (nome opcional no body; sem registros, `422 SEM_*_CADASTRADAS`). Extensão ao contrato, detalhada no `SPEC.md` e executada na Fase 13. | Definido (confirmado em 15/11/2026) |

## Extensões ao contrato (Auth/ORM)

- `POST /api/v1/auth/login`: body `{ "email", "senha" }`. `200` retorna `{ "accessToken", "tokenType": "bearer", "expiresIn" }`. Credenciais inválidas retornam `401`.
- `GET /api/v1/auth/me`: `200` retorna `{ "id", "nome", "email", "role" }`. Sem token ou com token inválido/expirado retorna `401`.
- Payload JWT (HS256): `sub` (ID do usuário, como string), `email`, `role`, `iat`, `exp`. Expiração padrão de 60 minutos. Segredo lido de variável de ambiente `JWT_SECRET`, com valor de desenvolvimento como fallback.
- Todas as rotas de recursos passam a declarar `401` e `403` (`403` apenas no `DELETE`), além do que já consta no contrato.

---

## Fase 0 — Pré-requisitos
- [x] 0.1 Confirmar a decisão **D1** (formato de erro) com o usuário.
- [x] 0.2 Criar `SPEC.md` com o conteúdo de "Decisões" e "Extensões ao contrato" deste plano.
- [x] 0.3 Registrar no `SPEC.md` as divergências do contrato listadas na Fase 11 para correção no Apidog.

## Fase 1 — Estrutura e dependências
- [x] 1.1 Criar a árvore `src/api/` (com `routers/` e `tests/`), incluindo os `__init__.py`.
- [x] 1.2 Criar `src/api/requirements.txt` com versões fixadas: `fastapi`, `uvicorn`, `pydantic`, `sqlalchemy`, `pyjwt`, `pytest`, `httpx`.
- [x] 1.3 Definir como rodar o app (`uvicorn src.api.main:app --reload`) e os testes (`pytest src/api/tests`). Documentar no README do repositório.

## Fase 2 — Persistência base (`database.py`)
- [x] 2.1 Declarar `DATABASE_URL` (padrão `sqlite:///./gerador_personagens.db`, sobrescrevível por variável de ambiente).
- [x] 2.2 Criar o `engine` com `connect_args={"check_same_thread": False}` e o listener que executa `PRAGMA foreign_keys=ON`.
- [x] 2.3 Criar `SessionLocal` (`sessionmaker`, `autoflush=False`, `expire_on_commit=False`).
- [x] 2.4 Criar a dependência `get_db()` com `yield` e fechamento da sessão em `finally`.
- [x] 2.5 Criar `init_db()`, que executa `Base.metadata.create_all`.
- [x] 2.6 Criar `seed_db()` idempotente: usuário `ADMIN` e usuário `MEMBER` com senhas hasheadas (D9) e um conjunto mínimo de classes, armas, fraquezas e habilidades de exemplo. Não insere nada se os dados já existirem.

## Fase 3 — Entidades ORM (`models.py`)
- [x] 3.1 Criar `Base(DeclarativeBase)`.
- [x] 3.2 Criar os enums Python `TipoArma` (`corpo_a_corpo`, `distancia`, `magica`), `TipoHabilidade` (`fisica`, `magica`, `suporte`) e `Role` (`ADMIN`, `MEMBER`).
- [x] 3.3 `UserModel` (`users`): `id`, `nome`, `email` (único, indexado), `senha_hash`, `role`, `created_at`.
- [x] 3.4 `ClasseModel` (`classes`): `id`, `nome` (String 80), `descricao` (String 500).
- [x] 3.5 `ArmaModel` (`armas`): `id`, `nome` (String 80), `dano` (Integer), `tipo` (Enum `TipoArma`).
- [x] 3.6 `FraquezaModel` (`fraquezas`): `id`, `nome` (String 80), `descricao` (String 500).
- [x] 3.7 `HabilidadeModel` (`habilidades`): `id`, `nome` (String 80), `tipo` (Enum `TipoHabilidade`), `descricao` (String 500), `dano` (Integer).
- [x] 3.8 Tabela associativa `personagem_habilidades` (`personagem_id` FK com `ondelete="CASCADE"` e `habilidade_id` FK), com chave primária composta.
- [x] 3.9 `PersonagemModel` (`personagens`): `id`, `nome` (String 80), `classe_id` → `ForeignKey("classes.id")`, `arma_id` → `ForeignKey("armas.id")`, `fraqueza_id` → `ForeignKey("fraquezas.id")`, todas `nullable=False`.
- [x] 3.10 Relationships em `PersonagemModel`: `classe`, `arma`, `fraqueza` (N:1) e `habilidades` (N:N via `secondary`). Lados inversos `personagens` em Classe, Arma, Fraqueza e Habilidade, com `back_populates`.
- [x] 3.11 Usar exclusivamente `Mapped[...]` e `mapped_column(...)` (sem `Column` legado).

## Fase 4 — Contratos Pydantic v2 (`schemas.py`)
- [x] 4.1 Criar `BaseSchema` com `ConfigDict(populate_by_name=True, from_attributes=True)`.
- [x] 4.2 Enums Pydantic espelhando `tipo` de Arma e Habilidade.
- [x] 4.3 Arma: `CreateArmaDTO`, `UpdateArmaDTO` (`nome` 4–80, `dano` 0–100, `tipo` enum, todos obrigatórios), `Arma` (saída) e `ListaArmas`.
- [x] 4.4 Classe: `CreateClasseDTO`, `UpdateClasseDTO` (`nome` 2–80, `descricao` 10–500), `Classe` e `ListaClasses`.
- [x] 4.5 Fraqueza: `CreateFraquezaDTO`, `UpdateFraquezaDTO` (`nome` 2–80, `descricao` 10–500), `Fraqueza` e `ListaFraquezas`.
- [x] 4.6 Habilidade: `CreateHabilidadeDTO`, `UpdateHabilidadeDTO` (`nome` 2–80, `tipo` enum, `descricao` 10–500, `dano` 0–100), `Habilidade` e `ListaHabilidades`.
- [x] 4.7 Personagem: `CreatePersonagemDTO` e `UpdatePersonagemDTO` (`nome` 2–80, `classeId`, `armaId`, `fraquezaId` ≥ 1, `habilidadeIds` com `minItems=1` e itens ≥ 1). Usar `Field(alias=...)` para camelCase e `@field_validator` para rejeitar IDs duplicados em `habilidadeIds` (422).
- [x] 4.8 `Personagem` (saída) com `classe`, `arma`, `fraqueza` e `habilidades` aninhados, e `ListaPersonagens`.
- [x] 4.9 Schemas de saída **sem** restrições mais rígidas que os DTOs de entrada, para não quebrar a serialização de dados válidos (ver divergências na Fase 11, inclusive o `maxItems=3` de `habilidades` em `Personagem`).
- [x] 4.10 DTOs de Auth: `LoginRequestDTO` (`email`, `senha`), `TokenResponseDTO` (`accessToken`, `tokenType`, `expiresIn`) e `UserResponse` (`id`, `nome`, `email`, `role`).
- [x] 4.11 `ApiError` conforme D1.
- [x] 4.12 Garantir que as respostas sejam serializadas por alias (`response_model_by_alias`), preservando o camelCase do contrato.

## Fase 5 — Erros padronizados (`exceptions.py`)
- [x] 5.1 Criar a exceção base de domínio `ApiException(status, codigo, mensagem)`.
- [x] 5.2 Subclasses: `NaoEncontradoError` (404, com `codigo` por entidade: `ARMA_NAO_ENCONTRADA`, `CLASSE_NAO_ENCONTRADA`, `FRAQUEZA_NAO_ENCONTRADA`, `HABILIDADE_NAO_ENCONTRADA`, `PERSONAGEM_NAO_ENCONTRADO`), `ReferenciaInvalidaError` (422, D6), `RecursoEmUsoError` (409, D7), `NaoAutenticadoError` (401, `NAO_AUTENTICADO`) e `AcessoNegadoError` (403, `ACESSO_NEGADO`).
- [x] 5.3 Handler de `ApiException` que retorna `JSONResponse` no formato `ApiError`.
- [x] 5.4 Handler de `RequestValidationError` que aplica D5: erros de parsing retornam 400 (`REQUISICAO_INVALIDA`); violações de regra retornam 422 (`DADOS_INVALIDOS`), com mensagem que cite o(s) campo(s).
- [x] 5.5 Handler de `StarletteHTTPException` para converter 404/405 de rota inexistente e qualquer outro `HTTPException` para `ApiError`, para que nenhuma resposta saia como `{"detail": ...}`.
- [x] 5.6 Handler genérico de `Exception` que retorna 500 (`ERRO_INTERNO`) em `ApiError`, sem expor stack trace.
- [x] 5.7 Função `register_exception_handlers(app)` para uso no `main.py`.

## Fase 6 — Segurança (`security.py`)
- [x] 6.1 Configurações: `JWT_SECRET`, `JWT_ALGORITHM="HS256"`, `ACCESS_TOKEN_EXPIRE_MINUTES=60`.
- [x] 6.2 `hash_senha()` e `verificar_senha()` (D9, comparação com `hmac.compare_digest`).
- [x] 6.3 `criar_access_token(user)` com `sub`, `email`, `role`, `iat` e `exp`.
- [x] 6.4 `decodificar_token()` tratando `ExpiredSignatureError` e `InvalidTokenError` como `NaoAutenticadoError`.
- [x] 6.5 `bearer_scheme = HTTPBearer(auto_error=False)`, para que a ausência de cabeçalho gere 401 no nosso formato (e não o 403 padrão do FastAPI).
- [x] 6.6 Dependência `get_current_user(db, credentials)`: valida o token, carrega o `UserModel` pelo `sub` e retorna 401 se o usuário não existir.
- [x] 6.7 Fábrica de dependência `require_role(*roles)`, que retorna 403 (`AcessoNegadoError`) quando o `role` do usuário não está na lista.

## Fase 7 — Aplicação (`main.py`)
- [x] 7.1 `lifespan` que executa `init_db()` e `seed_db()` na inicialização.
- [x] 7.2 Instanciar `FastAPI` com título, versão e descrição do README.
- [x] 7.3 Configurar CORS (origens via variável de ambiente; `*` em desenvolvimento).
- [x] 7.4 Middleware JSON: rejeitar `POST`/`PUT` cujo `Content-Type` não seja `application/json` com 400 em `ApiError` *(interpretação do item "middleware JSON" do STYLEGUIDE; confirmar)*.
- [x] 7.5 Registrar os handlers de erro (Fase 5).
- [x] 7.6 Incluir os routers de auth, armas, habilidades, classes, fraquezas e personagens sob `/api/v1`.

## Fase 8 — Rotas
Regras comuns a todos os routers de recurso:
listagem com `select()` + `offset/limit` + `func.count()` para `total`;
filtro `nome` por `ilike('%texto%')`;
escrita com `db.commit()`, `db.refresh()` e `db.rollback()` em `except`;
`DELETE` retorna `204` sem corpo;
códigos de status exatamente como no contrato (com os acréscimos de D7 e D8).

- [x] 8.1 `routers/auth.py`: `POST /auth/login` (público) e `GET /auth/me` (autenticado).
- [x] 8.2 `routers/armas.py`: `POST`, `GET` (lista), `GET /{id}`, `PUT /{id}`, `DELETE /{id}` (ADMIN, 409 se em uso).
- [x] 8.3 `routers/classes.py`: as mesmas 5 operações.
- [x] 8.4 `routers/fraquezas.py`: as mesmas 5 operações.
- [x] 8.5 `routers/habilidades.py`: as mesmas 5 operações.
- [x] 8.6 `routers/personagens.py` — `POST`: validar existência de `classeId`, `armaId`, `fraquezaId` e de todos os `habilidadeIds` (uma consulta `in_()` para as habilidades), retornando 422 se algum não existir; criar o personagem e retornar 201 com os relacionamentos carregados.
- [x] 8.7 `routers/personagens.py` — `GET` (lista) e `GET /{id}` com `options(selectinload(PersonagemModel.classe), selectinload(...arma), selectinload(...fraqueza), selectinload(...habilidades))`, evitando N+1.
- [x] 8.8 `routers/personagens.py` — `PUT /{id}`: substituição completa, inclusive do conjunto de habilidades, com as mesmas validações do `POST`; 404 se o personagem não existir.
- [x] 8.9 `routers/personagens.py` — `DELETE /{id}` (ADMIN): remove o personagem e as linhas da tabela associativa.
- [x] 8.10 Aplicar `Depends(get_current_user)` em todas as rotas de recurso e `Depends(require_role("ADMIN"))` em todos os `DELETE` (D8).

## Fase 9 — Infraestrutura de testes (`tests/conftest.py`)
- [x] 9.1 Engine SQLite em memória com `StaticPool` e `PRAGMA foreign_keys=ON`.
- [x] 9.2 Fixture que cria e derruba as tabelas a cada teste (isolamento total).
- [x] 9.3 Override de `get_db` no `app.dependency_overrides`.
- [x] 9.4 Garantir que o `lifespan` não grave no banco real durante os testes.
- [x] 9.5 Fixtures de usuários (`admin`, `member`) e de tokens: `admin_headers`, `member_headers`, `token_expirado` e `token_malformado`.
- [x] 9.6 Fixtures de dados base (uma classe, uma arma, uma fraqueza e duas habilidades) para os testes de personagem.
- [x] 9.7 Utilitário que conta queries SQL por requisição (listener `before_cursor_execute`), para os testes de N+1.

## Fase 10 — Suíte de testes (`[QA Engineer]`)
- [x] 10.1 `test_auth.py`: login válido retorna token com `sub`, `email`, `role`, `iat` e `exp`; senha errada retorna 401; `/auth/me` com token retorna 200; sem header, token malformado ou expirado retorna 401; `MEMBER` em `DELETE` retorna 403; `ADMIN` em `DELETE` retorna 204.
- [x] 10.2 `test_armas.py`: CRUD completo com persistência verificada por GET após escrita; paginação (`pagina`, `limite`, `total`); filtro `nome`; `dano` fora de 0–100 e `tipo` fora do enum retornam 422; id inexistente retorna 404 (`ARMA_NAO_ENCONTRADA`); arma em uso no DELETE retorna 409.
- [x] 10.3 `test_classes.py`: o mesmo escopo, adaptado (`descricao` 10–500).
- [x] 10.4 `test_fraquezas.py`: o mesmo escopo, adaptado.
- [x] 10.5 `test_habilidades.py`: o mesmo escopo, adaptado (`tipo` enum, `dano` 0–100).
- [x] 10.6 `test_personagens.py`: criação retorna objetos aninhados; referência inexistente retorna 422; `habilidadeIds` vazio ou duplicado retorna 422; PUT substitui as habilidades; DELETE remove os vínculos; número de queries da listagem **constante** com 1 e com N personagens (prova de ausência de N+1).
- [x] 10.7 `test_errors.py`: todo erro (400, 401, 403, 404, 409, 422 e rota inexistente) retorna o formato `ApiError` e nunca a chave `detail`; JSON malformado retorna 400; `id=abc` no path retorna 400.
- [x] 10.8 Executar `pytest` no terminal e registrar 100% de aprovação. Só então marcar a Fase 10 como concluída.

## Fase 11 — Fechamento e alinhamento com o Apidog
- [x] 11.1 Conferir no Swagger (`/docs`) se todas as rotas, schemas e status batem com o contrato e com as extensões.
- [x] 11.2 Listar para o `[Spec Auditor]` as divergências do export a corrigir no Apidog:
  - Paths `/v1/api/classes/{id}`, `/v1/api/fraqueza/{id}`, `/v1/api/personagens` e `/v1/api/personagens/{id}`, e listagem em `/api/v1/fraqueza` (singular).
  - Restrições do schema de saída mais rígidas que as do DTO: `Personagem.nome` (mín. 5 x 2), `Fraqueza.descricao` (5–100 x 10–500), `Habilidade.dano` (mín. 1 x 0), `Habilidade.nome` (mín. 4 x 2) e `Personagem.habilidades` (`maxItems` 3 na saída, sem limite equivalente em `habilidadeIds`; decidir se o limite de 3 passa a valer também na entrada ou se sai do schema de saída).
  - Bodies e respostas inline (`{"type": "object", "properties": {}}`) em POST/GET de habilidades, classes, fraquezas e personagens, em vez de `$ref` para os Data Schemas (critério 3 do `[Spec Auditor]`).
  - Exemplos desatualizados ou incoerentes: PUT `/personagens/{id}` com `classe`/`habilidades`/`arma`/`fraqueza` aninhados em vez de `classeId`/`habilidadeIds`/`armaId`/`fraquezaId`; `ListaPersonagens` com `pagina` e `total` irreais; itens de `ListaFraquezas` e `ListaPersonagens` sem `id`; descrição "Identificador da arma" repetida nos PUT de classe, fraqueza e personagem.
  - PUT de classes, fraquezas e personagens sem `404` declarado; GET/DELETE de habilidades, classes, fraquezas e personagens sem `400`/`422`.
  - Operações de armas sem `tags` (a tag `Arma` não existe na lista de tags).
  - `info.title` ("Módulo predefinido") e `info.description` vazio no export, e `securitySchemes` ausente.
  - Ausência de `401`, `403` e `409` (D7, D8) e das rotas de `/auth`.
  - Ajuste do `ApiError` se D1 for alterada para RFC 9457.
- [x] 11.3 Atualizar o README do repositório com instruções de execução, usuários de seed e exemplos de chamadas autenticadas.

## Fase 12 — Servidor MCP (Claude → API)

Servidor MCP local (transporte `stdio`, Python) que expõe a API ao Claude: listar, buscar, criar, atualizar e excluir recursos. Fica em `src/mcp_server/`, autônomo (não importa `src/api`), e fala com a API só por HTTP.

| ID | Decisão |
| -- | ------- |
| M1 | **SDK:** pacote oficial `mcp` 2.x (`MCPServer`, antigo `FastMCP`), `httpx` como cliente HTTP. Dependências em `src/mcp_server/requirements.txt`, separadas das da API. |
| M2 | **Autenticação:** o servidor faz login em `POST /api/v1/auth/login` com `GERADOR_API_EMAIL`/`GERADOR_API_SENHA` (variáveis de ambiente), guarda o token em memória e refaz o login uma vez ao receber `401`. Credenciais nunca aparecem em respostas das ferramentas. |
| M3 | **Papéis:** o usuário configurado define o que o Claude pode fazer. `ADMIN` pode excluir; `MEMBER` recebe `403` nas exclusões. |
| M4 | **Ferramentas:** genéricas `listar`, `buscar` e `excluir` (parâmetro `recurso`: `armas`, `classes`, `fraquezas`, `habilidades`, `personagens`); tipadas `criar_*` e `atualizar_*` para cada recurso; `quem_sou_eu`. `excluir` é marcada como destrutiva (`destructiveHint`). |
| M5 | **Erros:** o `ApiError` da API (`status`, `codigo`, `mensagem`) vira mensagem de erro legível da ferramenta; falha de rede informa que a API não está acessível. |
| M6 | **Transporte:** `stdio`, iniciado pelo Claude Desktop/Claude Code. A API precisa estar rodando em `GERADOR_API_URL` (padrão `http://127.0.0.1:8000`). |

- [x] 12.1 Criar `src/mcp_server/requirements.txt` (`mcp`, `httpx`) com versões fixadas.
- [x] 12.2 `server.py`: cliente HTTP com login, cache de token, renovação em `401` e tradução de `ApiError` (M2, M5).
- [x] 12.3 `server.py`: ferramentas genéricas `listar`, `buscar`, `excluir` e `quem_sou_eu` (M4).
- [x] 12.4 `server.py`: ferramentas `criar_*` e `atualizar_*` para arma, classe, fraqueza, habilidade e personagem, com os mesmos limites do contrato nos parâmetros (M4).
- [x] 12.5 Testes (`src/mcp_server/tests/`) com a API real em memória: cada ferramenta, erros (`404`, `409`, `422`, `403`) e renovação de token.
- [x] 12.6 Teste de ponta a ponta pelo protocolo MCP (processo `stdio` real contra um `uvicorn` local).
- [x] 12.7 README: configuração no Claude Desktop (Windows) e no Claude Code, variáveis de ambiente e exemplos de pedidos.

## Fase 13 — Personagem aleatório (extensão D11)

Endpoint que sorteia os componentes e cria o personagem, mais a ferramenta correspondente no MCP. Regras completas no `SPEC.md` (D11).

- [x] 13.1 Registrar D11 e a seção "Extensões ao contrato (Personagem aleatório)" no `SPEC.md`.
- [x] 13.2 `schemas.py`: `CreatePersonagemAleatorioDTO` com `nome` opcional (mesma validação de `NomePersonagem`).
- [x] 13.3 `exceptions.py`: erro `422` com os códigos `SEM_*_CADASTRADAS`.
- [x] 13.4 `routers/personagens.py`: dependência `get_aleatorio`, listas de nomes e epítetos, e a rota `POST /aleatorio` (sorteio por `id`, sem carregar tabelas inteiras).
- [x] 13.5 Testes em `test_personagens.py`: sem body e com `nome`, determinismo com semente, 1–3 habilidades distintas, recurso faltando (cada código), 401 sem token, 400 sem `Content-Type` JSON, nada gravado em caso de erro.
- [x] 13.6 MCP: ferramenta `criar_personagem_aleatorio` com testes (usa a API real em memória).
- [x] 13.7 README: seção do endpoint e da ferramenta; conferir no `/docs` e rodar a suíte completa.

