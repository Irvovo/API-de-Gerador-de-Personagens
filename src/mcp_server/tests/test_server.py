"""Ferramentas do servidor MCP contra a API real (banco em memória)."""

import asyncio

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from src.mcp_server import server

NOMES_DAS_FERRAMENTAS = {
    "quem_sou_eu", "listar", "buscar", "excluir",
    "criar_arma", "atualizar_arma", "criar_classe", "atualizar_classe",
    "criar_fraqueza", "atualizar_fraqueza", "criar_habilidade", "atualizar_habilidade",
    "criar_personagem", "criar_personagem_aleatorio", "atualizar_personagem",
}


@pytest.fixture()
def mundo(como_admin, chamar):
    """Classe, arma, fraqueza e duas habilidades criadas pelas próprias ferramentas."""
    classe = chamar("criar_classe", nome="Guerreiro", descricao="Classe de combate físico e armas.")
    arma = chamar("criar_arma", nome="Espada longa", dano=25, tipo="corpo_a_corpo")
    fraqueza = chamar("criar_fraqueza", nome="Fogo", descricao="Recebe dano adicional de fogo.")
    h1 = chamar("criar_habilidade", nome="Bola de fogo", tipo="magica",
                descricao="Lança uma esfera de fogo.", dano=40)
    h2 = chamar("criar_habilidade", nome="Cura divina", tipo="suporte",
                descricao="Restaura a vida de um aliado.", dano=0)
    return {"classe": classe, "arma": arma, "fraqueza": fraqueza, "habilidades": [h1, h2]}


def _criar_personagem(chamar, mundo, nome="Lyra"):
    return chamar(
        "criar_personagem", nome=nome, classe_id=mundo["classe"]["id"],
        habilidade_ids=[h["id"] for h in mundo["habilidades"]],
        arma_id=mundo["arma"]["id"], fraqueza_id=mundo["fraqueza"]["id"],
    )


def test_expoe_as_ferramentas_esperadas():
    ferramentas = asyncio.run(server.mcp.list_tools())
    assert {t.name for t in ferramentas} == NOMES_DAS_FERRAMENTAS


def test_so_excluir_e_destrutiva_e_leitura_e_somente_leitura():
    ferramentas = {t.name: t for t in asyncio.run(server.mcp.list_tools())}
    assert ferramentas["excluir"].annotations.destructive_hint is True
    for nome in ("listar", "buscar", "quem_sou_eu"):
        assert ferramentas[nome].annotations.read_only_hint is True
    for nome in NOMES_DAS_FERRAMENTAS - {"excluir", "listar", "buscar", "quem_sou_eu"}:
        assert ferramentas[nome].annotations.destructive_hint is False


def test_quem_sou_eu(como_admin, chamar):
    assert chamar("quem_sou_eu") == {"id": 1, "nome": "Admin", "email": "admin@teste.com", "role": "ADMIN"}


def test_criar_e_listar_armas_com_paginacao_e_filtro(como_admin, chamar):
    for nome in ("Lanca Sagrada", "lanca curta", "Machado"):
        chamar("criar_arma", nome=nome, dano=10, tipo="distancia")
    todas = chamar("listar", recurso="armas")
    assert todas["total"] == 3 and (todas["pagina"], todas["limite"]) == (1, 10)
    pag = chamar("listar", recurso="armas", pagina=2, limite=2)
    assert len(pag["itens"]) == 1 and pag["total"] == 3
    filtradas = chamar("listar", recurso="armas", nome="LANCA")
    assert filtradas["total"] == 2


def test_buscar_atualizar_e_excluir_arma(como_admin, chamar):
    arma = chamar("criar_arma", nome="Espada longa", dano=25, tipo="corpo_a_corpo")
    assert chamar("buscar", recurso="armas", id=arma["id"]) == arma
    nova = chamar("atualizar_arma", id=arma["id"], nome="Espada encantada", dano=50, tipo="magica")
    assert nova == {"id": arma["id"], "nome": "Espada encantada", "dano": 50, "tipo": "magica"}
    assert chamar("buscar", recurso="armas", id=arma["id"]) == nova
    assert chamar("excluir", recurso="armas", id=arma["id"]) == {
        "excluido": True, "recurso": "armas", "id": arma["id"],
    }
    with pytest.raises(ToolError, match="404 ARMA_NAO_ENCONTRADA"):
        chamar("buscar", recurso="armas", id=arma["id"])


