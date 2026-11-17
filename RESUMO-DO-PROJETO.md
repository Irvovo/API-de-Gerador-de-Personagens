# API de Gerador de Personagens — Resumo completo do projeto

> Material de apoio para a apresentação. Reúne o que foi feito, como foi feito, por que cada decisão foi tomada, os trechos de código principais, os testes, o servidor MCP, o Docker, os problemas encontrados e um roteiro de demonstração com perguntas prováveis.
> O projeto foi desenvolvido com assistência de IA (Claude), seguindo a metodologia Spec-Driven Development descrita abaixo.

---

## 1. O projeto em um minuto

**O que é:** uma API REST para gerenciar os elementos de um RPG. Cadastra **armas, classes, fraquezas e habilidades**, e monta **personagens** que combinam esses elementos. Também consegue **sortear um personagem** sozinha.

**Para que serve na prática:** é um backend completo e seguro, com login, permissões por papel, validação rigorosa, erros padronizados, testes automatizados, empacotamento em Docker e uma integração para o Claude operar a API por conversa.

**Números do projeto**

| Item | Valor |
| ---- | ----- |
| Recursos | 5 (Arma, Classe, Fraqueza, Habilidade, Personagem) + autenticação |
| Operações (endpoints) | 28 |
| Schemas no contrato (OpenAPI) | 27 |
| Papéis de acesso | 2 (ADMIN e MEMBER) |
| Testes automatizados | **212** (190 da API + 19 das ferramentas MCP + 3 ponta a ponta), todos passando |
| Código da API | cerca de 2.100 linhas; servidor MCP: 321 linhas; testes: cerca de 1.900 linhas |
| Fases do plano | 14 (da Fase 0 à 13), todas concluídas |
| Decisões de arquitetura registradas | 11 (D1 a D11) |

---

## 2. Como o trabalho foi conduzido (metodologia)

### Spec-Driven Development (SDD)

Em vez de sair programando ("vibe coding"), o trabalho segue **especificação primeiro, código depois**. Cada passo existe num plano escrito antes e só então é implementado. Os documentos que governam o projeto:

| Documento | Papel |
| --------- | ----- |
| `api_gerador_personagens.json` | **Contrato** exportado do Apidog: schemas, validações e status HTTP (a fonte da verdade) |
| `STYLEGUIDE.md` | **Constituição técnica**: stack, estrutura de pastas, regras de ORM, segurança e erros |
| `AGENTS.md` | **Governança**: as personas e o que cada uma pode ou não fazer |
| `SPEC.md` | **Decisões e extensões** ao contrato (autenticação, banco, personagem aleatório) |
| `PLAN.md` | **Roteiro** com todas as fases e itens, marcados com `[x]` ao concluir |

### As quatro personas (AGENTS.md)

| Persona | Responsabilidade | Restrição |
| ------- | ---------------- | --------- |
| `[Spec Auditor]` | Confere se o export do Apidog cumpre os critérios (descrição da API, 2+ entidades com CRUD, schemas desacoplados, atributos ricos) | Não escreve código |
| `[Tech Lead]` | Planeja: elabora o `PLAN.md` | Proibido editar `.py` |
| `[Backend Coder]` | Implementa **só** os passos do plano pedidos no turno e **para** para revisão humana | Segue o STYLEGUIDE à risca |
| `[QA Engineer]` | Cria e roda a suíte de testes | Só marca a fase de testes como concluída com 100% de aprovação |

### O ciclo de trabalho

1. O plano define a fase (Tech Lead).
2. O Backend Coder implementa os itens pedidos, marca `[x]` no PLAN e **para**.
3. A pessoa revisa e libera a próxima fase.
4. O QA prova com testes; só então a fase é dada como concluída.

Uma regra importante: **nenhum código de aplicação é criado sem um passo correspondente no PLAN.md.** Quando surgiu uma ideia nova (o personagem aleatório), ela foi registrada primeiro no SPEC (decisão D11) e no PLAN (Fase 13), e só depois codificada.

---

## 3. Tecnologias e por quê

| Tecnologia | Função | Por que foi escolhida |
| ---------- | ------ | --------------------- |
| **Python 3.12** | Linguagem | Exigido pelo STYLEGUIDE; tipagem estática moderna |
| **FastAPI** | Framework web | Validação automática, documentação Swagger gerada do código, injeção de dependências |
| **Pydantic v2** | Contratos de entrada/saída | Valida tipos e regras (tamanho, faixa, enum) e converte para JSON |
| **SQLAlchemy 2.0** | ORM | Mapeia tabelas para classes (`Mapped[...]`), controla transações e evita SQL manual |
| **SQLite** | Banco de dados | Arquivo único, sem servidor: ideal para um projeto acadêmico e fácil de empacotar |
| **PyJWT** | Tokens de login | Autenticação *stateless* (a API não guarda sessão) |
| **PBKDF2 (hashlib)** | Hash de senha | Já vem na biblioteca padrão do Python, então não adiciona dependência |
| **pytest + TestClient** | Testes | Roda a API inteira em memória, sem subir servidor |
| **Docker** | Empacotamento | Quem receber o projeto só precisa do Docker |
| **MCP (Model Context Protocol)** | Integração com o Claude | Protocolo padrão para um modelo de IA usar ferramentas externas |

