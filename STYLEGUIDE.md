# STYLEGUIDE.md — Constituição Técnica (API de Gerador de Personagens: ORM & Auth Edition)

> Projeto: **API de Gerador de Personagens** — recursos `Arma`, `Classe`, `Fraqueza`, `Habilidade` e `Personagem`, descritos no contrato `api_gerador_personagens.json` (export do Apidog).

## 1. Stack Tecnológica e Versões Obrigatórias
- **Linguagem:** Python 3.12+ com anotações estáticas de tipo (`typing`, `datetime`, `Enum`, `Annotated`).
- **Framework Web:** FastAPI.
- **Validação e Serialização:** Pydantic v2 (`BaseModel`, `ConfigDict(populate_by_name=True, from_attributes=True)`, `Field`, `@field_validator`).
- **Persistência e ORM (Aula 09):** SQLAlchemy 2.0+ utilizando sintaxe declarativa moderna (`DeclarativeBase`, `Mapped`, `mapped_column`, `relationship`, `ForeignKey`) com banco SQLite (`sqlite:///./gerador_personagens.db` em execução normal e banco isolado em memória/arquivo temporário nos testes).
- **Segurança, Autenticação e Autorização (Aula 08):** Autenticação Stateless via **JWT (`PyJWT`)** no padrão `Bearer Token` (`HTTPBearer`) e controle de acesso baseado em papéis (**RBAC**: `ADMIN` e `MEMBER`). Hash de senha com `hashlib.pbkdf2_hmac` (biblioteca padrão).
- **Suíte de Testes:** `pytest` + `fastapi.testclient.TestClient`.

---

## 2. Arquitetura de Diretórios e Separação de Camadas
Todo o código da API deve respeitar rigorosamente a estrutura abaixo:

```text
src/api/
├── __init__.py
├── main.py          # Instância FastAPI, lifespan (init_db + seed), CORS, middleware JSON e rotas
├── schemas.py       # Contratos Pydantic v2 espelhando os Data Schemas do Apidog (Arma, Classe, Fraqueza, Habilidade, Personagem, DTOs e Listas) + DTOs de Auth
├── models.py        # Entidades ORM SQLAlchemy 2.0 (UserModel, ClasseModel, ArmaModel, FraquezaModel, HabilidadeModel, PersonagemModel + tabela associativa personagem_habilidades)
├── database.py      # Engine SQLAlchemy, SessionLocal, get_db (Dependency Injection) e seed inicial
├── security.py      # Geração/validação de JWT, hash de senha e dependências RBAC (get_current_user, require_role)
├── exceptions.py    # Exceções de domínio e handlers globais no formato ApiError do contrato (400, 401, 403, 404, 409, 422, 500)
├── requirements.txt # Dependências estritas do projeto (fastapi, uvicorn, pydantic, sqlalchemy, pyjwt, pytest, httpx)
├── routers/
│   ├── __init__.py
│   ├── auth.py        # Endpoints de autenticação (/api/v1/auth/login e /api/v1/auth/me)
│   ├── armas.py       # CRUD de /api/v1/armas (integrado ao ORM e protegido por JWT/RBAC)
│   ├── classes.py     # CRUD de /api/v1/classes
│   ├── fraquezas.py   # CRUD de /api/v1/fraquezas
│   ├── habilidades.py # CRUD de /api/v1/habilidades
│   └── personagens.py # CRUD de /api/v1/personagens (com eager loading selectinload)
└── tests/
    ├── __init__.py
    ├── conftest.py          # Override de get_db para banco SQLite isolado de teste e fixtures de tokens JWT
    ├── test_auth.py         # Testes de login, token inválido/ausente (401) e RBAC (403 Forbidden)
    ├── test_armas.py        # Testes de contrato e persistência ORM da coleção Armas
    ├── test_classes.py      # Testes de contrato e persistência ORM da coleção Classes
    ├── test_fraquezas.py    # Testes de contrato e persistência ORM da coleção Fraquezas
    ├── test_habilidades.py  # Testes de contrato e persistência ORM da coleção Habilidades
    ├── test_personagens.py  # Testes de contrato, relacionamentos (N:1 e N:N) e ausência de N+1 em Personagens
    └── test_errors.py       # Testes de conformidade do formato ApiError (400, 401, 403, 404, 409, 422)
```

---

## 3. Regras Inegociáveis de Implementação

### 3.1. Tratamento de Erros Padronizado (schema `ApiError`)
- É **PROIBIDO** retornar erros no formato padrão do FastAPI (`{"detail": "..."}`).
- Qualquer erro HTTP (`400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`, `409 Conflict`, `422 Unprocessable Entity`, `500 Internal Server Error`) DEVE retornar um JSON no schema `ApiError` do contrato:
  - `status`: Código HTTP numérico (400–599).
  - `codigo`: Identificador do tipo de erro, em `MAIUSCULAS_COM_UNDERSCORE` (1–80 caracteres).
  - `mensagem`: Explicação clara da ocorrência para quem usa a API (1–500 caracteres). Em falhas de validação (`400`/`422`), deve citar o(s) campo(s) inválido(s).