def test_classes_fraquezas_e_habilidades_criar_atualizar(como_admin, chamar):
    classe = chamar("criar_classe", nome="Mago", descricao="Domina as artes arcanas.")
    assert chamar("atualizar_classe", id=classe["id"], nome="Arquimago",
                  descricao="Mestre das artes arcanas.")["nome"] == "Arquimago"
    fraq = chamar("criar_fraqueza", nome="Luz", descricao="Passa duas rodadas sem atacar.")
    assert chamar("atualizar_fraqueza", id=fraq["id"], nome="Sombra",
                  descricao="Perde a visão em locais escuros.")["nome"] == "Sombra"
    hab = chamar("criar_habilidade", nome="Golpe", tipo="fisica", descricao="Um golpe forte.", dano=30)
    novo = chamar("atualizar_habilidade", id=hab["id"], nome="Golpe duplo", tipo="suporte",
                  descricao="Dois golpes rápidos.", dano=0)
    assert (novo["nome"], novo["tipo"], novo["dano"]) == ("Golpe duplo", "suporte", 0)


def test_criar_buscar_listar_e_atualizar_personagem(como_admin, chamar, mundo):
    p = _criar_personagem(chamar, mundo)
    assert p["nome"] == "Lyra" and p["classe"]["nome"] == "Guerreiro"
    assert [h["nome"] for h in p["habilidades"]] == ["Bola de fogo", "Cura divina"]
    assert chamar("buscar", recurso="personagens", id=p["id"]) == p
    assert chamar("listar", recurso="personagens")["total"] == 1

    nova_classe = chamar("criar_classe", nome="Paladino", descricao="Guerreiro sagrado.")
    atualizado = chamar(
        "atualizar_personagem", id=p["id"], nome="Lyra Nova", classe_id=nova_classe["id"],
        habilidade_ids=[mundo["habilidades"][1]["id"]],
        arma_id=mundo["arma"]["id"], fraqueza_id=mundo["fraqueza"]["id"],
    )
    assert atualizado["nome"] == "Lyra Nova" and atualizado["classe"]["nome"] == "Paladino"
    assert [h["nome"] for h in atualizado["habilidades"]] == ["Cura divina"]


def test_excluir_personagem_e_depois_o_recurso_que_ele_usava(como_admin, chamar, mundo):
    p = _criar_personagem(chamar, mundo)
    with pytest.raises(ToolError, match="409 RECURSO_EM_USO"):
        chamar("excluir", recurso="classes", id=mundo["classe"]["id"])
    chamar("excluir", recurso="personagens", id=p["id"])
    chamar("excluir", recurso="classes", id=mundo["classe"]["id"])
    assert chamar("listar", recurso="classes")["total"] == 0


def test_referencia_inexistente_vira_erro_legivel(como_admin, chamar, mundo):
    with pytest.raises(ToolError, match="422 CLASSE_NAO_ENCONTRADA"):
        chamar("criar_personagem", nome="Fantasma", classe_id=9999,
               habilidade_ids=[mundo["habilidades"][0]["id"]],
               arma_id=mundo["arma"]["id"], fraqueza_id=mundo["fraqueza"]["id"])


def test_parametros_invalidos_sao_barrados_antes_de_chamar_a_api(como_admin, chamar):
    with pytest.raises(ToolError):
        chamar("criar_arma", nome="ab", dano=10, tipo="magica")          # nome curto demais
    with pytest.raises(ToolError):
        chamar("criar_arma", nome="Espada", dano=101, tipo="magica")     # dano fora da faixa
    with pytest.raises(ToolError):
        chamar("criar_arma", nome="Espada", dano=10, tipo="lanca")       # tipo fora do enum
    with pytest.raises(ToolError):
        chamar("listar", recurso="monstros")                              # recurso desconhecido
    assert chamar("listar", recurso="armas")["total"] == 0


