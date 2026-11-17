"""Servidor MCP da API de Gerador de Personagens.

Deixa o Claude listar, buscar, criar, atualizar e excluir Armas, Classes, Fraquezas,
Habilidades e Personagens, falando com a API por HTTP (transporte stdio).

Autônomo de propósito: não importa nada de ``src/api``. Variáveis de ambiente:

- ``GERADOR_API_URL``   (padrão ``http://127.0.0.1:8000``)
- ``GERADOR_API_EMAIL`` e ``GERADOR_API_SENHA``: usuário usado nas chamadas. O papel dele
  define o que o Claude pode fazer (``ADMIN`` pode excluir; ``MEMBER`` recebe 403).

Atenção: em servidores stdio nada pode ser escrito no stdout (é o canal do protocolo).
"""

import logging
import os
from typing import Annotated, Any, Literal

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

API_PREFIX = "/api/v1"

logging.getLogger("httpx").setLevel(logging.WARNING)  # sem ruído nos logs do servidor

Recurso = Literal["armas", "classes", "fraquezas", "habilidades", "personagens"]
TipoArma = Literal["corpo_a_corpo", "distancia", "magica"]
TipoHabilidade = Literal["fisica", "magica", "suporte"]

IdRecurso = Annotated[int, Field(ge=1, description="Identificador numérico do registro.")]
Nome2a80 = Annotated[str, Field(min_length=2, max_length=80)]
NomeArma = Annotated[str, Field(min_length=4, max_length=80)]
Descricao = Annotated[str, Field(min_length=10, max_length=500)]
Dano = Annotated[int, Field(ge=0, le=100, description="Dano base, de 0 a 100.")]
HabilidadeIds = Annotated[
    list[Annotated[int, Field(ge=1)]],
    Field(min_length=1, description="IDs de habilidades existentes, sem repetição."),
]


# ---------------------------------------------------------------------------
# Cliente HTTP (login, token em memória, renovação em 401, tradução de erros)
# ---------------------------------------------------------------------------


class ClienteApi:
    def __init__(
        self,
        http: httpx.Client | None = None,
        base_url: str | None = None,
        email: str | None = None,
        senha: str | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("GERADOR_API_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.email = email if email is not None else os.getenv("GERADOR_API_EMAIL", "")
        self.senha = senha if senha is not None else os.getenv("GERADOR_API_SENHA", "")
        self._http = http or httpx.Client(base_url=self.base_url, timeout=15.0)
        self._token: str | None = None

    # -- infraestrutura -----------------------------------------------------

    def _enviar(self, metodo: str, caminho: str, **kwargs: Any) -> httpx.Response:
        try:
            return self._http.request(metodo, caminho, **kwargs)
        except httpx.TransportError as exc:
            raise ToolError(
                f"A API não está acessível em {self.base_url}. Confira se ela está rodando "
                f"(uvicorn src.api.main:app) e se GERADOR_API_URL está correta. ({type(exc).__name__})"
            ) from exc

    @staticmethod
    def _descrever_erro(resp: httpx.Response) -> str:
        try:
            corpo = resp.json()
            return f"A API respondeu {corpo['status']} {corpo['codigo']}: {corpo['mensagem']}"
        except (ValueError, KeyError, TypeError):
            return f"A API respondeu {resp.status_code}: {resp.text[:300]}"

    def _login(self) -> None:
        if not self.email or not self.senha:
            raise ToolError(
                "Credenciais não configuradas: defina GERADOR_API_EMAIL e GERADOR_API_SENHA "
                "no ambiente do servidor MCP."
            )
        resp = self._enviar(
            "POST", f"{API_PREFIX}/auth/login", json={"email": self.email, "senha": self.senha}
        )
        if resp.status_code != 200:
            raise ToolError("Falha no login. " + self._descrever_erro(resp))
        self._token = resp.json()["accessToken"]

    # -- uso pelas ferramentas ----------------------------------------------

    def requisicao(self, metodo: str, caminho: str, **kwargs: Any) -> Any:
        """Chama a API autenticada. Devolve o JSON (ou ``None`` em 204); erro vira ``ToolError``."""
        if self._token is None:
            self._login()
        resp = self._enviar(metodo, caminho, headers={"Authorization": f"Bearer {self._token}"}, **kwargs)
        if resp.status_code == 401:  # token expirado (60 min): renova uma vez
            self._login()
            resp = self._enviar(
                metodo, caminho, headers={"Authorization": f"Bearer {self._token}"}, **kwargs
            )
        if resp.status_code >= 400:
            raise ToolError(self._descrever_erro(resp))
        return None if resp.status_code == 204 else resp.json()


_cliente: ClienteApi | None = None


def definir_cliente(cliente: ClienteApi | None) -> None:
    """Troca o cliente HTTP (usado nos testes)."""
    global _cliente
    _cliente = cliente


def api() -> ClienteApi:
    global _cliente
    if _cliente is None:
        _cliente = ClienteApi()
    return _cliente


# ---------------------------------------------------------------------------
# Servidor e ferramentas
# ---------------------------------------------------------------------------

mcp = MCPServer(
    "gerador-de-personagens",
    instructions=(
        "Gerencia a API de Gerador de Personagens (RPG): armas, classes, fraquezas, habilidades "
        "e personagens. Para criar ou atualizar um personagem, primeiro use `listar` em classes, "
        "armas, fraquezas e habilidades para descobrir os IDs; para um personagem sorteado, use `criar_personagem_aleatorio`, que não precisa de IDs. Atualizações (`atualizar_*`) "
        "substituem o registro inteiro: use `buscar` antes e reenvie os campos que não mudam. "
        "Só use `excluir` quando a pessoa pedir explicitamente e estiver claro qual registro; "
        "recursos vinculados a personagens não podem ser excluídos (erro 409)."
    ),
)

SOMENTE_LEITURA = ToolAnnotations(read_only_hint=True, open_world_hint=False)
ESCRITA = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)
DESTRUTIVA = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)


