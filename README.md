# API de Gerador de Personagens

API REST (FastAPI + SQLAlchemy 2.0 + Pydantic v2) para gerenciar `Arma`, `Classe`, `Fraqueza`,
`Habilidade` e `Personagem`, com autenticação JWT (Bearer) e controle de acesso por papéis
(`ADMIN` e `MEMBER`). O contrato de referência é o `api_gerador_personagens.json` (export do Apidog);
as decisões de projeto estão no `SPEC.md` e no `PLAN.md`.

## Equipe

| Integrante | Responsabilidade |
| ---------- | ---------------- |
| Irving Lucas Marinho | Desenvolvimento da API (rotas, ORM), servidor MCP, Docker e documentação |
| Thiago Andrade | Testes da API, desenvolvimento da Autenticação e planejamento da segurança |
| Sofia Nascimento | Revisão do contrato da API no Apidog, testes manuais pelo Swagger (/docs), revisão da documentação (DOCUMENTACAO-API.md e README), apoio na montagem dos slides e na apresentação |


Método: Spec-Driven Development. O trabalho segue o `SPEC.md`, o `PLAN.md`, o `STYLEGUIDE.md` e as
personas definidas no `AGENTS.md`, com desenvolvimento assistido por IA e revisão a cada fase.

## Como rodar

Requer Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r src/api/requirements.txt

uvicorn src.api.main:app --reload    # http://127.0.0.1:8000  (Swagger em /docs)
pytest                               # API + servidor MCP (precisa de: pip install -r src/mcp_server/requirements.txt)
pytest src/api/tests                 # só a API
```

Na primeira execução o banco SQLite `gerador_personagens.db` é criado na pasta atual, com usuários
e dados de exemplo (o seed é idempotente: não duplica nada nas execuções seguintes).

### Variáveis de ambiente (todas opcionais)

| Variável | Padrão | Uso |
| -------- | ------ | --- |
| `DATABASE_URL` | `sqlite:///./gerador_personagens.db` | Banco de dados |
| `JWT_SECRET` | valor de desenvolvimento | **Troque em produção** |
| `PBKDF2_ITERATIONS` | `600000` | Custo do hash de senha |
| `CORS_ORIGINS` | `*` | Origens permitidas, separadas por vírgula |
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_SENHA` | `admin@example.com` / `Admin@123` | Usuário ADMIN do seed |
| `SEED_MEMBER_EMAIL` / `SEED_MEMBER_SENHA` | `member@example.com` / `Member@123` | Usuário MEMBER do seed |

## Usuários de seed

| Papel | E-mail | Senha |
| ----- | ------ | ----- |
| ADMIN | `admin@example.com` | `Admin@123` |
| MEMBER | `member@example.com` | `Member@123` |

`GET`, `POST` e `PUT` aceitam ADMIN e MEMBER; `DELETE` somente ADMIN. Apenas o login é público.

## Exemplos de chamadas

```bash
# 1) login -> token (válido por 60 minutos)
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "senha": "Admin@123"}'
# {"accessToken": "<JWT>", "tokenType": "bearer", "expiresIn": 3600}

TOKEN=<cole o accessToken>

# 2) usuário autenticado
curl -s http://127.0.0.1:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN"

# 3) listar armas (paginação e filtro por nome)
curl -s "http://127.0.0.1:8000/api/v1/armas?pagina=1&limite=10&nome=espada" \
  -H "Authorization: Bearer $TOKEN"

# 4) criar arma
curl -s -X POST http://127.0.0.1:8000/api/v1/armas \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"nome": "Machado de guerra", "dano": 35, "tipo": "corpo_a_corpo"}'

# 5) criar personagem (usa IDs de classe, arma, fraqueza e habilidades existentes)
curl -s -X POST http://127.0.0.1:8000/api/v1/personagens \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"nome": "Lyra", "classeId": 1, "habilidadeIds": [1, 2], "armaId": 1, "fraquezaId": 1}'

# 6) criar personagem aleatório (sorteia classe, arma, fraqueza e 1 a 3 habilidades)
#    body opcional ("nome"); o Content-Type JSON continua obrigatório mesmo sem body
curl -s -X POST http://127.0.0.1:8000/api/v1/personagens/aleatorio \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json"
curl -s -X POST http://127.0.0.1:8000/api/v1/personagens/aleatorio \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"nome": "Sir Teste"}'

# 7) excluir (somente ADMIN) -> 204
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE http://127.0.0.1:8000/api/v1/personagens/1 \
  -H "Authorization: Bearer $TOKEN"
