"""Ponta a ponta: processo MCP real (stdio) falando com um uvicorn real."""

import asyncio
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

RAIZ = Path(__file__).resolve().parents[3]
SERVER_PY = RAIZ / "src" / "mcp_server" / "server.py"


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def api_rodando(tmp_path):
    porta = _porta_livre()
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{(tmp_path / 'e2e.db').as_posix()}",
        "PBKDF2_ITERATIONS": "1000",
        "JWT_SECRET": "chave-e2e-com-mais-de-32-bytes-0123456789",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api.main:app", "--host", "127.0.0.1", "--port", str(porta)],
        cwd=RAIZ, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{porta}"
    try:
        limite = time.time() + 30
        while time.time() < limite:
            try:
                if httpx.get(f"{url}/docs", timeout=1).status_code == 200:
                    break
            except httpx.TransportError:
                time.sleep(0.2)
        else:
            pytest.fail("a API não subiu a tempo")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def _parametros(url, email="admin@example.com", senha="Admin@123"):
    return StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PY)],
        env={
            "GERADOR_API_URL": url,
            "GERADOR_API_EMAIL": email,
            "GERADOR_API_SENHA": senha,
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )


def _texto(resultado) -> str:
    return " ".join(getattr(c, "text", "") for c in resultado.content)


def test_fluxo_completo_pelo_protocolo_mcp(api_rodando):
    async def fluxo():
        async with Client(_parametros(api_rodando)) as cliente:
            ferramentas = {t.name for t in (await cliente.list_tools()).tools}
            assert {"listar", "criar_personagem", "excluir"} <= ferramentas

            eu = await cliente.call_tool("quem_sou_eu", {})
            assert eu.structured_content["role"] == "ADMIN"

            armas = await cliente.call_tool("listar", {"recurso": "armas"})
            assert armas.structured_content["total"] == 3  # dados de seed

            criada = await cliente.call_tool(
                "criar_arma", {"nome": "Machado de guerra", "dano": 35, "tipo": "corpo_a_corpo"}
            )
            arma_id = criada.structured_content["id"]

            apagada = await cliente.call_tool("excluir", {"recurso": "armas", "id": arma_id})
            assert apagada.structured_content["excluido"] is True

            erro = await cliente.call_tool("buscar", {"recurso": "armas", "id": arma_id})
            assert erro.is_error
            assert "404 ARMA_NAO_ENCONTRADA" in _texto(erro)

    asyncio.run(fluxo())


def test_member_recebe_403_ao_excluir_pelo_protocolo(api_rodando):
    async def fluxo():
        async with Client(_parametros(api_rodando, "member@example.com", "Member@123")) as cliente:
            eu = await cliente.call_tool("quem_sou_eu", {})
            assert eu.structured_content["role"] == "MEMBER"
            negado = await cliente.call_tool("excluir", {"recurso": "armas", "id": 1})
            assert negado.is_error and "403 ACESSO_NEGADO" in _texto(negado)
            ainda = await cliente.call_tool("buscar", {"recurso": "armas", "id": 1})
            assert not ainda.is_error

    asyncio.run(fluxo())


def test_api_fora_do_ar_gera_erro_claro(tmp_path):
    async def fluxo():
        url_morta = f"http://127.0.0.1:{_porta_livre()}"
        async with Client(_parametros(url_morta)) as cliente:
            resultado = await cliente.call_tool("listar", {"recurso": "armas"})
            assert resultado.is_error and "não está acessível" in _texto(resultado)

    asyncio.run(fluxo())
