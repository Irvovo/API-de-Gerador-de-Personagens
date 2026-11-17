"""Persistência base: engine, sessão, dependência ``get_db``, criação e seed."""

import os
from collections.abc import Iterator

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from . import models

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./gerador_personagens.db")

_URLS_EM_MEMORIA = ("sqlite://", "sqlite:///:memory:")


def ativar_foreign_keys(engine: Engine) -> None:
    """Liga ``PRAGMA foreign_keys`` em toda nova conexão SQLite."""

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_connection, _record) -> None:  # pragma: no cover - callback do driver
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def criar_engine(url: str = DATABASE_URL) -> Engine:
    kwargs: dict = {}
    eh_sqlite = url.startswith("sqlite")
    if eh_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in _URLS_EM_MEMORIA:
            kwargs["poolclass"] = StaticPool  # uma única conexão => o banco em memória persiste
    engine = create_engine(url, **kwargs)
    if eh_sqlite:
        ativar_foreign_keys(engine)
    return engine


engine = criar_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependência FastAPI: uma sessão por requisição, sempre fechada."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(bind: Engine | None = None) -> None:
    """Cria as tabelas que ainda não existem."""
    models.Base.metadata.create_all(bind or engine)


# ---------------------------------------------------------------------------
# Seed (idempotente)
# ---------------------------------------------------------------------------

SEED_ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@example.com")
SEED_ADMIN_SENHA = os.getenv("SEED_ADMIN_SENHA", "Admin@123")
SEED_MEMBER_EMAIL = os.getenv("SEED_MEMBER_EMAIL", "member@example.com")
SEED_MEMBER_SENHA = os.getenv("SEED_MEMBER_SENHA", "Member@123")


def _semear_usuarios(db: Session) -> None:
    from .security import hash_senha  # import tardio: security depende deste módulo

    usuarios = [
        ("Administrador", SEED_ADMIN_EMAIL, SEED_ADMIN_SENHA, models.Role.ADMIN),
        ("Membro", SEED_MEMBER_EMAIL, SEED_MEMBER_SENHA, models.Role.MEMBER),
    ]
    for nome, email, senha, role in usuarios:
        existe = db.scalar(select(models.UserModel.id).where(models.UserModel.email == email))
        if existe is None:
            db.add(
                models.UserModel(nome=nome, email=email, senha_hash=hash_senha(senha), role=role)
            )


def _vazia(db: Session, model: type[models.Base]) -> bool:
    return (db.scalar(select(func.count()).select_from(model)) or 0) == 0


def _semear_recursos(db: Session) -> None:
    if _vazia(db, models.ClasseModel):
        db.add_all(
            [
                models.ClasseModel(
                    nome="Guerreiro",
                    descricao="Classe especializada em combate físico e uso de armas.",
                ),
                models.ClasseModel(
                    nome="Mago",
                    descricao="Classe que domina as artes arcanas e magias de longo alcance.",
                ),
                models.ClasseModel(
                    nome="Arqueiro",
                    descricao="Classe ágil, especializada em ataques precisos à distância.",
                ),
            ]
        )
    if _vazia(db, models.ArmaModel):
        db.add_all(
            [
                models.ArmaModel(nome="Espada longa", dano=25, tipo=models.TipoArma.CORPO_A_CORPO),
                models.ArmaModel(nome="Arco curto", dano=20, tipo=models.TipoArma.DISTANCIA),
                models.ArmaModel(nome="Cajado arcano", dano=30, tipo=models.TipoArma.MAGICA),
            ]
        )
    if _vazia(db, models.FraquezaModel):
        db.add_all(
            [
                models.FraquezaModel(
                    nome="Vulnerabilidade ao fogo",
                    descricao="O personagem recebe dano adicional de ataques de fogo.",
                ),
                models.FraquezaModel(
                    nome="Vulnerabilidade à prata",
                    descricao="Em contato direto com prata, a arma causa apenas metade do dano.",
                ),
            ]
        )
    if _vazia(db, models.HabilidadeModel):
        db.add_all(
            [
                models.HabilidadeModel(
                    nome="Bola de fogo",
                    tipo=models.TipoHabilidade.MAGICA,
                    descricao="Lança uma esfera de fogo contra um alvo.",
                    dano=40,
                ),
                models.HabilidadeModel(
                    nome="Golpe giratório",
                    tipo=models.TipoHabilidade.FISICA,
                    descricao="Gira a arma atingindo todos os inimigos próximos.",
                    dano=30,
                ),
                models.HabilidadeModel(
                    nome="Cura divina",
                    tipo=models.TipoHabilidade.SUPORTE,
                    descricao="Restaura a vida de um aliado próximo.",
                    dano=0,
                ),
            ]
        )


def seed_db(db: Session | None = None) -> None:
    """Insere usuários e dados de exemplo. Não duplica nada se já existirem."""
    propria = db is None
    sessao = db or SessionLocal()
    try:
        _semear_usuarios(sessao)
        _semear_recursos(sessao)
        sessao.commit()
    except Exception:
        sessao.rollback()
        raise
    finally:
        if propria:
            sessao.close()
