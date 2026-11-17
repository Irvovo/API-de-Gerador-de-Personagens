# API de Gerador de Personagens — rodando com Docker

API de RPG (armas, classes, fraquezas, habilidades e personagens) feita em Python/FastAPI.
Com Docker você não precisa instalar Python nem nada além do próprio Docker.

## O que você precisa

- **Docker Desktop** instalado e aberto (Windows, Mac) ou Docker Engine + Compose (Linux).
  Para conferir: `docker --version` e `docker compose version`.

## Passo a passo

1. Abra um terminal **dentro da pasta do projeto** (a que tem o arquivo `docker-compose.yml`).
2. Crie o arquivo de configuração a partir do exemplo:
   ```bash
   cp .env.example .env
   ```
   No PowerShell do Windows: `Copy-Item .env.example .env`
   (os valores de exemplo já funcionam; abra o `.env` se quiser trocar a porta ou as senhas).
3. Suba a API:
   ```bash
   docker compose up --build
   ```
   Na primeira vez demora um pouco (baixa a imagem e instala as dependências). Quando aparecer
   `Uvicorn running on http://0.0.0.0:8000`, está pronta.
4. Abra no navegador: **http://localhost:8000/docs** (documentação interativa da API).

## Como testar que está funcionando

**Está no ar?** Abra http://localhost:8000/openapi.json — deve aparecer um JSON grande.
Ou, no terminal: `docker compose ps` (a coluna de status deve mostrar `healthy`).

**Login e uma chamada de verdade** (use `curl.exe` no PowerShell; no Mac/Linux/Git Bash, `curl`):

```bash
# 1) login -> devolve um "accessToken"
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "senha": "Admin@123"}'

# 2) listar classes (troque SEU_TOKEN pelo accessToken do passo 1)
curl http://localhost:8000/api/v1/classes -H "Authorization: Bearer SEU_TOKEN"
```

Deve voltar a lista com Guerreiro, Mago e Arqueiro. Também dá para testar pelo navegador em
`/docs`: faça o login em **POST /api/v1/auth/login**, copie o `accessToken`, clique em
**Authorize** e cole o token.

Usuários criados automaticamente (valores do `.env`):

| Papel | E-mail | Senha | Pode |
| ----- | ------ | ----- | ---- |
| ADMIN | admin@example.com | Admin@123 | tudo, inclusive excluir |
| MEMBER | member@example.com | Member@123 | listar, criar e atualizar (não exclui) |

## Opcional: usar a API pelo Claude (servidor MCP)

Quem usa o **Claude Desktop** pode pedir "liste as classes", "crie um personagem aleatório" etc. O servidor
MCP também roda em Docker, então não precisa instalar Python.

1. Deixe a API no ar (`docker compose up -d`).
2. Gere a imagem do MCP (uma vez só, na pasta do projeto):
   ```bash
   docker build -f Dockerfile.mcp -t gerador-personagens-mcp .
   ```
3. Abra `%APPDATA%\Claude\claude_desktop_config.json` e coloque o bloco de
   `src/mcp_server/claude_desktop_config.docker.exemplo.json` dentro de `mcpServers`
   (se já houver outros servidores, junte sem repetir a chave `mcpServers`).
4. Feche o Claude Desktop por completo (inclusive na bandeja do sistema) e abra de novo.
5. Peça ao Claude: "liste as habilidades".

Observações:
- O usuário do bloco (`admin@example.com`) pode excluir registros; use `member@example.com` / `Member@123`
  se quiser que o Claude **não** consiga excluir.
- Se você trocou a porta (`API_PORT`) ou as senhas no `.env`, ajuste `GERADOR_API_URL` e as credenciais no bloco.
- O Docker Desktop precisa estar aberto quando o Claude for usar o MCP.

## Parar e limpar

```bash
docker compose down        # para e remove o container; os DADOS continuam salvos
docker compose down -v     # para e APAGA também os dados (volta ao estado inicial)
```

Para ver os logs: `docker compose logs -f api`.

## Problemas comuns

- **"port is already allocated"**: a porta 8000 está em uso. No `.env`, mude `API_PORT=8001` e
  suba de novo (a API passa a ficar em http://localhost:8001).
- **"env file .env not found"**: faltou o passo 2 (copiar `.env.example` para `.env`).
- **Mudei as senhas no `.env` e o login antigo ainda funciona**: os usuários só são criados com o banco
  vazio. Rode `docker compose down -v` e suba de novo.
- **Mudei o código/dependências**: rode `docker compose up --build` de novo.