---

## 4. Arquitetura

### Estrutura de pastas

```text
src/
├── __init__.py
├── api/
│   ├── main.py          # app FastAPI, lifespan (cria tabelas + seed), CORS, middleware JSON, rotas
│   ├── schemas.py       # contratos Pydantic (DTOs de entrada, saída, listas, erros, auth)
│   ├── models.py        # entidades ORM (SQLAlchemy 2.0)
│   ├── database.py      # engine, sessão (get_db), init_db e seed idempotente
│   ├── security.py      # hash de senha, JWT e dependências RBAC
│   ├── exceptions.py    # exceções de domínio e handlers no formato ApiError
│   ├── routers/         # auth, armas, classes, fraquezas, habilidades, personagens
│   └── tests/           # 190 testes da API
└── mcp_server/
    ├── server.py        # servidor MCP (15 ferramentas)
    └── tests/           # 22 testes (19 de ferramentas + 3 ponta a ponta)
```

### Separação em camadas

```text
Cliente (Swagger, curl, Claude via MCP)
        │  HTTP + JSON  (Authorization: Bearer <token>)
        ▼
   main.py ── middleware (Content-Type JSON) ── CORS ── handlers de erro (ApiError)
        ▼
   routers/ ── validação (schemas.py) ── autenticação/RBAC (security.py)
        ▼
   models.py + database.py ── SQLAlchemy ── SQLite (gerador_personagens.db)
```

Cada camada tem uma responsabilidade. As rotas **não** montam SQL à mão, os schemas **não** conhecem o banco, e a segurança é uma dependência reutilizável que se encaixa em qualquer rota.

### Onde os dados ficam

No arquivo `gerador_personagens.db`, na pasta de onde a API é iniciada (SQLite). No Docker, esse arquivo fica num **volume** (`/data`), para sobreviver a reinicializações do container.

---

## 5. Modelo de dados

```text
 classes ──┐
 armas ────┼──< personagens >──< personagem_habilidades >── habilidades
 fraquezas ┘      (N:1)                    (N:N)

 users (login e papéis; independente dos demais)
```

- **Personagem → Classe, Arma, Fraqueza:** relação **N:1** (várias personagens podem usar a mesma classe). Chaves estrangeiras obrigatórias.
- **Personagem ↔ Habilidade:** relação **N:N** por meio da tabela associativa `personagem_habilidades` (chave primária composta por `personagem_id` + `habilidade_id`).
- **Integridade:** `PRAGMA foreign_keys=ON` em toda conexão SQLite. Assim o próprio banco **impede** excluir uma classe, arma, fraqueza ou habilidade em uso.

Trecho do modelo (`models.py`), usando apenas a sintaxe moderna `Mapped[...]` e `mapped_column(...)`:

```python
class PersonagemModel(Base):
    __tablename__ = "personagens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(80))
    classe_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    arma_id: Mapped[int] = mapped_column(ForeignKey("armas.id"), nullable=False)
    fraqueza_id: Mapped[int] = mapped_column(ForeignKey("fraquezas.id"), nullable=False)

    # N:1
    classe: Mapped[ClasseModel] = relationship(back_populates="personagens")
    arma: Mapped[ArmaModel] = relationship(back_populates="personagens")
    fraqueza: Mapped[FraquezaModel] = relationship(back_populates="personagens")
    # N:N
    habilidades: Mapped[list[HabilidadeModel]] = relationship(
        secondary="personagem_habilidades",
        back_populates="personagens",
        order_by="HabilidadeModel.id",
    )
```

---

## 6. Contratos e validação (Pydantic v2)

Os schemas espelham o contrato do Apidog. As regras ficam **declaradas** nos tipos, e o FastAPI as aplica sozinho:

```python
NomeArma = Annotated[str, Field(min_length=4, max_length=80, examples=["Espada longa"])]
DanoArma = Annotated[int, Field(ge=0, le=100, examples=[25])]

class CreateArmaDTO(BaseSchema):
    nome: NomeArma
    dano: DanoArma
    tipo: TipoArma          # enum: corpo_a_corpo | distancia | magica
```

Pontos de destaque:

