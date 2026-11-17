# syntax=docker/dockerfile:1

# ---------- Estágio 1: instala as dependências num virtualenv ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Só o arquivo de dependências vem primeiro: enquanto ele não mudar, o Docker
# reaproveita o cache desta camada e não baixa tudo de novo a cada alteração no código.
COPY src/api/requirements.txt ./requirements.txt

# pytest e httpx servem apenas para os testes; a API em execução não usa.
RUN grep -viE '^(pytest|httpx)==' requirements.txt > requirements-runtime.txt \
    && pip install -r requirements-runtime.txt


# ---------- Estágio 2: imagem final, enxuta e sem root ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DATABASE_URL="sqlite:////data/gerador_personagens.db"

# Usuário comum (uid 10001) e pasta /data para o arquivo SQLite.
RUN groupadd --system --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /data \
    && chown app:app /data

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app src/__init__.py ./src/__init__.py
COPY --chown=app:app src/api ./src/api

USER app

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/openapi.json', timeout=2)"]

# 0.0.0.0: escuta em todas as interfaces do container (com 127.0.0.1 o mapeamento de porta não funcionaria).
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
