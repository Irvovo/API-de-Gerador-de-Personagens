"""Contrato, relacionamentos (N:1 e N:N) e ausência de N+1 em Personagens."""

import random

import pytest
from sqlalchemy import func, select, text

from src.api import models
from src.api.main import app
from src.api.routers.personagens import get_aleatorio

URL = "/api/v1/personagens"


def _vinculos(db, personagem_id):
    linhas = db.execute(
        text("select habilidade_id from personagem_habilidades where personagem_id = :p"),
        {"p": personagem_id},
    )
    return sorted(r[0] for r in linhas)


def test_criar_retorna_201_com_objetos_aninhados(client, admin_headers, dados_base, payload_personagem):
    resp = client.post(URL, json=payload_personagem(), headers=admin_headers)
    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["id"] >= 1 and corpo["nome"] == "Lyra"
    assert corpo["classe"] == {
        "id": dados_base["classe_id"], "nome": "Guerreiro",
        "descricao": "Classe de combate físico e armas.",
    }
    assert corpo["arma"] == {
        "id": dados_base["arma_id"], "nome": "Espada longa", "dano": 25, "tipo": "corpo_a_corpo",
    }
    assert corpo["fraqueza"]["id"] == dados_base["fraqueza_id"]
    assert [h["id"] for h in corpo["habilidades"]] == dados_base["habilidade_ids"]
    assert corpo["habilidades"][0]["tipo"] == "magica"
    # nada de ids soltos na saída
    assert not {"classeId", "armaId", "fraquezaId", "habilidadeIds"} & set(corpo)


def test_buscar_por_id_e_listar(client, admin_headers, personagem_criado):
    assert client.get(f"{URL}/{personagem_criado['id']}", headers=admin_headers).json() == personagem_criado
    lista = client.get(URL, headers=admin_headers).json()
    assert (lista["pagina"], lista["limite"], lista["total"]) == (1, 10, 1)
    assert lista["itens"] == [personagem_criado]


def test_paginacao_e_filtro_por_nome(client, admin_headers, payload_personagem):
    ids = []
    for nome in ("Lyra", "Lyria", "Thorin"):
        resp = client.post(URL, json=payload_personagem(nome=nome), headers=admin_headers)
        ids.append(resp.json()["id"])
    pag = client.get(URL, params={"pagina": 2, "limite": 2}, headers=admin_headers).json()
    assert pag["total"] == 3 and [p["id"] for p in pag["itens"]] == ids[2:]
    filtro = client.get(URL, params={"nome": "LYR"}, headers=admin_headers).json()
    assert filtro["total"] == 2 and [p["nome"] for p in filtro["itens"]] == ["Lyra", "Lyria"]


@pytest.mark.parametrize(
    "campo,valor,codigo",
    [
        ("classeId", 9999, "CLASSE_NAO_ENCONTRADA"),
        ("armaId", 9999, "ARMA_NAO_ENCONTRADA"),
        ("fraquezaId", 9999, "FRAQUEZA_NAO_ENCONTRADA"),
        ("habilidadeIds", [1, 9999], "HABILIDADE_NAO_ENCONTRADA"),
    ],
)
def test_referencia_inexistente_retorna_422(
    client, admin_headers, payload_personagem, campo, valor, codigo
):
    resp = client.post(URL, json=payload_personagem(**{campo: valor}), headers=admin_headers)
    assert resp.status_code == 422
    erro = resp.json()
    assert erro["codigo"] == codigo and erro["status"] == 422
    assert campo in erro["mensagem"]
    assert client.get(URL, headers=admin_headers).json()["total"] == 0


@pytest.mark.parametrize(
    "corpo_extra,campo",
    [
        ({"habilidadeIds": []}, "habilidadeIds"),
        ({"habilidadeIds": [1, 1]}, "habilidadeIds"),
        ({"habilidadeIds": [0]}, "habilidadeIds"),
        ({"nome": "A"}, "nome"),
        ({"nome": "a" * 81}, "nome"),
        ({"classeId": 0}, "classeId"),
    ],
)
def test_dados_invalidos_retornam_422(client, admin_headers, payload_personagem, corpo_extra, campo):
    resp = client.post(URL, json=payload_personagem(**corpo_extra), headers=admin_headers)
    assert resp.status_code == 422
    assert resp.json()["codigo"] == "DADOS_INVALIDOS"
    assert campo in resp.json()["mensagem"]