- **DTOs de entrada separados dos schemas de saída** (`CreateArmaDTO` x `Arma`): quem cria não escolhe o `id`.
- **camelCase na API, snake_case no Python**, com `Field(alias="classeId")` e `populate_by_name=True`.
- **Regra de negócio dentro do schema:** `habilidadeIds` não aceita IDs repetidos (`@field_validator`) nem lista vazia.
- **Schemas de saída não são mais rígidos que os de entrada**, para nunca quebrar a serialização de dados válidos.
- **Resposta de listas padronizada** com um schema genérico `Pagina[T]` (`itens`, `pagina`, `limite`, `total`), reutilizado pelos 5 recursos.

```python
class CreatePersonagemDTO(BaseSchema):
    nome: NomePersonagem
    classe_id: ClasseId              # alias "classeId", ge=1
    habilidade_ids: HabilidadeIds    # alias "habilidadeIds", min_length=1
    arma_id: ArmaId
    fraqueza_id: FraquezaId

    @field_validator("habilidade_ids")
    @classmethod
    def _sem_duplicados(cls, valor: list[int]) -> list[int]:
        return _rejeitar_ids_duplicados(valor)
```

---

## 7. Segurança

### 7.1 Senhas: PBKDF2

Nunca se guarda a senha, só um **hash** com *salt* aleatório. O formato armazenado é `pbkdf2_sha256$iterações$salt$hash`:

```python
def hash_senha(senha: str) -> str:
    salt = os.urandom(16)
    derivada = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{_PREFIXO_HASH}${PBKDF2_ITERATIONS}${salt.hex()}${derivada.hex()}"

def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    ...
    return hmac.compare_digest(derivada, bytes.fromhex(hash_hex))   # comparação em tempo constante
```

- 600.000 iterações por padrão: deixa cada tentativa lenta de propósito, o que dificulta ataque por força bruta.
- `hmac.compare_digest` evita *timing attacks*.

### 7.2 Login com JWT

`POST /auth/login` valida e-mail e senha e devolve um token **assinado** (HS256) que vale 60 minutos e carrega `sub`, `email`, `role`, `iat` e `exp`.

Um cuidado no login: quando o e-mail **não existe**, a API ainda calcula um hash de uma senha falsa. Assim o tempo de resposta é parecido, e quem ataca não descobre quais e-mails estão cadastrados:

```python
user = db.scalar(select(UserModel).where(func.lower(UserModel.email) == dto.email.lower()))
senha_ok = verificar_senha(dto.senha, user.senha_hash if user else _HASH_FALSO)
if user is None or not senha_ok:
    raise NaoAutenticadoError("E-mail ou senha inválidos.")
```

### 7.3 Autorização por papéis (RBAC)

Duas dependências do FastAPI, encaixadas nas rotas:

```python
router = APIRouter(prefix="/armas", tags=["Arma"],
                   dependencies=[Depends(get_current_user)])     # todas as rotas exigem token

@router.delete("/{id}", dependencies=[Depends(require_role("ADMIN"))], ...)   # só ADMIN exclui
```

| Situação | Resposta |
| -------- | -------- |
| Sem token, token inválido ou expirado | `401 NAO_AUTENTICADO` |
| Token válido, mas papel sem permissão (MEMBER tentando excluir) | `403 ACESSO_NEGADO` |

Detalhe: `HTTPBearer(auto_error=False)`, porque o padrão do FastAPI devolveria 403 e um JSON fora do nosso formato. Assim a ausência de token vira `401` no formato `ApiError`.

---

## 8. Tratamento de erros padronizado

Toda resposta de erro tem o formato do contrato, e **nunca** o `{"detail": ...}` do FastAPI:

```json
{ "status": 404, "codigo": "ARMA_NAO_ENCONTRADA", "mensagem": "Não existe arma com o ID informado." }
```

Como foi garantido: exceções de domínio (`NaoEncontradoError`, `RecursoEmUsoError`, `AcessoNegadoError`…) e handlers globais para validação, erros HTTP e falhas inesperadas (`500` sem expor detalhes técnicos).

**Decisão importante, 400 x 422** (D5):

```python
def _malformado(erro):
    """400 = JSON inválido ou tipo errado em path/query (ex.: id=abc)."""
    ...
# 400 REQUISICAO_INVALIDA  -> a requisição está malformada
# 422 DADOS_INVALIDOS      -> está bem formada, mas viola uma regra (tamanho, faixa, enum...)
```

Referências inexistentes (por exemplo, `classeId: 9999`) geram `422` com um código específico (`CLASSE_NAO_ENCONTRADA`), e exclusão de recurso em uso gera `409 RECURSO_EM_USO`.

---

## 9. As rotas

Os cinco recursos seguem o mesmo molde de CRUD. Exemplo (`armas.py`):

- **Listar** com paginação, filtro por nome e total:

