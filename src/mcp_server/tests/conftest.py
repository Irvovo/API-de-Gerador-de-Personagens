"""Fixtures dos testes do servidor MCP: a API real (em memória) atrás do cliente HTTP."""

import os

# Antes de importar a API: banco em memória e hash de senha barato.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["PBKDF2_ITERATIONS"] = "1000"
os.environ["JWT_SECRET"] = "chave-de-teste-com-mais-de-32-bytes-0123456789"

import asyncio  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from src.api import models  # noqa: E402
from src.api.database import criar_engine, get_db  # noqa: E402
from src.api.main import app  # noqa: E402
from src.api.security import hash_senha  # noqa: E402
from src.mcp_server import server  # noqa: E402

SENHA_ADMIN = "Admin@123"
SENHA_MEMBER = "Member@123"


@pytest.fixture()
def api_http():
    """Cliente HTTP (TestClient) ligado à API com banco isolado e dois usuários."""
    engine = criar_engine("sqlite://")
    models.Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with fabrica() as db:
        db.add_all(
            [
                models.UserModel(nome="Admin", email="admin@teste.com",
                                 senha_hash=hash_senha(SENHA_ADMIN), role=models.Role.ADMIN),
                models.UserModel(nome="Membro", email="member@teste.com",
                                 senha_hash=hash_senha(SENHA_MEMBER), role=models.Role.MEMBER),
            ]
        )
        db.commit()

    def _get_db():
        sessao = fabrica()
        try:
            yield sessao
        finally:
            sessao.close()

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    server.definir_cliente(None)
    engine.dispose()


@pytest.fixture()
def como_admin(api_http):
    server.definir_cliente(server.ClienteApi(http=api_http, email="admin@teste.com", senha=SENHA_ADMIN))
    return server.api()


@pytest.fixture()
def como_member(api_http):
    server.definir_cliente(server.ClienteApi(http=api_http, email="member@teste.com", senha=SENHA_MEMBER))
    return server.api()


@pytest.fixture()
def chamar():
    """Chama uma ferramenta pelo servidor MCP e devolve o conteúdo estruturado."""

    def _chamar(ferramenta, /, **argumentos):
        resultado = asyncio.run(server.mcp.call_tool(ferramenta, argumentos))
        return resultado.structured_content

    return _chamar