```

## Erros

Todo erro retorna `{"status", "codigo", "mensagem"}` (schema `ApiError`), nunca `{"detail": ...}`:

| Status | `codigo` | Quando |
| ------ | -------- | ------ |
| 400 | `REQUISICAO_INVALIDA` | JSON malformado, `Content-Type` diferente de JSON, tipo errado em path/query (`id=abc`) |
| 401 | `NAO_AUTENTICADO` | Token ausente, malformado, expirado ou login inválido |
| 403 | `ACESSO_NEGADO` | Papel sem permissão (ex.: `MEMBER` em `DELETE`) |
| 404 | `ARMA_NAO_ENCONTRADA`, `CLASSE_NAO_ENCONTRADA`, `FRAQUEZA_NAO_ENCONTRADA`, `HABILIDADE_NAO_ENCONTRADA`, `PERSONAGEM_NAO_ENCONTRADO`, `ROTA_NAO_ENCONTRADA` | Recurso ou rota inexistente |
| 405 | `METODO_NAO_PERMITIDO` | Método HTTP não suportado na rota |
| 409 | `RECURSO_EM_USO` | Excluir classe/arma/fraqueza/habilidade vinculada a personagem |
| 422 | `DADOS_INVALIDOS` | Violação de regra (tamanho, faixa, enum, campo obrigatório) |
| 422 | `CLASSE_NAO_ENCONTRADA`, `ARMA_NAO_ENCONTRADA`, `FRAQUEZA_NAO_ENCONTRADA`, `HABILIDADE_NAO_ENCONTRADA` | `classeId`, `armaId`, `fraquezaId` ou `habilidadeIds` inexistentes ao criar/atualizar personagem |
| 422 | `SEM_CLASSES_CADASTRADAS`, `SEM_ARMAS_CADASTRADAS`, `SEM_FRAQUEZAS_CADASTRADAS`, `SEM_HABILIDADES_CADASTRADAS` | `POST /personagens/aleatorio` sem nenhum registro do tipo para sortear (reporta só o primeiro que falta) |
| 500 | `ERRO_INTERNO` | Falha inesperada (sem stack trace) |

## Servidor MCP (usar a API pelo Claude)

O servidor MCP em `src/mcp_server/server.py` deixa o Claude listar, buscar, criar, atualizar e
excluir registros pela conversa. Ele roda no seu computador (transporte `stdio`) e chama a API por HTTP,
então **a API precisa estar rodando** (`uvicorn src.api.main:app --reload`) enquanto você usa.

### Ferramentas

| Ferramenta | O que faz |
| ---------- | --------- |
| `quem_sou_eu` | Mostra o usuário e o papel (ADMIN/MEMBER) usados nas chamadas |
| `listar` | Lista `armas`, `classes`, `fraquezas`, `habilidades` ou `personagens` (paginação e filtro por nome) |
| `buscar` | Busca um registro pelo ID (personagem vem com tudo aninhado) |
| `criar_arma`, `criar_classe`, `criar_fraqueza`, `criar_habilidade`, `criar_personagem` | Cria registros (personagem usa IDs existentes) |
| `criar_personagem_aleatorio` | Cria um personagem sorteando classe, arma, fraqueza e 1 a 3 habilidades (`nome` opcional) |
| `atualizar_arma`, `atualizar_classe`, `atualizar_fraqueza`, `atualizar_habilidade`, `atualizar_personagem` | Substitui todos os dados de um registro |
| `excluir` | Exclui um registro (**destrutiva**; exige ADMIN; `409` se estiver vinculado a personagem) |

### Instalar e conectar (Windows)

1. Instale as dependências do servidor no mesmo ambiente virtual da API:
   ```powershell
   .venv\Scripts\activate
   pip install -r src/mcp_server/requirements.txt
   ```
2. **Claude Desktop:** abra `%APPDATA%\Claude\claude_desktop_config.json` e acrescente o bloco de
   `src/mcp_server/claude_desktop_config.exemplo.json` dentro de `mcpServers` (se já houver outros servidores,
   junte, sem duplicar a chave `mcpServers`). Ajuste os caminhos se o projeto estiver em outra pasta.
   Depois feche o Claude Desktop por completo (inclusive na bandeja) e abra de novo.
3. **Claude Code:**
   ```bash
   claude mcp add gerador-de-personagens \
     --env GERADOR_API_URL=http://127.0.0.1:8000 \
     --env GERADOR_API_EMAIL=admin@example.com \
     --env GERADOR_API_SENHA=Admin@123 \
     -- "D:\aplicacoes\api criador de personagem\.venv\Scripts\python.exe" \
        "D:\aplicacoes\api criador de personagem\src\mcp_server\server.py"
   ```

### Variáveis de ambiente do servidor MCP

| Variável | Padrão | Uso |
| -------- | ------ | --- |
| `GERADOR_API_URL` | `http://127.0.0.1:8000` | Endereço da API |
| `GERADOR_API_EMAIL` / `GERADOR_API_SENHA` | — (obrigatórias) | Usuário usado nas chamadas |

O papel do usuário define o que o Claude pode fazer: com `admin@example.com` ele pode excluir; com
`member@example.com` / `Member@123` pode listar, criar e atualizar, mas recebe `403` ao excluir.
As credenciais ficam em texto puro na configuração do Claude, então use um usuário só para isso e troque a senha do seed.

### Exemplos de pedidos

- "Liste as armas." / "Quais classes existem?"
- "Crie uma arma chamada Machado de guerra, dano 35, corpo a corpo."
- "Crie um personagem chamado Thorin, classe Guerreiro, com as habilidades Golpe giratório e Cura divina, usando a Espada longa e a fraqueza Vulnerabilidade ao fogo."
- "Crie um personagem aleatório." / "Crie um personagem aleatório chamado Sir Teste."
- "Exclua a arma 4." (o Claude deve pedir sua confirmação antes)