```python
total = db.scalar(select(func.count()).select_from(ArmaModel).where(*filtros)) or 0
itens = db.scalars(
    select(ArmaModel).where(*filtros).order_by(ArmaModel.id)
    .offset((pagina - 1) * limite).limit(limite)
).all()
return ListaArmas(itens=itens, pagina=pagina, limite=limite, total=total)
```

- O filtro usa `icontains(nome, autoescape=True)`: busca "contém" que trata `%` e `_` como texto comum (não como curinga), evitando resultados inesperados.
- **Excluir** verifica o uso antes e deixa o banco como rede de segurança:

```python
em_uso = db.scalar(select(func.count()).select_from(PersonagemModel)
                   .where(PersonagemModel.arma_id == recurso_id))
if em_uso:
    raise RecursoEmUsoError("arma")          # 409
db.delete(recurso)
try:
    db.commit()
except IntegrityError as exc:                # a FK do banco também barra
    db.rollback()
    raise RecursoEmUsoError("arma") from exc
```

- **Toda escrita** gerencia a transação: `commit()`, e `rollback()` se algo falhar.

### 9.1 O problema N+1 (destaque para a apresentação)

**O problema:** listar 100 personagens e, para cada um, buscar classe, arma, fraqueza e habilidades faria 1 + 100 × 4 consultas ao banco. O número de consultas cresceria junto com a lista.

**A solução:** carregamento antecipado com `selectinload`: uma consulta por relacionamento, **sempre o mesmo total**, não importa quantos personagens existam.

```python
_EAGER = (
    selectinload(PersonagemModel.classe),
    selectinload(PersonagemModel.arma),
    selectinload(PersonagemModel.fraqueza),
    selectinload(PersonagemModel.habilidades),
)

itens = db.scalars(select(PersonagemModel).options(*_EAGER).where(*filtros)
                   .order_by(PersonagemModel.id).offset(...).limit(...)).all()
```

**A prova:** há um teste que conta as consultas SQL reais (listener `before_cursor_execute`) e exige que listar 1 personagem e listar 9 façam **o mesmo número**. Também foi verificado que o teste **falha** de verdade quando se remove o carregamento antecipado, ou seja, ele realmente detecta o problema.

### 9.2 Validação de referências no Personagem

Ao criar/atualizar, a rota confere se classe, arma, fraqueza e **todas** as habilidades existem. Para as habilidades, faz **uma** consulta com `IN`, e não uma por item. Se algo faltar, `422` com o código do recurso.

---

## 10. Decisões de arquitetura registradas

| ID | Decisão | Motivo |
| -- | ------- | ------ |
| D1 | Erros no schema `ApiError` (`status`, `codigo`, `mensagem`) | É o formato do contrato; a alternativa (RFC 9457) exigiria alterar o Apidog |
| D2 | Rotas em `/api/v1/{recurso}`, no plural | O export do Apidog tinha paths digitados errado (`/v1/api/...`, `/fraqueza`) |
| D3 | IDs inteiros autoincrementados | Conforme o contrato |
| D4 | Paginação `itens/pagina/limite/total` | Formato do contrato |
| D5 | 400 = malformado; 422 = regra violada | Separa erro de formato de erro de negócio |
| D6 | Referência inexistente = 422 com código específico | O contrato do personagem não declara 404 |
| D7 | Excluir recurso em uso = 409 `RECURSO_EM_USO` | Protege a integridade dos dados |
| D8 | RBAC: DELETE só ADMIN; demais, ADMIN e MEMBER | Princípio do menor privilégio para exclusão |
| D9 | PBKDF2 da biblioteca padrão | Sem dependência extra, padrão reconhecido |
| D10 | SQLite em arquivo; em memória nos testes | Simples de empacotar; testes rápidos e isolados |
| D11 | Personagem aleatório como extensão | Funcionalidade nova, registrada na spec **antes** do código |

---

## 11. As fases do projeto

| Fase | Entrega |
| ---- | ------- |
| 0 | Pré-requisitos: decisões e criação do `SPEC.md` |
| 1 | Estrutura de pastas e dependências |
| 2 | Persistência: engine, sessão, `get_db`, `init_db`, seed |
| 3 | Entidades ORM |
| 4 | Contratos Pydantic v2 |
| 5 | Erros padronizados |
| 6 | Segurança (hash, JWT, RBAC) |
| 7 | Aplicação (`main.py`, CORS, middleware JSON) |
| 8 | Rotas dos cinco recursos e autenticação |
| 9 | Infraestrutura de testes |
| 10 | Suíte de testes |
| 11 | Fechamento: conferência no Swagger e divergências do Apidog |
| 12 | Servidor MCP (Claude → API) |
| 13 | Personagem aleatório (extensão D11) |
| Extra | Empacotamento em Docker (API e MCP) e documentação |

---

## 12. Testes automatizados