@pytest.mark.parametrize("campo", ["nome", "classeId", "habilidadeIds", "armaId", "fraquezaId"])
def test_campo_obrigatorio_ausente_retorna_422(client, admin_headers, payload_personagem, campo):
    corpo = payload_personagem()
    del corpo[campo]
    resp = client.post(URL, json=corpo, headers=admin_headers)
    assert resp.status_code == 422 and campo in resp.json()["mensagem"]


def test_put_substitui_dados_e_conjunto_de_habilidades(
    client, admin_headers, db, dados_base, personagem_criado, payload_personagem
):
    from src.api import models

    nova_classe = models.ClasseModel(nome="Mago", descricao="Domina as artes arcanas.")
    nova_hab = models.HabilidadeModel(
        nome="Cura divina", tipo=models.TipoHabilidade.SUPORTE,
        descricao="Restaura a vida de um aliado.", dano=0,
    )
    db.add_all([nova_classe, nova_hab])
    db.commit()

    corpo = payload_personagem(
        nome="Lyra Nova", classeId=nova_classe.id, habilidadeIds=[nova_hab.id]
    )
    resp = client.put(f"{URL}/{personagem_criado['id']}", json=corpo, headers=admin_headers)
    assert resp.status_code == 200
    atualizado = resp.json()
    assert atualizado["nome"] == "Lyra Nova"
    assert atualizado["classe"]["id"] == nova_classe.id and atualizado["classe"]["nome"] == "Mago"
    assert [h["id"] for h in atualizado["habilidades"]] == [nova_hab.id]
    assert client.get(f"{URL}/{personagem_criado['id']}", headers=admin_headers).json() == atualizado
    db.expire_all()
    assert _vinculos(db, personagem_criado["id"]) == [nova_hab.id]


def test_put_com_referencia_invalida_nao_altera_o_personagem(
    client, admin_headers, personagem_criado, payload_personagem
):
    resp = client.put(
        f"{URL}/{personagem_criado['id']}",
        json=payload_personagem(armaId=9999), headers=admin_headers,
    )
    assert resp.status_code == 422 and resp.json()["codigo"] == "ARMA_NAO_ENCONTRADA"
    assert client.get(f"{URL}/{personagem_criado['id']}", headers=admin_headers).json() == personagem_criado


def test_put_e_get_de_id_inexistente_retornam_404(client, admin_headers, payload_personagem):
    resp = client.put(f"{URL}/9999", json=payload_personagem(), headers=admin_headers)
    assert resp.status_code == 404 and resp.json()["codigo"] == "PERSONAGEM_NAO_ENCONTRADO"
    resp = client.get(f"{URL}/9999", headers=admin_headers)
    assert resp.status_code == 404 and resp.json()["codigo"] == "PERSONAGEM_NAO_ENCONTRADO"
    resp = client.delete(f"{URL}/9999", headers=admin_headers)
    assert resp.status_code == 404 and resp.json()["codigo"] == "PERSONAGEM_NAO_ENCONTRADO"


def test_delete_remove_personagem_e_vinculos(client, admin_headers, db, dados_base, personagem_criado):
    assert _vinculos(db, personagem_criado["id"]) == sorted(dados_base["habilidade_ids"])
    assert client.delete(f"{URL}/{personagem_criado['id']}", headers=admin_headers).status_code == 204
    assert client.get(f"{URL}/{personagem_criado['id']}", headers=admin_headers).status_code == 404
    db.expire_all()
    assert _vinculos(db, personagem_criado["id"]) == []
    # as habilidades continuam existindo
    for hid in dados_base["habilidade_ids"]:
        assert client.get(f"/api/v1/habilidades/{hid}", headers=admin_headers).status_code == 200


def test_member_nao_exclui_personagem(client, member_headers, admin_headers, personagem_criado):
    resp = client.delete(f"{URL}/{personagem_criado['id']}", headers=member_headers)
    assert resp.status_code == 403 and resp.json()["codigo"] == "ACESSO_NEGADO"
    assert client.get(f"{URL}/{personagem_criado['id']}", headers=admin_headers).status_code == 200