def test_member_nao_pode_excluir_mas_pode_criar_e_listar(como_member, chamar):
    arma = chamar("criar_arma", nome="Espada longa", dano=25, tipo="corpo_a_corpo")
    assert chamar("listar", recurso="armas")["total"] == 1
    with pytest.raises(ToolError, match="403 ACESSO_NEGADO"):
        chamar("excluir", recurso="armas", id=arma["id"])
    assert chamar("buscar", recurso="armas", id=arma["id"])["nome"] == "Espada longa"


def test_token_expirado_e_renovado_automaticamente(como_admin, chamar):
    chamar("quem_sou_eu")
    token_antigo = como_admin._token
    como_admin._token = "token-que-o-servidor-nao-aceita"
    assert chamar("quem_sou_eu")["role"] == "ADMIN"
    assert como_admin._token not in (None, "token-que-o-servidor-nao-aceita")
    assert isinstance(token_antigo, str)


def test_login_invalido_informa_falha_sem_vazar_a_senha(api_http, chamar):
    server.definir_cliente(server.ClienteApi(http=api_http, email="admin@teste.com", senha="senha-errada-123"))
    with pytest.raises(ToolError) as exc:
        chamar("quem_sou_eu")
    assert "Falha no login" in str(exc.value) and "401 NAO_AUTENTICADO" in str(exc.value)
    assert "senha-errada-123" not in str(exc.value)


def test_credenciais_ausentes(api_http, chamar):
    server.definir_cliente(server.ClienteApi(http=api_http, email="", senha=""))
    with pytest.raises(ToolError, match="GERADOR_API_EMAIL"):
        chamar("listar", recurso="armas")


def test_api_fora_do_ar(chamar):
    def _recusar(request):
        raise httpx.ConnectError("conexão recusada", request=request)

    cliente = httpx.Client(transport=httpx.MockTransport(_recusar), base_url="http://127.0.0.1:9")
    server.definir_cliente(server.ClienteApi(http=cliente, base_url="http://127.0.0.1:9", email="a@b.com", senha="x"))
    try:
        with pytest.raises(ToolError, match="não está acessível"):
            chamar("listar", recurso="armas")
    finally:
        server.definir_cliente(None)


def test_criar_personagem_aleatorio_sem_nome(como_admin, chamar, mundo):
    p = chamar("criar_personagem_aleatorio")
    assert p["id"] >= 1 and ", " in p["nome"]
    assert p["classe"]["id"] == mundo["classe"]["id"]
    assert p["arma"]["id"] == mundo["arma"]["id"]
    assert p["fraqueza"]["id"] == mundo["fraqueza"]["id"]
    ids_validos = {h["id"] for h in mundo["habilidades"]}
    assert 1 <= len(p["habilidades"]) <= 2 and {h["id"] for h in p["habilidades"]} <= ids_validos
    assert chamar("buscar", recurso="personagens", id=p["id"]) == p


def test_criar_personagem_aleatorio_com_nome(como_admin, chamar, mundo):
    assert chamar("criar_personagem_aleatorio", nome="Sir Teste")["nome"] == "Sir Teste"


def test_criar_personagem_aleatorio_sem_registros_vira_erro_legivel(como_admin, chamar):
    with pytest.raises(ToolError, match="422 SEM_CLASSES_CADASTRADAS"):
        chamar("criar_personagem_aleatorio")
    assert chamar("listar", recurso="personagens")["total"] == 0


def test_criar_personagem_aleatorio_barra_nome_curto(como_admin, chamar, mundo):
    with pytest.raises(ToolError):
        chamar("criar_personagem_aleatorio", nome="A")
    assert chamar("listar", recurso="personagens")["total"] == 0