**212 testes, todos passando.** A API roda inteira dentro do teste, sem servidor e sem tocar no banco real.

| Arquivo | Testes | O que verifica |
| ------- | -----: | -------------- |
| `test_auth.py` | 16 | Login, conteúdo do token, `/auth/me`, 401 (sem token, malformado, expirado), 403 do MEMBER, 204 do ADMIN |
| `test_armas.py` | 29 | CRUD completo, persistência, paginação, filtro, validações (422), 404, 409 |
| `test_classes.py` | 27 | Mesmo escopo, adaptado |
| `test_fraquezas.py` | 27 | Mesmo escopo, adaptado |
| `test_habilidades.py` | 30 | Mesmo escopo, adaptado (enum e faixa de dano) |
| `test_personagens.py` | 43 | Objetos aninhados, referências inexistentes, IDs repetidos, PUT, vínculos, **N+1**, personagem aleatório |
| `test_errors.py` | 18 | Todo erro sai no formato `ApiError` e **nunca** com a chave `detail` |
| MCP: `test_server.py` | 19 | Cada ferramenta contra a API real em memória, erros e renovação de token |
| MCP: `test_e2e_stdio.py` | 3 | Processo MCP real + `uvicorn` real: fluxo completo, MEMBER sem permissão, API fora do ar |

### Como os testes são isolados

- **Banco em memória** (SQLite com `StaticPool`): cada teste cria e derruba as tabelas, então um teste nunca interfere no outro.
- **`dependency_overrides[get_db]`**: troca o banco real pelo de teste sem mudar o código da API.
- **Fixtures de login:** `admin_headers`, `member_headers`, `token_expirado` e `token_malformado`.
- **Sementes de aleatoriedade fixas** no teste do personagem aleatório, para o resultado ser previsível.

### Exemplo: a prova de que não há N+1

```python
def test_listagem_nao_tem_n_mais_1(client, admin_headers, payload_personagem, contar_queries):
    client.post(URL, json=payload_personagem(nome="Primeiro"), headers=admin_headers)
    with contar_queries() as com_um:
        client.get(URL, params={"limite": 100}, headers=admin_headers)

    for i in range(8):
        client.post(URL, json=payload_personagem(nome=f"Heroi {i}"), headers=admin_headers)
    with contar_queries() as com_nove:
        client.get(URL, params={"limite": 100}, headers=admin_headers)

    assert com_um["n"] == com_nove["n"]      # mesmo número de consultas, com 1 ou com 9
```

O `contar_queries` é uma fixture que escuta o evento `before_cursor_execute` do SQLAlchemy e conta cada SQL enviado ao banco.

---

## 13. Servidor MCP: o Claude operando a API

### O que é

**MCP (Model Context Protocol)** é um protocolo aberto que permite a um modelo de IA, como o Claude, usar ferramentas externas. Aqui, o servidor MCP é a "ponte" entre o Claude e a API:

```text
Claude Desktop ──(stdio)──> servidor MCP ──(HTTP + Bearer token)──> API ──> SQLite
```

O Claude Desktop inicia o servidor MCP como um processo local e conversa com ele pela entrada e saída padrão (`stdio`). Por isso o servidor **nunca pode imprimir nada no stdout**: é o canal do protocolo.

### O que ele expõe: 15 ferramentas

| Grupo | Ferramentas |
| ----- | ----------- |
| Leitura (marcadas como somente leitura) | `quem_sou_eu`, `listar`, `buscar` |
| Criação | `criar_arma`, `criar_classe`, `criar_fraqueza`, `criar_habilidade`, `criar_personagem`, `criar_personagem_aleatorio` |
| Atualização | `atualizar_arma`, `atualizar_classe`, `atualizar_fraqueza`, `atualizar_habilidade`, `atualizar_personagem` |
| Exclusão (marcada como **destrutiva**) | `excluir` |

### Decisões de projeto

- **Ferramentas genéricas onde fazia sentido:** `listar`, `buscar` e `excluir` recebem o parâmetro `recurso` (`armas`, `classes`, ...). Já `criar_*` e `atualizar_*` são tipadas por recurso, com os mesmos limites do contrato nos parâmetros (o Claude erra menos).
- **Autenticação automática.** O servidor faz login com o usuário das variáveis `GERADOR_API_EMAIL` e `GERADOR_API_SENHA`, guarda o token em memória e, se receber `401`, faz login de novo uma vez. **O token nunca aparece na conversa.**
- **O papel do usuário configurado manda.** Com o ADMIN o Claude pode excluir; com o MEMBER a API devolve `403`.
- **Erros legíveis.** O `ApiError` vira uma mensagem clara para o Claude (por exemplo, `A API respondeu 409 RECURSO_EM_USO: ...`), e falha de rede avisa que a API não está acessível.
- **Autônomo:** não importa nada de `src/api`. Fala com a API só por HTTP, então funciona com a API em qualquer lugar (inclusive no Docker).