def test_member_pode_criar_ler_e_atualizar(client, member_headers, payload_personagem):
    resp = client.post(URL, json=payload_personagem(), headers=member_headers)
    assert resp.status_code == 201
    pid = resp.json()["id"]
    assert client.get(f"{URL}/{pid}", headers=member_headers).status_code == 200
    resp = client.put(f"{URL}/{pid}", json=payload_personagem(nome="Outro nome"), headers=member_headers)
    assert resp.status_code == 200 and resp.json()["nome"] == "Outro nome"


def test_listagem_nao_tem_n_mais_1(client, admin_headers, payload_personagem, contar_queries):
    """O número de queries da listagem é constante com 1 ou com muitos personagens."""
    client.post(URL, json=payload_personagem(nome="Primeiro"), headers=admin_headers)
    with contar_queries() as com_um:
        resp = client.get(URL, params={"limite": 100}, headers=admin_headers)
    assert resp.json()["total"] == 1

    for i in range(8):
        client.post(URL, json=payload_personagem(nome=f"Heroi {i}"), headers=admin_headers)
    with contar_queries() as com_nove:
        resp = client.get(URL, params={"limite": 100}, headers=admin_headers)
    assert resp.json()["total"] == 9
    assert all(len(p["habilidades"]) == 2 for p in resp.json()["itens"])

    assert com_um["n"] == com_nove["n"], (com_um, com_nove)


def test_buscar_por_id_tem_numero_fixo_de_queries(client, admin_headers, personagem_criado, contar_queries):
    with contar_queries() as c:
        assert client.get(f"{URL}/{personagem_criado['id']}", headers=admin_headers).status_code == 200
    # usuário + personagem + classe + arma + fraqueza + habilidades
    assert c["n"] <= 6, c


# --- 13.5 POST /personagens/aleatorio (D11) ---------------------------------

URL_ALEATORIO = f"{URL}/aleatorio"
JSON = {"Content-Type": "application/json"}


@pytest.fixture()
def fixar_aleatorio():
    """Troca a fonte de aleatoriedade por uma semente fixa (o `client` limpa os overrides)."""

    def _fixar(semente):
        rng = random.Random(semente)  # uma instância só: a sequência continua entre as chamadas
        app.dependency_overrides[get_aleatorio] = lambda: rng

    return _fixar


@pytest.fixture()
def muitas_habilidades(db, dados_base):
    """Dados base + 3 habilidades (total 5), para exercitar o limite de 3."""
    for i in range(3):
        db.add(
            models.HabilidadeModel(
                nome=f"Habilidade extra {i}",
                tipo=models.TipoHabilidade.SUPORTE,
                descricao="Habilidade extra de teste.",
                dano=0,
            )
        )
    db.commit()


def _total_personagens(db):
    return db.scalar(select(func.count()).select_from(models.PersonagemModel))


def test_aleatorio_sem_body_gera_nome_e_retorna_personagem_completo(
    client, admin_headers, dados_base
):
    resp = client.post(URL_ALEATORIO, headers={**admin_headers, **JSON})
    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["id"] >= 1
    assert ", " in corpo["nome"] and 2 <= len(corpo["nome"]) <= 80
    assert corpo["classe"]["id"] == dados_base["classe_id"]
    assert corpo["arma"]["id"] == dados_base["arma_id"]
    assert corpo["fraqueza"]["id"] == dados_base["fraqueza_id"]
    ids = [h["id"] for h in corpo["habilidades"]]
    assert 1 <= len(ids) <= 2 and set(ids) <= set(dados_base["habilidade_ids"])
    # é o mesmo personagem que o GET devolve
    assert client.get(f"{URL}/{corpo['id']}", headers=admin_headers).json() == corpo


def test_aleatorio_com_nome_usa_o_nome_informado(client, admin_headers, dados_base):
    resp = client.post(URL_ALEATORIO, json={"nome": "Sir Teste"}, headers=admin_headers)
    assert resp.status_code == 201 and resp.json()["nome"] == "Sir Teste"


def test_aleatorio_com_objeto_vazio_gera_nome(client, admin_headers, dados_base):
    resp = client.post(URL_ALEATORIO, json={}, headers=admin_headers)
    assert resp.status_code == 201 and ", " in resp.json()["nome"]


def test_aleatorio_membro_tambem_pode(client, member_headers, dados_base):
    assert client.post(URL_ALEATORIO, json={}, headers=member_headers).status_code == 201


