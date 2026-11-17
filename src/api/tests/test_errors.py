"""Todo erro sai no formato ApiError (status, codigo, mensagem) — nunca {"detail": ...}."""

import pytest

from src.api.main import app

FORMATO = {"status", "codigo", "mensagem"}


def _checar(resp, status, codigo):
    assert resp.status_code == status, resp.text
    corpo = resp.json()
    assert "detail" not in corpo
    assert set(corpo) == FORMATO
    assert corpo["status"] == status
    assert corpo["codigo"] == codigo
    assert 1 <= len(corpo["codigo"]) <= 80 and 1 <= len(corpo["mensagem"]) <= 500
    return corpo


def test_400_json_malformado(client, admin_headers):
    resp = client.post(
        "/api/v1/armas", content="{nome: ", headers={**admin_headers, "Content-Type": "application/json"}
    )
    corpo = _checar(resp, 400, "REQUISICAO_INVALIDA")
    assert "JSON" in corpo["mensagem"]


def test_400_id_nao_numerico_no_path(client, admin_headers):
    corpo = _checar(client.get("/api/v1/armas/abc", headers=admin_headers), 400, "REQUISICAO_INVALIDA")
    assert "id" in corpo["mensagem"]


def test_400_tipo_errado_na_query(client, admin_headers):
    resp = client.get("/api/v1/classes", params={"limite": "dez"}, headers=admin_headers)
    corpo = _checar(resp, 400, "REQUISICAO_INVALIDA")
    assert "limite" in corpo["mensagem"]


def test_400_content_type_diferente_de_json(client, admin_headers):
    resp = client.post(
        "/api/v1/armas", content="nome=Espada", headers={**admin_headers, "Content-Type": "text/plain"}
    )
    _checar(resp, 400, "REQUISICAO_INVALIDA")
    resp = client.put(
        "/api/v1/armas/1", content="x", headers={**admin_headers, "Content-Type": "application/x-www-form-urlencoded"}
    )
    _checar(resp, 400, "REQUISICAO_INVALIDA")


def test_401_sem_token(client):
    resp = client.get("/api/v1/armas")
    _checar(resp, 401, "NAO_AUTENTICADO")


def test_401_token_malformado_e_expirado(client, token_malformado, token_expirado):
    for token in (token_malformado, token_expirado):
        resp = client.get("/api/v1/armas", headers={"Authorization": f"Bearer {token}"})
        _checar(resp, 401, "NAO_AUTENTICADO")


def test_403_member_em_delete(client, member_headers):
    for rota in ("armas", "classes", "fraquezas", "habilidades", "personagens"):
        resp = client.delete(f"/api/v1/{rota}/1", headers=member_headers)
        _checar(resp, 403, "ACESSO_NEGADO")


@pytest.mark.parametrize(
    "rota,codigo",
    [
        ("armas", "ARMA_NAO_ENCONTRADA"),
        ("classes", "CLASSE_NAO_ENCONTRADA"),
        ("fraquezas", "FRAQUEZA_NAO_ENCONTRADA"),
        ("habilidades", "HABILIDADE_NAO_ENCONTRADA"),
        ("personagens", "PERSONAGEM_NAO_ENCONTRADO"),
    ],
)
def test_404_recurso_inexistente(client, admin_headers, rota, codigo):
    _checar(client.get(f"/api/v1/{rota}/9999", headers=admin_headers), 404, codigo)


def test_404_rota_inexistente_e_405_metodo_nao_permitido(client, admin_headers):
    _checar(client.get("/api/v1/nao-existe", headers=admin_headers), 404, "ROTA_NAO_ENCONTRADA")
    _checar(client.patch("/api/v1/armas", headers=admin_headers), 405, "METODO_NAO_PERMITIDO")


def test_409_recurso_em_uso(client, admin_headers, dados_base, personagem_criado):
    resp = client.delete(f"/api/v1/armas/{dados_base['arma_id']}", headers=admin_headers)
    corpo = _checar(resp, 409, "RECURSO_EM_USO")
    assert "arma" in corpo["mensagem"]


def test_422_violacao_de_regra_cita_os_campos(client, admin_headers):
    resp = client.post(
        "/api/v1/armas", json={"nome": "Es", "dano": 101, "tipo": "lanca"}, headers=admin_headers
    )
    corpo = _checar(resp, 422, "DADOS_INVALIDOS")
    assert all(campo in corpo["mensagem"] for campo in ("nome", "dano", "tipo"))


def test_422_corpo_ausente_e_valores_de_path_fora_do_minimo(client, admin_headers):
    resp = client.post("/api/v1/armas", content="", headers={**admin_headers, "Content-Type": "application/json"})
    _checar(resp, 422, "DADOS_INVALIDOS")
    _checar(client.get("/api/v1/armas/0", headers=admin_headers), 422, "DADOS_INVALIDOS")


def test_422_referencia_inexistente_em_personagem(client, admin_headers, payload_personagem):
    resp = client.post("/api/v1/personagens", json=payload_personagem(classeId=9999), headers=admin_headers)
    _checar(resp, 422, "CLASSE_NAO_ENCONTRADA")


def test_500_nao_expoe_stack_trace(client):
    from fastapi.testclient import TestClient

    async def _quebrar():
        raise RuntimeError("segredo interno do servidor")

    app.add_api_route("/__teste_500__", _quebrar, methods=["GET"])
    try:
        seguro = TestClient(app, raise_server_exceptions=False)
        resp = seguro.get("/__teste_500__")
    finally:
        app.router.routes.pop()
    corpo = _checar(resp, 500, "ERRO_INTERNO")
    assert "segredo interno" not in resp.text and "Traceback" not in resp.text
    assert corpo["mensagem"]
