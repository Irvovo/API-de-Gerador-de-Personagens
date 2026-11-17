"""Infraestrutura de testes: SQLite isolado em memória, usuários e tokens JWT."""

import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

# Configuração ANTES de importar a aplicação: o banco do módulo `database` vira
# SQLite em memória (o lifespan nunca toca o arquivo real), e o hash de senha
# usa poucas iterações para os testes rodarem rápido.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["PBKDF2_ITERATIONS"] = "1000"
os.environ["JWT_SECRET"] = "chave-de-teste-com-mais-de-32-bytes-0123456789"

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from src.api import models  # noqa: E402
from src.api.database import criar_engine, get_db  # noqa: E402
from src.api.main import app  # noqa: E402
from src.api.security import JWT_ALGORITHM, JWT_SECRET, criar_access_token, hash_senha  # noqa: E402

SENHA_ADMIN = "Admin@123"
SENHA_MEMBER = "Member@123"


# 9.1 / 9.2 — engine em memória (StaticPool + PRAGMA foreign_keys=ON) recriado a cada teste
@pytest.fixture()
def engine():
    eng = criar_engine("sqlite://")
    models.Base.metadata.create_all(eng)
    yield eng
    models.Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db(session_factory):
    with session_factory() as sessao:
        yield sessao


# 9.3 / 9.4 — override de get_db; o TestClient é usado sem `with`, então o lifespan não roda
@pytest.fixture()
def client(session_factory):
    def _get_db():
        sessao = session_factory()
        try:
            yield sessao
        finally:
            sessao.close()

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# 9.5 — usuários e tokens
def _criar_usuario(db, nome, email, senha, role):
    user = models.UserModel(nome=nome, email=email, senha_hash=hash_senha(senha), role=role)
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def admin(db):
    return _criar_usuario(db, "Admin", "admin@teste.com", SENHA_ADMIN, models.Role.ADMIN)


@pytest.fixture()
def member(db):
    return _criar_usuario(db, "Membro", "member@teste.com", SENHA_MEMBER, models.Role.MEMBER)


@pytest.fixture()
def admin_headers(admin):
    return {"Authorization": f"Bearer {criar_access_token(admin)}"}


@pytest.fixture()
def member_headers(member):
    return {"Authorization": f"Bearer {criar_access_token(member)}"}


@pytest.fixture()
def token_expirado(admin):
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": str(admin.id),
        "email": admin.email,
        "role": "ADMIN",
        "iat": agora - timedelta(hours=2),
        "exp": agora - timedelta(hours=1),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@pytest.fixture()
def token_malformado():
    return "isto.nao-e.um-jwt"


# 9.6 — dados base para os testes de personagem
@pytest.fixture()
def dados_base(db):
    classe = models.ClasseModel(nome="Guerreiro", descricao="Classe de combate físico e armas.")
    arma = models.ArmaModel(nome="Espada longa", dano=25, tipo=models.TipoArma.CORPO_A_CORPO)
    fraqueza = models.FraquezaModel(nome="Fogo", descricao="Recebe dano adicional de fogo.")
    h1 = models.HabilidadeModel(
        nome="Bola de fogo", tipo=models.TipoHabilidade.MAGICA,
        descricao="Lança uma esfera de fogo.", dano=40,
    )
    h2 = models.HabilidadeModel(
        nome="Golpe giratório", tipo=models.TipoHabilidade.FISICA,
        descricao="Gira a arma em volta.", dano=30,
    )
    db.add_all([classe, arma, fraqueza, h1, h2])
    db.commit()
    return {
        "classe_id": classe.id,
        "arma_id": arma.id,
        "fraqueza_id": fraqueza.id,
        "habilidade_ids": [h1.id, h2.id],
    }


@pytest.fixture()
def payload_personagem(dados_base):
    def _montar(**sobrescrever):
        corpo = {
            "nome": "Lyra",
            "classeId": dados_base["classe_id"],
            "habilidadeIds": list(dados_base["habilidade_ids"]),
            "armaId": dados_base["arma_id"],
            "fraquezaId": dados_base["fraqueza_id"],
        }
        corpo.update(sobrescrever)
        return corpo

    return _montar


@pytest.fixture()
def personagem_criado(client, admin_headers, payload_personagem):
    resp = client.post("/api/v1/personagens", json=payload_personagem(), headers=admin_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# 9.7 — contador de queries SQL por bloco (testes de N+1)
@pytest.fixture()
def contar_queries(engine):
    @contextmanager
    def _contar():
        contador = {"n": 0}

        def _ao_executar(*_args, **_kwargs):
            contador["n"] += 1

        event.listen(engine, "before_cursor_execute", _ao_executar)
        try:
            yield contador
        finally:
            event.remove(engine, "before_cursor_execute", _ao_executar)

    return _contar