```python
def _login(self) -> None:
    resp = self._enviar("POST", f"{API_PREFIX}/auth/login",
                        json={"email": self.email, "senha": self.senha})
    if resp.status_code != 200:
        raise ToolError("Falha no login. " + self._descrever_erro(resp))
    self._token = resp.json()["accessToken"]           # guardado em memória
```

### O que foi demonstrado na prática (pelo Claude, via MCP)

1. Listou as 3 habilidades do seed.
2. Criou **5 habilidades, 5 armas, 5 fraquezas e 5 personagens** que combinam esses itens.
3. Consultou cada personagem e conferiu os dados aninhados.
4. Excluiu um personagem e, em seguida, a arma e a fraqueza que só ele usava, na ordem certa, pois a API recusaria o contrário com `409`.
5. Criou um personagem aleatório pela ferramenta `criar_personagem_aleatorio`.

---

## 14. Personagem aleatório (extensão D11)

**Fluxo seguido (spec primeiro):** a ideia foi registrada no `SPEC.md` (D11) e no `PLAN.md` (Fase 13) antes de qualquer código.

**Como funciona:** `POST /api/v1/personagens/aleatorio` sorteia 1 classe, 1 arma, 1 fraqueza e de 1 a 3 habilidades distintas entre as que já existem, e grava o personagem. O `nome` é opcional; sem ele, a API monta um (`<Nome>, <epíteto>`, com 16 nomes e 12 epítetos).

```python
@router.post("/aleatorio", response_model=Personagem, status_code=201, ...)
def criar_personagem_aleatorio(
    dto: Annotated[CreatePersonagemAleatorioDTO | None, Body()] = None,
    db: Session = Depends(get_db),
    rng: random.Random = Depends(get_aleatorio),         # aleatoriedade injetável
):
    classe_id = _sortear_id(db, ClasseModel, "classe", rng)
    arma_id = _sortear_id(db, ArmaModel, "arma", rng)
    fraqueza_id = _sortear_id(db, FraquezaModel, "fraqueza", rng)
    ...
    quantidade = rng.randint(1, min(MAX_HABILIDADES_ALEATORIO, len(ids_habilidades)))
    escolhidas = rng.sample(ids_habilidades, quantidade)
```

Destaques de engenharia:

- **Aleatoriedade como dependência** (`get_aleatorio`): em produção é um `random.Random()` livre; nos testes é substituído por uma semente fixa, o que torna o teste **determinístico**.
- **Só IDs são carregados** para sortear, e não as tabelas inteiras.
- **Sem registros para sortear?** `422` com código específico (`SEM_CLASSES_CADASTRADAS`, `SEM_ARMAS_CADASTRADAS`...) e **nada é gravado**.
- **17 testes** cobrem: com e sem nome, mesma semente = mesmo resultado, 1 a 3 habilidades distintas, cada código de erro, 401, 400 e nada gravado em caso de erro.

---

## 15. Docker: rodar em qualquer máquina

**Objetivo:** quem receber o projeto precisa **só do Docker** instalado.

| Arquivo | Função |
| ------- | ------ |
| `Dockerfile` | Imagem da API em **dois estágios** (instala dependências / imagem final enxuta) |
| `.dockerignore` | Deixa de fora `.git`, `.env`, `.venv`, bancos, testes, MCP e documentação |
| `docker-compose.yml` | Sobe a API, mapeia a porta, lê o `.env` e guarda o banco num **volume** |
| `.env.example` | Todas as variáveis, só com valores de exemplo (sem segredos reais) |
| `README-DOCKER.md` | Passo a passo para quem nunca viu o projeto |
| `Dockerfile.mcp` | Imagem opcional do servidor MCP |

Boas práticas aplicadas:

- **Imagem base oficial e leve:** `python:3.12-slim`.
- **Cache de dependências:** o `requirements.txt` é copiado antes do código, então o Docker só reinstala as bibliotecas quando elas mudam.
- **Usuário sem privilégios:** a API roda como usuário comum (uid 10001), não como root.
- **`--host 0.0.0.0`:** dentro do container a API precisa escutar em todas as interfaces; em `127.0.0.1`, a porta mapeada não funcionaria.
- **Healthcheck:** o Docker consulta `/openapi.json` e mostra o container como `healthy`.
- **Sem segredos na imagem:** tudo vem do `.env`, que fica fora da imagem e do pacote enviado.
- **Dados persistentes:** o SQLite fica no volume `dados`; `docker compose down` mantém os dados e `down -v` apaga.
- **`pytest` e `httpx` fora da imagem:** servem só para testes.

**Comando único:** `docker compose up --build` e abrir `http://localhost:8000/docs`.

