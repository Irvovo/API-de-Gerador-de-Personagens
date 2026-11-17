"""Instância FastAPI: lifespan (init_db + seed), CORS, middleware JSON e rotas."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db, seed_db
from .exceptions import register_exception_handlers, resposta_erro
from .routers import armas, auth, classes, fraquezas, habilidades, personagens

API_PREFIX = "/api/v1"

DESCRICAO = (
    "API de Gerador de Personagens (RPG). Gerencia os recursos Arma, Classe, Fraqueza, "
    "Habilidade e Personagem, com autenticação JWT (Bearer) e controle de acesso por papéis "
    "(ADMIN e MEMBER). Erros seguem o schema ApiError (status, codigo, mensagem)."
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed_db()
    yield


app = FastAPI(
    title="API de Gerador de Personagens",
    version="2.0.0",
    description=DESCRICAO,
    lifespan=lifespan,
)

register_exception_handlers(app)


@app.middleware("http")
async def exigir_json(request: Request, call_next):
    """POST/PUT só aceitam ``Content-Type: application/json`` (400 no formato ApiError)."""
    if request.method in ("POST", "PUT"):
        tipo = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if tipo != "application/json":
            return resposta_erro(
                400,
                "REQUISICAO_INVALIDA",
                "O cabeçalho Content-Type deve ser application/json.",
            )
    return await call_next(request)


# Adicionado por último => camada mais externa (cabeçalhos CORS também nos erros).
_origens = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origens,
    allow_methods=["*"],
    allow_headers=["*"],
)

for modulo in (auth, armas, habilidades, classes, fraquezas, personagens):
    app.include_router(modulo.router, prefix=API_PREFIX)
