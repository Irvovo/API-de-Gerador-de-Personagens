"""Login, token inválido/ausente (401) e RBAC (403)."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import func, select

from src.api import models
from src.api.database import seed_db
from src.api.security import (
    JWT_ALGORITHM,
    JWT_SECRET,
    hash_senha,
    verificar_senha,
)

from .conftest import SENHA_ADMIN, SENHA_MEMBER

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


def test_login_valido_retorna_token_com_claims_esperadas(client, admin):
    resp = client.post(LOGIN, json={"email": admin.email, "senha": SENHA_ADMIN})
    assert resp.status_code == 200
    corpo = resp.json()
    assert set(corpo) == {"accessToken", "tokenType", "expiresIn"}
    assert corpo["tokenType"] == "bearer" and corpo["expiresIn"] == 3600

    claims = jwt.decode(corpo["accessToken"], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert set(claims) == {"sub", "email", "role", "iat", "exp"}
    assert claims["sub"] == str(admin.id) and claims["email"] == admin.email
    assert claims["role"] == "ADMIN"
    assert claims["exp"] - claims["iat"] == 60 * 60


def test_login_ignora_maiusculas_no_email(client, admin):
    resp = client.post(LOGIN, json={"email": admin.email.upper(), "senha": SENHA_ADMIN})
    assert resp.status_code == 200


@pytest.mark.parametrize(
    "email,senha",
    [("admin@teste.com", "senha-errada"), ("ninguem@teste.com", SENHA_ADMIN)],
)
def test_login_invalido_retorna_401(client, admin, email, senha):
    resp = client.post(LOGIN, json={"email": email, "senha": senha})
    assert resp.status_code == 401
    assert resp.json() == {
        "status": 401, "codigo": "NAO_AUTENTICADO", "mensagem": "E-mail ou senha inválidos.",
    }
    assert resp.headers["www-authenticate"] == "Bearer"


def test_login_sem_campos_retorna_422(client):
    resp = client.post(LOGIN, json={"email": "a@b.com"})
    assert resp.status_code == 422 and "senha" in resp.json()["mensagem"]


def test_me_com_token_valido(client, admin, admin_headers):
    resp = client.get(ME, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == {"id": admin.id, "nome": "Admin", "email": admin.email, "role": "ADMIN"}
    assert "senha_hash" not in resp.text


def test_me_sem_header_retorna_401(client):
    resp = client.get(ME)
    assert resp.status_code == 401 and resp.json()["codigo"] == "NAO_AUTENTICADO"


def test_me_com_token_malformado_retorna_401(client, token_malformado):
    resp = client.get(ME, headers={"Authorization": f"Bearer {token_malformado}"})
    assert resp.status_code == 401 and resp.json()["codigo"] == "NAO_AUTENTICADO"


def test_me_com_token_expirado_retorna_401(client, token_expirado):
    resp = client.get(ME, headers={"Authorization": f"Bearer {token_expirado}"})
    assert resp.status_code == 401
    assert resp.json()["codigo"] == "NAO_AUTENTICADO" and "expirado" in resp.json()["mensagem"]


def test_token_assinado_com_outro_segredo_retorna_401(client, admin):
    agora = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(admin.id), "email": admin.email, "role": "ADMIN",
         "iat": agora, "exp": agora + timedelta(minutes=5)},
        "outro-segredo-com-mais-de-32-bytes-0123456789", algorithm=JWT_ALGORITHM,
    )
    assert client.get(ME, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_esquema_diferente_de_bearer_retorna_401(client):
    resp = client.get(ME, headers={"Authorization": "Basic YWRtaW46YWRtaW4="})
    assert resp.status_code == 401 and resp.json()["codigo"] == "NAO_AUTENTICADO"


def test_token_de_usuario_removido_retorna_401(client, db, admin, admin_headers):
    db.delete(admin)
    db.commit()
    assert client.get(ME, headers=admin_headers).status_code == 401


def test_member_em_delete_retorna_403_e_admin_retorna_204(client, member_headers, admin_headers):
    criada = client.post(
        "/api/v1/armas", json={"nome": "Espada", "dano": 10, "tipo": "magica"}, headers=admin_headers
    ).json()
    resp = client.delete(f"/api/v1/armas/{criada['id']}", headers=member_headers)
    assert resp.status_code == 403
    assert resp.json()["codigo"] == "ACESSO_NEGADO" and resp.json()["status"] == 403
    assert client.delete(f"/api/v1/armas/{criada['id']}", headers=admin_headers).status_code == 204


def test_apenas_login_e_publico(client):
    # qualquer rota de recurso exige token
    for rota in ("armas", "classes", "fraquezas", "habilidades", "personagens"):
        assert client.get(f"/api/v1/{rota}").status_code == 401


# --- senhas e seed ---------------------------------------------------------


def test_hash_e_verificacao_de_senha():
    h = hash_senha("segredo")
    assert h.startswith("pbkdf2_sha256$") and "segredo" not in h
    assert hash_senha("segredo") != h  # salt aleatório
    assert verificar_senha("segredo", h)
    assert not verificar_senha("outra", h)
    assert not verificar_senha("segredo", "lixo")
    assert not verificar_senha("segredo", "md5$1$zz$zz")


def test_seed_e_idempotente_e_usuarios_do_seed_fazem_login(client, db):
    seed_db(db)
    seed_db(db)
    contagens = {
        m.__name__: db.scalar(select(func.count()).select_from(m))
        for m in (models.UserModel, models.ClasseModel, models.ArmaModel,
                  models.FraquezaModel, models.HabilidadeModel)
    }
    assert contagens["UserModel"] == 2
    assert all(n > 0 for n in contagens.values())
    seed_db(db)
    assert db.scalar(select(func.count()).select_from(models.ClasseModel)) == contagens["ClasseModel"]

    for email, senha, role in (
        ("admin@example.com", "Admin@123", "ADMIN"),
        ("member@example.com", "Member@123", "MEMBER"),
    ):
        resp = client.post(LOGIN, json={"email": email, "senha": senha})
        assert resp.status_code == 200
        token = resp.json()["accessToken"]
        me = client.get(ME, headers={"Authorization": f"Bearer {token}"}).json()
        assert me["role"] == role