**O que foi verificado:** o build rodou na máquina do autor. Os passos da imagem (instalar dependências com Python 3.12, rodar como usuário comum, escutar em `0.0.0.0`, healthcheck, login e chamadas reais, persistência após reiniciar) foram reproduzidos e funcionaram. O Docker Hub estava inacessível no ambiente de desenvolvimento, por isso a primeira execução completa de `docker compose up --build` foi feita pelo autor.

---

## 16. Problemas encontrados e como foram resolvidos

| Problema | Como foi resolvido |
| -------- | ------------------ |
| O export do Apidog tinha **8 divergências** (paths errados como `/v1/api/...`, schemas de saída mais rígidos que os de entrada, bodies inline em vez de `$ref`, status e segurança ausentes, metadados vazios) | Foram listadas no `SPEC.md` para o Spec Auditor corrigir no Apidog; a API seguiu a decisão D2 e os contratos corretos |
| A biblioteca `mcp` 2.x trocou a API (`FastMCP` virou `MCPServer`) | O servidor foi escrito para a versão atual e a decisão ficou documentada no PLAN (M1) |
| Um teste do MCP falhava porque o parâmetro `nome` da ferramenta colidia com o `nome` do helper | O helper passou a receber o nome da ferramenta como parâmetro **somente posicional** (`/`) |
| Um erro no teste do personagem aleatório: a semente fixa dava sempre o mesmo sorteio | A fixture criava um gerador novo a cada requisição; passou a usar **uma instância só** por teste. O endpoint estava correto |
| Risco de N+1 na listagem de personagens (consultas crescendo junto com a lista) | `selectinload` + teste que **conta as consultas** |
| Dúvida sobre 400 x 422 | Decisão D5 e handler que classifica cada erro |
| `docker compose up` falhou com "env file .env not found" | Era o passo de copiar `.env.example` para `.env`; ficou documentado no README-DOCKER (Problemas comuns) |

---

## 17. Roteiro de demonstração (10 a 12 minutos)

**Antes de começar:** API no ar (`uvicorn src.api.main:app --reload` **ou** `docker compose up`), navegador em `http://localhost:8000/docs`.

| # | O que mostrar | Resultado esperado |
| - | ------------- | ------------------ |
| 1 | Abrir o Swagger: tags, 28 operações e os schemas | Documentação gerada do próprio código |
| 2 | `POST /auth/login` com `admin@example.com` / `Admin@123`; copiar o token e clicar em **Authorize** | `200` com `accessToken` e `expiresIn: 3600` |
| 3 | `GET /classes` | Guerreiro, Mago e Arqueiro (seed) |
| 4 | `POST /armas` válido e depois com `dano: 101` | `201`, depois `422 DADOS_INVALIDOS` citando o campo |
| 5 | `GET /armas/abc` e `GET /armas/999` | `400 REQUISICAO_INVALIDA` e `404 ARMA_NAO_ENCONTRADA` |
| 6 | `POST /personagens` com IDs existentes | `201` com classe, arma, fraqueza e habilidades **aninhadas** |
| 7 | `DELETE /classes/{id}` de uma classe em uso | `409 RECURSO_EM_USO` |
| 8 | Sem token, e depois logado como `member@example.com` tentando `DELETE` | `401 NAO_AUTENTICADO` e `403 ACESSO_NEGADO` |
| 9 | `POST /personagens/aleatorio` duas vezes | Dois personagens diferentes, sorteados |
| 10 | No terminal: `pytest -q` | `212 passed` |
| 11 | No Claude Desktop: "liste as habilidades", "crie um personagem aleatório" e "exclua o personagem X" | O Claude usa a API pelo MCP e **pede confirmação** antes de excluir |
| 12 | Mostrar `PLAN.md` com todos os `[x]` e o `SPEC.md` | O método SDD: nada foi feito sem estar no plano |

**Dica:** deixe o token já copiado e um personagem criado antes, para não perder tempo.

---

## 18. Limitações e melhorias futuras

**Limitações atuais (honestas):**

- **SQLite** serve para o projeto e para um usuário por vez; para muitos acessos simultâneos, o ideal é PostgreSQL.
- As tabelas são criadas com `create_all`, sem **migrações** (Alembic) para evoluir o banco com segurança.
- O token dura 60 minutos e **não há refresh token** nem logout (revogação).
- Sem **limite de tentativas** de login (rate limit) e sem HTTPS próprio (em produção, usaria um proxy com TLS).
- As **senhas do seed e a chave JWT padrão são de desenvolvimento** e devem ser trocadas fora do ambiente local.
- No MCP, as credenciais ficam em texto no arquivo de configuração do Claude Desktop.
- O filtro por nome ignora maiúsculas só em letras **sem acento** (limitação do SQLite).
- `PUT` substitui o registro inteiro; não há `PATCH` (atualização parcial).
- Os testes completos foram executados em Python 3.10 no ambiente de desenvolvimento; o alvo do projeto e do Docker é 3.12.
- As correções das 8 divergências no Apidog ainda dependem do Spec Auditor.

