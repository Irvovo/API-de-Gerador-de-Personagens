"""Testes de contrato e persistência ORM da coleção Armas."""

import pytest

URL = "/api/v1/armas"
ATUALIZADO = {"nome": "Espada encantada", "dano": 50, "tipo": "magica"}
CODIGO_404 = "ARMA_NAO_ENCONTRADA"


def payload(nome="Espada longa"):
    return {"nome": nome, "dano": 25, "tipo": "corpo_a_corpo"}


def criar(client, headers, nome="Espada longa"):
    resp = client.post(URL, json=payload(nome), headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _sem_id(corpo):
    return {k: v for k, v in corpo.items() if k != "id"}


def test_crud_completo_com_persistencia(client, admin_headers):
    criado = criar(client, admin_headers)
    assert criado["id"] >= 1
    assert _sem_id(criado) == payload()

    # persistência verificada por GET após cada escrita
    assert client.get(f"{URL}/{criado['id']}", headers=admin_headers).json() == criado

    resp = client.put(f"{URL}/{criado['id']}", json=ATUALIZADO, headers=admin_headers)
    assert resp.status_code == 200
    esperado = {"id": criado["id"], **ATUALIZADO}
    assert resp.json() == esperado
    assert client.get(f"{URL}/{criado['id']}", headers=admin_headers).json() == esperado

    resp = client.delete(f"{URL}/{criado['id']}", headers=admin_headers)
    assert resp.status_code == 204
    assert resp.content == b""
    resp = client.get(f"{URL}/{criado['id']}", headers=admin_headers)
    assert resp.status_code == 404
    assert resp.json()["codigo"] == CODIGO_404


def test_paginacao(client, admin_headers):
    ids = [criar(client, admin_headers, n)["id"] for n in ("Alfa item", "Beta item", "Gama item")]

    padrao = client.get(URL, headers=admin_headers).json()
    assert (padrao["pagina"], padrao["limite"], padrao["total"]) == (1, 10, 3)
    assert [i["id"] for i in padrao["itens"]] == ids  # ordenação estável por id

    pag2 = client.get(URL, params={"pagina": 2, "limite": 2}, headers=admin_headers).json()
    assert (pag2["pagina"], pag2["limite"], pag2["total"]) == (2, 2, 3)
    assert [i["id"] for i in pag2["itens"]] == ids[2:]

    alem = client.get(URL, params={"pagina": 5}, headers=admin_headers).json()
    assert alem["itens"] == [] and alem["total"] == 3


def test_filtro_por_nome_contem_sem_diferenciar_maiusculas(client, admin_headers):
    for nome in ("Lanca Sagrada", "lanca curta", "Machado"):
        criar(client, admin_headers, nome)
    resp = client.get(URL, params={"nome": "LANCA"}, headers=admin_headers).json()
    assert resp["total"] == 2
    assert sorted(i["nome"] for i in resp["itens"]) == ["Lanca Sagrada", "lanca curta"]
    assert client.get(URL, params={"nome": "inexistente"}, headers=admin_headers).json()["total"] == 0


def test_filtro_nome_trata_curinga_como_texto(client, admin_headers):
    criar(client, admin_headers, "Machado")
    assert client.get(URL, params={"nome": "%"}, headers=admin_headers).json()["total"] == 0


@pytest.mark.parametrize(
    "corpo,campo",
    [
        ({"nome": "abc", "dano": 25, "tipo": "magica"}, "nome"),
        ({"nome": "a" * 81, "dano": 25, "tipo": "magica"}, "nome"),
        ({"nome": "Espada", "dano": 101, "tipo": "magica"}, "dano"),
        ({"nome": "Espada", "dano": -1, "tipo": "magica"}, "dano"),
        ({"nome": "Espada", "dano": 25, "tipo": "lanca"}, "tipo"),
    ],
)
def test_dados_invalidos_retornam_422(client, admin_headers, corpo, campo):
    resp = client.post(URL, json=corpo, headers=admin_headers)
    assert resp.status_code == 422
    erro = resp.json()
    assert erro["codigo"] == "DADOS_INVALIDOS"
    assert campo in erro["mensagem"]

    criado = criar(client, admin_headers)
    resp = client.put(f"{URL}/{criado['id']}", json=corpo, headers=admin_headers)
    assert resp.status_code == 422
    assert resp.json()["codigo"] == "DADOS_INVALIDOS"
    # nada foi alterado
    assert client.get(f"{URL}/{criado['id']}", headers=admin_headers).json() == criado


@pytest.mark.parametrize("campo", ["nome", "dano", "tipo"])
def test_campo_obrigatorio_ausente_retorna_422(client, admin_headers, campo):
    corpo = payload()
    del corpo[campo]
    resp = client.post(URL, json=corpo, headers=admin_headers)
    assert resp.status_code == 422
    assert campo in resp.json()["mensagem"]


@pytest.mark.parametrize("metodo", ["get", "put", "delete"])
def test_id_inexistente_retorna_404(client, admin_headers, metodo):
    kwargs = {"json": ATUALIZADO} if metodo == "put" else {}
    resp = getattr(client, metodo)(f"{URL}/9999", headers=admin_headers, **kwargs)
    assert resp.status_code == 404
    assert resp.json()["codigo"] == CODIGO_404


def test_id_nao_numerico_retorna_400_e_id_zero_retorna_422(client, admin_headers):
    resp = client.get(f"{URL}/abc", headers=admin_headers)
    assert resp.status_code == 400
    assert resp.json()["codigo"] == "REQUISICAO_INVALIDA"
    resp = client.get(f"{URL}/0", headers=admin_headers)
    assert resp.status_code == 422
    assert resp.json()["codigo"] == "DADOS_INVALIDOS"


@pytest.mark.parametrize(
    "params,status",
    [
        ({"pagina": 0}, 422),
        ({"limite": 0}, 422),
        ({"limite": 101}, 422),
        ({"nome": ""}, 422),
        ({"nome": "x" * 81}, 422),
        ({"pagina": "abc"}, 400),
    ],
)
def test_parametros_de_consulta_invalidos(client, admin_headers, params, status):
    resp = client.get(URL, params=params, headers=admin_headers)
    assert resp.status_code == status
    assert set(resp.json()) == {"status", "codigo", "mensagem"}


def test_exclusao_de_recurso_em_uso_retorna_409(
    client, admin_headers, dados_base, personagem_criado
):
    recurso_id = dados_base["arma_id"]
    resp = client.delete(f"{URL}/{recurso_id}", headers=admin_headers)
    assert resp.status_code == 409
    assert resp.json()["codigo"] == "RECURSO_EM_USO"
    assert client.get(f"{URL}/{recurso_id}", headers=admin_headers).status_code == 200

    # depois de excluir o personagem, o recurso é liberado
    assert client.delete(
        f"/api/v1/personagens/{personagem_criado['id']}", headers=admin_headers
    ).status_code == 204
    assert client.delete(f"{URL}/{recurso_id}", headers=admin_headers).status_code == 204


def test_rbac_member_le_cria_atualiza_mas_nao_exclui(client, member_headers, admin_headers):
    criado = criar(client, member_headers)
    assert client.get(URL, headers=member_headers).status_code == 200
    assert client.get(f"{URL}/{criado['id']}", headers=member_headers).status_code == 200
    resp = client.put(f"{URL}/{criado['id']}", json=ATUALIZADO, headers=member_headers)
    assert resp.status_code == 200
    resp = client.delete(f"{URL}/{criado['id']}", headers=member_headers)
    assert resp.status_code == 403
    assert resp.json()["codigo"] == "ACESSO_NEGADO"
    assert client.get(f"{URL}/{criado['id']}", headers=admin_headers).status_code == 200


@pytest.mark.parametrize(
    "metodo,sufixo",
    [("get", ""), ("post", ""), ("get", "/1"), ("put", "/1"), ("delete", "/1")],
)
def test_sem_token_retorna_401(client, metodo, sufixo):
    kwargs = {"json": payload()} if metodo in ("post", "put") else {}
    resp = getattr(client, metodo)(f"{URL}{sufixo}", **kwargs)
    assert resp.status_code == 401
    assert resp.json()["codigo"] == "NAO_AUTENTICADO"
