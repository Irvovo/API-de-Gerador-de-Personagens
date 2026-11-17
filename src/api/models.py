"""Entidades ORM (SQLAlchemy 2.0, sintaxe declarativa moderna).

Somente ``Mapped[...]`` e ``mapped_column(...)`` (sem ``Column`` legado).

Integridade referencial (PLAN.md, D7): as FKs de ``personagens`` para classes,
armas e fraquezas, e a FK ``habilidade_id`` da tabela associativa, NÃO têm
``ondelete``: com ``PRAGMA foreign_keys=ON`` o banco impede excluir um recurso
em uso. Por isso os lados inversos ``personagens`` usam ``passive_deletes="all"``,
para o ORM não anular/remover vínculos por conta própria e deixar a decisão
(``409 RECURSO_EM_USO``) para a camada de rotas e para o banco.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarativa de todas as entidades."""


# ---------------------------------------------------------------------------
# Enums Python (valores idênticos aos do contrato)
# ---------------------------------------------------------------------------


class TipoArma(str, Enum):
    CORPO_A_CORPO = "corpo_a_corpo"
    DISTANCIA = "distancia"
    MAGICA = "magica"


class TipoHabilidade(str, Enum):
    FISICA = "fisica"
    MAGICA = "magica"
    SUPORTE = "suporte"


class Role(str, Enum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


def _enum_coluna(enum_cls: type[Enum], nome: str) -> SAEnum:
    """Enum persistido pelo *valor* (ex.: ``corpo_a_corpo``), como VARCHAR."""
    return SAEnum(
        enum_cls,
        name=nome,
        native_enum=False,
        length=20,
        values_callable=lambda e: [m.value for m in e],
    )


def _agora_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Usuários (autenticação / RBAC)
# ---------------------------------------------------------------------------


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(_enum_coluna(Role, "role"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_agora_utc)


# ---------------------------------------------------------------------------
# Recursos
# ---------------------------------------------------------------------------


class ClasseModel(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(80))
    descricao: Mapped[str] = mapped_column(String(500))

    personagens: Mapped[list[PersonagemModel]] = relationship(
        back_populates="classe", passive_deletes="all"
    )


class ArmaModel(Base):
    __tablename__ = "armas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(80))
    dano: Mapped[int] = mapped_column(Integer)
    tipo: Mapped[TipoArma] = mapped_column(_enum_coluna(TipoArma, "tipo_arma"))

    personagens: Mapped[list[PersonagemModel]] = relationship(
        back_populates="arma", passive_deletes="all"
    )


class FraquezaModel(Base):
    __tablename__ = "fraquezas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(80))
    descricao: Mapped[str] = mapped_column(String(500))

    personagens: Mapped[list[PersonagemModel]] = relationship(
        back_populates="fraqueza", passive_deletes="all"
    )


class HabilidadeModel(Base):
    __tablename__ = "habilidades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[TipoHabilidade] = mapped_column(_enum_coluna(TipoHabilidade, "tipo_habilidade"))
    descricao: Mapped[str] = mapped_column(String(500))
    dano: Mapped[int] = mapped_column(Integer)

    personagens: Mapped[list[PersonagemModel]] = relationship(
        secondary="personagem_habilidades",
        back_populates="habilidades",
        passive_deletes="all",
    )


# ---------------------------------------------------------------------------
# Tabela associativa Personagem <-> Habilidade (N:N)
# Declarada como classe mapeada para usar apenas mapped_column (sem Column).
# ---------------------------------------------------------------------------


class PersonagemHabilidadeModel(Base):
    __tablename__ = "personagem_habilidades"

    personagem_id: Mapped[int] = mapped_column(
        ForeignKey("personagens.id", ondelete="CASCADE"), primary_key=True
    )
    habilidade_id: Mapped[int] = mapped_column(
        ForeignKey("habilidades.id"), primary_key=True
    )


class PersonagemModel(Base):
    __tablename__ = "personagens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(80))
    classe_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    arma_id: Mapped[int] = mapped_column(ForeignKey("armas.id"), nullable=False)
    fraqueza_id: Mapped[int] = mapped_column(ForeignKey("fraquezas.id"), nullable=False)

    # N:1
    classe: Mapped[ClasseModel] = relationship(back_populates="personagens")
    arma: Mapped[ArmaModel] = relationship(back_populates="personagens")
    fraqueza: Mapped[FraquezaModel] = relationship(back_populates="personagens")
    # N:N
    habilidades: Mapped[list[HabilidadeModel]] = relationship(
        secondary="personagem_habilidades",
        back_populates="personagens",
        order_by="HabilidadeModel.id",
    )