**Melhorias possíveis:** PostgreSQL + Alembic, refresh token, rate limit, CI (rodar `pytest` a cada alteração), `PATCH`, soft delete e mais tipos de personagem (nível, atributos).

---

## 19. Perguntas prováveis e respostas curtas

**Por que FastAPI?** Valida os dados automaticamente com os tipos do Python, gera o Swagger sozinho e tem injeção de dependências, o que facilitou a segurança e os testes.

**O que é JWT e por que "stateless"?** É um token assinado que carrega quem é o usuário e o papel dele. A API só confere a assinatura; não guarda sessão em memória ou no banco.

**Por que não guardar a senha direto?** Se o banco vazar, as senhas vazam. Guardamos só o hash PBKDF2 com salt aleatório, que é lento de propósito e não dá para reverter.

**Qual a diferença entre 400 e 422?** `400` é requisição malformada (JSON quebrado, `id=abc`). `422` é requisição bem formada que viola uma regra (nome curto, dano 101, referência inexistente).

**O que é o problema N+1 e como foi evitado?** Buscar a lista e depois, para cada item, consultar as relações (1 + N consultas). Foi resolvido com `selectinload` (número fixo de consultas) e provado com um teste que conta os SQLs.

**Por que o DELETE devolve 409?** Para não deixar personagens apontando para algo que não existe. A API checa o uso antes e o banco também barra, com chave estrangeira.

**O que é RBAC?** Controle de acesso por papel. Aqui, ADMIN faz tudo e MEMBER não exclui.

**Como os testes rodam sem um banco real?** Com SQLite em memória, trocado na API via `dependency_overrides`. Cada teste começa do zero.

**O que é MCP e como o Claude usa a API?** É um protocolo para o Claude usar ferramentas. O servidor MCP recebe os pedidos do Claude, faz login na API sozinho e chama os endpoints. Ele respeita o papel do usuário configurado (o MEMBER não exclui).

**É seguro deixar uma IA excluir dados?** A ferramenta `excluir` é marcada como destrutiva (o Claude confirma antes), exige o papel ADMIN e a API ainda barra exclusão de itens em uso. Para impedir exclusões, basta usar o usuário MEMBER.

**Qual foi o papel da IA?** Ela atuou nas personas definidas (principalmente Backend Coder e QA), implementando **passo a passo, conforme o PLAN**. As decisões de arquitetura foram confirmadas pelo autor, e cada fase foi revisada antes de seguir.

**O que mudaria para produção?** Banco PostgreSQL, migrações, segredos fora do código (variáveis seguras), HTTPS, refresh token e rate limit.

---

## 20. Glossário

| Termo | Significado |
| ----- | ----------- |
| **API REST** | Serviço acessado por HTTP (`GET`, `POST`, `PUT`, `DELETE`) que troca dados em JSON |
| **Endpoint** | Um endereço da API que faz uma operação (por exemplo, `POST /api/v1/armas`) |
| **DTO** | Objeto que define o formato dos dados de **entrada** (`CreateArmaDTO`) |
| **ORM** | Mapeia tabelas do banco para classes Python (SQLAlchemy) |
| **JWT** | Token assinado usado para provar quem é o usuário |
| **RBAC** | Permissões por papel (ADMIN, MEMBER) |
| **N+1** | Excesso de consultas ao banco ao carregar listas com relacionamentos |
| **Seed** | Dados iniciais inseridos quando o banco está vazio |
| **Idempotente** | Pode rodar várias vezes com o mesmo resultado (o seed não duplica) |
| **Container / imagem** | Pacote isolado com a aplicação e o que ela precisa para rodar |
| **Volume** | Área do Docker que guarda dados fora do ciclo de vida do container |
| **Healthcheck** | Teste que o Docker repete para saber se a aplicação está viva |
| **MCP** | Protocolo que permite a um modelo de IA usar ferramentas externas |
| **SDD** | Spec-Driven Development: especificar e planejar antes de programar |

---

## 21. Arquivos entregues

| Arquivo | Conteúdo |
| ------- | -------- |
| `DOCUMENTACAO-API.md` | Documentação completa da API |
| `RESUMO-DO-PROJETO.md` | Este resumo |
| `README.md` | Como rodar, variáveis, exemplos, servidor MCP |
| `README-DOCKER.md` | Rodar com Docker (para quem recebe o projeto) |
| `SPEC.md`, `PLAN.md`, `STYLEGUIDE.md`, `AGENTS.md` | Documentos do método SDD |
| `src/api/`, `src/mcp_server/` | Código e testes |