@mcp.tool(annotations=SOMENTE_LEITURA)
def quem_sou_eu() -> dict[str, Any]:
    """Mostra o usuário e o papel (ADMIN ou MEMBER) com que o servidor acessa a API."""
    return api().requisicao("GET", f"{API_PREFIX}/auth/me")


@mcp.tool(annotations=SOMENTE_LEITURA)
def listar(
    recurso: Recurso,
    pagina: Annotated[int, Field(ge=1)] = 1,
    limite: Annotated[int, Field(ge=1, le=100)] = 10,
    nome: Annotated[
        str | None,
        Field(min_length=1, max_length=80, description="Filtra por nome (contém, sem diferenciar maiúsculas)."),
    ] = None,
) -> dict[str, Any]:
    """Lista registros de um recurso, com paginação e filtro opcional por nome.

    Retorna `itens`, `pagina`, `limite` e `total` (total em todas as páginas).
    """
    params: dict[str, Any] = {"pagina": pagina, "limite": limite}
    if nome:
        params["nome"] = nome
    return api().requisicao("GET", f"{API_PREFIX}/{recurso}", params=params)


@mcp.tool(annotations=SOMENTE_LEITURA)
def buscar(recurso: Recurso, id: IdRecurso) -> dict[str, Any]:
    """Busca um registro pelo ID. Personagens vêm com classe, arma, fraqueza e habilidades."""
    return api().requisicao("GET", f"{API_PREFIX}/{recurso}/{id}")


@mcp.tool(annotations=DESTRUTIVA)
def excluir(recurso: Recurso, id: IdRecurso) -> dict[str, Any]:
    """Exclui definitivamente um registro (exige papel ADMIN).

    Classes, armas, fraquezas e habilidades vinculadas a personagens não podem ser excluídas.
    """
    api().requisicao("DELETE", f"{API_PREFIX}/{recurso}/{id}")
    return {"excluido": True, "recurso": recurso, "id": id}


# -- Armas --------------------------------------------------------------------


@mcp.tool(annotations=ESCRITA)
def criar_arma(nome: NomeArma, dano: Dano, tipo: TipoArma) -> dict[str, Any]:
    """Cria uma arma. `tipo`: corpo_a_corpo, distancia ou magica."""
    return api().requisicao("POST", f"{API_PREFIX}/armas", json={"nome": nome, "dano": dano, "tipo": tipo})


@mcp.tool(annotations=ESCRITA)
def atualizar_arma(id: IdRecurso, nome: NomeArma, dano: Dano, tipo: TipoArma) -> dict[str, Any]:
    """Substitui todos os dados de uma arma existente (envie todos os campos)."""
    return api().requisicao(
        "PUT", f"{API_PREFIX}/armas/{id}", json={"nome": nome, "dano": dano, "tipo": tipo}
    )


# -- Classes ------------------------------------------------------------------


@mcp.tool(annotations=ESCRITA)
def criar_classe(nome: Nome2a80, descricao: Descricao) -> dict[str, Any]:
    """Cria uma classe de personagem (ex.: Guerreiro, Mago)."""
    return api().requisicao("POST", f"{API_PREFIX}/classes", json={"nome": nome, "descricao": descricao})