- Códigos (`codigo`) por status:
  - `400` → `REQUISICAO_INVALIDA` (JSON malformado, tipo errado em path/query, como `id=abc`).
  - `401` → `NAO_AUTENTICADO`.
  - `403` → `ACESSO_NEGADO`.
  - `404` → `ARMA_NAO_ENCONTRADA`, `CLASSE_NAO_ENCONTRADA`, `FRAQUEZA_NAO_ENCONTRADA`, `HABILIDADE_NAO_ENCONTRADA`, `PERSONAGEM_NAO_ENCONTRADO`.
  - `409` → `RECURSO_EM_USO` (excluir Classe, Arma, Fraqueza ou Habilidade vinculada a um personagem).
  - `422` → `DADOS_INVALIDOS` (violação de `minLength`, `maxLength`, `minimum`, `maximum`, `enum` ou `required`). Referências inexistentes em `Personagem` seguem a decisão D6 do `PLAN.md`.
  - `500` → `ERRO_INTERNO` (sem expor stack trace).
- Os exemplos de resposta de erro do Apidog (`status`, `codigo`, `mensagem`) são a fonte da verdade para o formato.
- **Decisão D1 (pendente de confirmação):** a alternativa é o padrão RFC 9457 (`type`, `title`, `status`, `detail`, `instance`, `invalidParams`), que exigiria atualizar o `ApiError` no Apidog. Ver `PLAN.md`.

### 3.2. Regras de ORM e Prevenção do Problema N+1 (Aula 09)
- Use exclusivamente **SQLAlchemy 2.0** (`select()`, `Session.scalars()`, `Mapped[...]`, `mapped_column(...)`).
- `PersonagemModel` (`personagens`) se relaciona com:
  - `ClasseModel`, `ArmaModel` e `FraquezaModel` em **N:1**, mapeados com `ForeignKey("classes.id")`, `ForeignKey("armas.id")` e `ForeignKey("fraquezas.id")` e `relationship(...)`;
  - `HabilidadeModel` em **N:N**, por meio da tabela associativa `personagem_habilidades` (`relationship(secondary=...)`).
- Ao consultar personagens (`GET /api/v1/personagens` e `GET /api/v1/personagens/{id}`), utilize estratégias adequadas de consulta e carregamento (`selectinload` / `joinedload`) para `classe`, `arma`, `fraqueza` e `habilidades`, evitando o **problema de queries N+1**. O número de queries da listagem não pode crescer com a quantidade de personagens.
- Toda operação de escrita (`POST`, `PUT`, `DELETE`) deve gerenciar a transação explicitamente (`db.commit()`, `db.refresh()` ou `db.rollback()` em caso de falha).

### 3.3. Regras de Autenticação JWT e Autorização RBAC (Aula 08)
- Tokens JWT devem ser assinados com `HS256` contendo no payload: `sub` (ID do usuário), `email`, `role` (`ADMIN` ou `MEMBER`), `iat` e `exp`.
- Ausência de cabeçalho `Authorization: Bearer <token>`, token malformado ou expirado deve retornar **`401 Unauthorized`** no formato **`ApiError`** (`codigo: NAO_AUTENTICADO`).
- Tentativa de acessar um recurso autenticado sem o papel (`role`) exigido (ex.: um usuário `MEMBER` tentando executar `DELETE /api/v1/personagens/{id}`) deve retornar **`403 Forbidden`** no formato **`ApiError`** (`codigo: ACESSO_NEGADO`).
- Regra de acesso (decisão D8 do `PLAN.md`): `GET`, `POST` e `PUT` aceitam `ADMIN` e `MEMBER`; `DELETE` aceita somente `ADMIN`. Apenas `POST /api/v1/auth/login` é público.

### 3.4. Convenções de Nomenclatura JSON vs. Python
- Os payloads JSON de entrada e saída DEVEM preservar exatamente os nomes definidos no contrato do Apidog (em português, e em `camelCase` quando o nome é composto):
  - Personagem: `classeId`, `armaId`, `fraquezaId`, `habilidadeIds`
  - Paginação: `itens`, `pagina`, `limite`, `total`
  - Erros: `status`, `codigo`, `mensagem`
  - Auth: `accessToken`, `tokenType`, `expiresIn`
- Os valores dos campos `enum` também seguem o contrato: `tipo` de Arma (`corpo_a_corpo`, `distancia`, `magica`) e `tipo` de Habilidade (`fisica`, `magica`, `suporte`).
- Os identificadores (`id`) são inteiros autoincrementáveis (`int64`, mínimo `1`), gerados pela API e somente leitura.
- No código Python, os atributos usam `snake_case` (ex.: `classe_id`) e são expostos no JSON por `Field(alias=...)`.
