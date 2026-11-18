"""Exceções de domínio e handlers globais no formato ``ApiError`` do contrato.

Nenhuma resposta de erro sai como ``{"detail": ...}`` (STYLEGUIDE 3.1).
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .schemas import ApiError

logger = logging.getLogger(__name__)

_DESCRICOES = {
    400: "Requisição inválida",
    401: "Não autenticado",
    403: "Acesso negado",
    404: "Não encontrado",
    409: "Recurso em uso",
    422: "Dados inválidos",
}


_EXEMPLOS_ERRO = {
    400: ("REQUISICAO_INVALIDA", "O cabeçalho Content-Type deve ser application/json."),
    401: ("NAO_AUTENTICADO", "Autenticação ausente ou inválida."),
    403: ("ACESSO_NEGADO", "Você não tem permissão para executar esta operação."),
    422: ("DADOS_INVALIDOS", "Dados inválidos — nome: String should have at least 4 characters."),
}


def respostas(*status: int, recurso: str | None = None) -> dict[int | str, dict[str, Any]]:
    """Documenta (OpenAPI) os erros ``ApiError`` de uma rota."""
    exemplos = dict(_EXEMPLOS_ERRO)
    if recurso is not None:
        exemplos[404] = _NAO_ENCONTRADO[recurso]
        exemplos[409] = (
            "RECURSO_EM_USO",
            f"Não é possível excluir a {recurso}: ela está vinculada a um ou mais personagens.",
        )
    docs: dict[int | str, dict[str, Any]] = {}
    for s in status:
        doc: dict[str, Any] = {"model": ApiError, "description": _DESCRICOES[s]}
        if s in exemplos:
            codigo, mensagem = exemplos[s]
            doc["content"] = {
                "application/json": {
                    "example": {"status": s, "codigo": codigo, "mensagem": mensagem}
                }
            }
        docs[s] = doc
    return docs


def resposta_erro(
    status: int, codigo: str, mensagem: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    corpo = ApiError(status=status, codigo=codigo, mensagem=mensagem[:500])
    return JSONResponse(status_code=status, content=corpo.model_dump(), headers=headers)


# ---------------------------------------------------------------------------
# Exceções de domínio
# ---------------------------------------------------------------------------


class ApiException(Exception):
    def __init__(
        self, status: int, codigo: str, mensagem: str, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(mensagem)
        self.status = status
        self.codigo = codigo
        self.mensagem = mensagem
        self.headers = headers


_NAO_ENCONTRADO = {
    "arma": ("ARMA_NAO_ENCONTRADA", "Não existe arma com o ID informado."),
    "classe": ("CLASSE_NAO_ENCONTRADA", "Não existe classe com o ID informado."),
    "fraqueza": ("FRAQUEZA_NAO_ENCONTRADA", "Não existe fraqueza com o ID informado."),
    "habilidade": ("HABILIDADE_NAO_ENCONTRADA", "Não existe habilidade com o ID informado."),
    "personagem": ("PERSONAGEM_NAO_ENCONTRADO", "Não existe personagem com o ID informado."),
}


class NaoEncontradoError(ApiException):
    """404 — ``recurso`` é uma chave de ``_NAO_ENCONTRADO``."""

    def __init__(self, recurso: str) -> None:
        codigo, mensagem = _NAO_ENCONTRADO[recurso]
        super().__init__(404, codigo, mensagem)


class ReferenciaInvalidaError(ApiException):
    """422 — id de classe/arma/fraqueza/habilidade inexistente no corpo (D6)."""

    def __init__(self, recurso: str, mensagem: str) -> None:
        codigo, _ = _NAO_ENCONTRADO[recurso]
        super().__init__(422, codigo, mensagem)


_SEM_CADASTRO = {
    "classe": ("SEM_CLASSES_CADASTRADAS", "classe"),
    "arma": ("SEM_ARMAS_CADASTRADAS", "arma"),
    "fraqueza": ("SEM_FRAQUEZAS_CADASTRADAS", "fraqueza"),
    "habilidade": ("SEM_HABILIDADES_CADASTRADAS", "habilidade"),
}


class SemRecursosError(ApiException):
    """422 — não há nenhum registro do tipo para sortear (D11)."""

    def __init__(self, recurso: str) -> None:
        codigo, nome = _SEM_CADASTRO[recurso]
        super().__init__(
            422,
            codigo,
            f"Não há nenhuma {nome} cadastrada para sortear. Cadastre ao menos uma antes.",
        )


class RecursoEmUsoError(ApiException):
    """409 — exclusão de recurso vinculado a personagens (D7)."""

    def __init__(self, recurso: str) -> None:
        super().__init__(
            409,
            "RECURSO_EM_USO",
            f"Não é possível excluir a {recurso}: ela está vinculada a um ou mais personagens.",
        )


class NaoAutenticadoError(ApiException):
    def __init__(self, mensagem: str = "Autenticação ausente ou inválida.") -> None:
        super().__init__(401, "NAO_AUTENTICADO", mensagem, {"WWW-Authenticate": "Bearer"})


class AcessoNegadoError(ApiException):
    def __init__(self, mensagem: str = "Você não tem permissão para executar esta operação.") -> None:
        super().__init__(403, "ACESSO_NEGADO", mensagem)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

_CODIGOS_HTTP = {
    404: "ROTA_NAO_ENCONTRADA",
    405: "METODO_NAO_PERMITIDO",
}


async def _tratar_api_exception(_: Request, exc: ApiException) -> JSONResponse:
    return resposta_erro(exc.status, exc.codigo, exc.mensagem, exc.headers)


def _malformado(erro: dict[str, Any]) -> bool:
    """D5: 400 = JSON inválido ou tipo errado em path/query (ex.: ``id=abc``)."""
    tipo: str = erro["type"]
    loc = erro["loc"]
    if tipo == "json_invalid":
        return True
    if loc and loc[0] in ("path", "query"):
        return tipo.endswith("_parsing") or tipo.endswith("_type") or tipo == "int_from_float"
    return False


def _descrever(erro: dict[str, Any]) -> str:
    if erro["type"] == "json_invalid":
        return "o corpo da requisição não é um JSON válido"
    loc = [str(p) for p in erro["loc"]]
    partes = loc[1:] if loc and loc[0] == "body" else loc
    campo = ".".join(partes) or "corpo da requisição"
    return f"{campo}: {erro['msg']}"


async def _tratar_validacao(_: Request, exc: RequestValidationError) -> JSONResponse:
    erros = exc.errors()
    malformada = any(_malformado(e) for e in erros)
    detalhes = "; ".join(_descrever(e) for e in erros)
    if malformada:
        return resposta_erro(400, "REQUISICAO_INVALIDA", f"Requisição malformada — {detalhes}.")
    return resposta_erro(422, "DADOS_INVALIDOS", f"Dados inválidos — {detalhes}.")


async def _tratar_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    codigo = _CODIGOS_HTTP.get(exc.status_code, "ERRO_HTTP")
    mensagem = str(exc.detail) if exc.detail else "Erro na requisição."
    status = exc.status_code if 400 <= exc.status_code <= 599 else 500
    return resposta_erro(status, codigo, mensagem, dict(exc.headers) if exc.headers else None)


async def _tratar_erro_interno(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erro interno não tratado", exc_info=exc)
    return resposta_erro(500, "ERRO_INTERNO", "Ocorreu um erro interno. Tente novamente mais tarde.")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiException, _tratar_api_exception)
    app.add_exception_handler(RequestValidationError, _tratar_validacao)
    app.add_exception_handler(StarletteHTTPException, _tratar_http)
    app.add_exception_handler(Exception, _tratar_erro_interno)