@mcp.tool(annotations=ESCRITA)
def atualizar_classe(id: IdRecurso, nome: Nome2a80, descricao: Descricao) -> dict[str, Any]:
    """Substitui todos os dados de uma classe existente (envie todos os campos)."""
    return api().requisicao(
        "PUT", f"{API_PREFIX}/classes/{id}", json={"nome": nome, "descricao": descricao}
    )


# -- Fraquezas ----------------------------------------------------------------


@mcp.tool(annotations=ESCRITA)
def criar_fraqueza(nome: Nome2a80, descricao: Descricao) -> dict[str, Any]:
    """Cria uma fraqueza (ponto fraco) para personagens."""
    return api().requisicao("POST", f"{API_PREFIX}/fraquezas", json={"nome": nome, "descricao": descricao})


@mcp.tool(annotations=ESCRITA)
def atualizar_fraqueza(id: IdRecurso, nome: Nome2a80, descricao: Descricao) -> dict[str, Any]:
    """Substitui todos os dados de uma fraqueza existente (envie todos os campos)."""
    return api().requisicao(
        "PUT", f"{API_PREFIX}/fraquezas/{id}", json={"nome": nome, "descricao": descricao}
    )


# -- Habilidades --------------------------------------------------------------


@mcp.tool(annotations=ESCRITA)
def criar_habilidade(
    nome: Nome2a80, tipo: TipoHabilidade, descricao: Descricao, dano: Dano
) -> dict[str, Any]:
    """Cria uma habilidade. `tipo`: fisica, magica ou suporte (suporte pode ter dano 0)."""
    corpo = {"nome": nome, "tipo": tipo, "descricao": descricao, "dano": dano}
    return api().requisicao("POST", f"{API_PREFIX}/habilidades", json=corpo)


@mcp.tool(annotations=ESCRITA)
def atualizar_habilidade(
    id: IdRecurso, nome: Nome2a80, tipo: TipoHabilidade, descricao: Descricao, dano: Dano
) -> dict[str, Any]:
    """Substitui todos os dados de uma habilidade existente (envie todos os campos)."""
    corpo = {"nome": nome, "tipo": tipo, "descricao": descricao, "dano": dano}
    return api().requisicao("PUT", f"{API_PREFIX}/habilidades/{id}", json=corpo)


# -- Personagens --------------------------------------------------------------


def _corpo_personagem(
    nome: str, classe_id: int, habilidade_ids: list[int], arma_id: int, fraqueza_id: int
) -> dict[str, Any]:
    return {
        "nome": nome,
        "classeId": classe_id,
        "habilidadeIds": habilidade_ids,
        "armaId": arma_id,
        "fraquezaId": fraqueza_id,
    }


@mcp.tool(annotations=ESCRITA)
def criar_personagem(
    nome: Nome2a80,
    classe_id: IdRecurso,
    habilidade_ids: HabilidadeIds,
    arma_id: IdRecurso,
    fraqueza_id: IdRecurso,
) -> dict[str, Any]:
    """Cria um personagem a partir de IDs existentes (use `listar` para descobri-los).

    Retorna o personagem com classe, arma, fraqueza e habilidades completas.
    """
    corpo = _corpo_personagem(nome, classe_id, habilidade_ids, arma_id, fraqueza_id)
    return api().requisicao("POST", f"{API_PREFIX}/personagens", json=corpo)


@mcp.tool(annotations=ESCRITA)
def criar_personagem_aleatorio(nome: Nome2a80 | None = None) -> dict[str, Any]:
    """Cria um personagem sorteando classe, arma, fraqueza e de 1 a 3 habilidades.

    A API escolhe tudo entre os registros que já existem (não precisa de IDs). `nome` é
    opcional: sem ele, a API gera um nome. Se faltar algum tipo de registro, o erro 422
    informa qual (ex.: SEM_ARMAS_CADASTRADAS).
    """
    corpo = {} if nome is None else {"nome": nome}
    return api().requisicao("POST", f"{API_PREFIX}/personagens/aleatorio", json=corpo)


@mcp.tool(annotations=ESCRITA)
def atualizar_personagem(
    id: IdRecurso,
    nome: Nome2a80,
    classe_id: IdRecurso,
    habilidade_ids: HabilidadeIds,
    arma_id: IdRecurso,
    fraqueza_id: IdRecurso,
) -> dict[str, Any]:
    """Substitui todos os dados de um personagem, inclusive o conjunto de habilidades."""
    corpo = _corpo_personagem(nome, classe_id, habilidade_ids, arma_id, fraqueza_id)
    return api().requisicao("PUT", f"{API_PREFIX}/personagens/{id}", json=corpo)


if __name__ == "__main__":
    mcp.run()