def test_aleatorio_mesma_semente_mesmo_resultado(
    client, admin_headers, muitas_habilidades, fixar_aleatorio
):
    def _gerar():
        fixar_aleatorio(2024)
        corpo = client.post(URL_ALEATORIO, json={}, headers=admin_headers).json()
        return (
            corpo["nome"],
            corpo["classe"]["id"],
            corpo["arma"]["id"],
            corpo["fraqueza"]["id"],
            [h["id"] for h in corpo["habilidades"]],
        )

    assert _gerar() == _gerar()


def test_aleatorio_sempre_de_1_a_3_habilidades_distintas(
    client, admin_headers, muitas_habilidades, fixar_aleatorio
):
    fixar_aleatorio(1)
    quantidades = set()
    for _ in range(40):
        habilidades = client.post(URL_ALEATORIO, json={}, headers=admin_headers).json()["habilidades"]
        ids = [h["id"] for h in habilidades]
        assert len(ids) == len(set(ids)) and 1 <= len(ids) <= 3
        quantidades.add(len(ids))
    assert quantidades == {1, 2, 3}  # com 5 habilidades e 40 sorteios, os três tamanhos aparecem


def test_aleatorio_varia_entre_chamadas(client, admin_headers, muitas_habilidades, fixar_aleatorio):
    fixar_aleatorio(5)
    nomes = {
        client.post(URL_ALEATORIO, json={}, headers=admin_headers).json()["nome"] for _ in range(20)
    }
    assert len(nomes) > 1


@pytest.mark.parametrize(
    "modelo,codigo",
    [
        (models.ClasseModel, "SEM_CLASSES_CADASTRADAS"),
        (models.ArmaModel, "SEM_ARMAS_CADASTRADAS"),
        (models.FraquezaModel, "SEM_FRAQUEZAS_CADASTRADAS"),
        (models.HabilidadeModel, "SEM_HABILIDADES_CADASTRADAS"),
    ],
)
def test_aleatorio_sem_recurso_retorna_422_e_nao_grava(
    client, admin_headers, db, dados_base, modelo, codigo
):
    db.execute(modelo.__table__.delete())
    db.commit()
    resp = client.post(URL_ALEATORIO, json={}, headers=admin_headers)
    assert resp.status_code == 422
    assert resp.json()["codigo"] == codigo and resp.json()["status"] == 422
    assert "detail" not in resp.json()
    assert _total_personagens(db) == 0


def test_aleatorio_banco_vazio_reporta_so_a_primeira_falta(client, admin_headers):
    resp = client.post(URL_ALEATORIO, json={}, headers=admin_headers)
    assert resp.status_code == 422 and resp.json()["codigo"] == "SEM_CLASSES_CADASTRADAS"


def test_aleatorio_nome_invalido_retorna_422(client, admin_headers, db, dados_base):
    resp = client.post(URL_ALEATORIO, json={"nome": "A"}, headers=admin_headers)
    assert resp.status_code == 422 and resp.json()["codigo"] == "DADOS_INVALIDOS"
    assert _total_personagens(db) == 0


def test_aleatorio_json_malformado_retorna_400(client, admin_headers, dados_base):
    resp = client.post(URL_ALEATORIO, content="{nome:", headers={**admin_headers, **JSON})
    assert resp.status_code == 400 and resp.json()["codigo"] == "REQUISICAO_INVALIDA"


def test_aleatorio_sem_content_type_json_retorna_400(client, admin_headers, dados_base):
    resp = client.post(URL_ALEATORIO, headers=admin_headers)
    assert resp.status_code == 400 and resp.json()["codigo"] == "REQUISICAO_INVALIDA"


def test_aleatorio_sem_token_retorna_401(client, dados_base):
    resp = client.post(URL_ALEATORIO, json={})
    assert resp.status_code == 401 and resp.json()["codigo"] == "NAO_AUTENTICADO"


def test_aleatorio_nao_conflita_com_rotas_de_id(client, admin_headers, dados_base):
    # GET /aleatorio cai em /{id}: "aleatorio" não é inteiro => 400 (D5), nunca cria nada
    resp = client.get(URL_ALEATORIO, headers=admin_headers)
    assert resp.status_code == 400 and resp.json()["codigo"] == "REQUISICAO_INVALIDA"

