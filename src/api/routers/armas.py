"""CRUD de /api/v1/armas (ORM + JWT/RBAC)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..exceptions import NaoEncontradoError, RecursoEmUsoError, respostas
from ..models import ArmaModel, PersonagemModel
from ..models import TipoArma as TipoArmaModel
from ..schemas import (
    Arma,
    CreateArmaDTO,
    ListaArmas,
    UpdateArmaDTO,
)
from ..security import get_current_user, require_role

router = APIRouter(
    prefix="/armas",
    tags=["Arma"],
    dependencies=[Depends(get_current_user)],
)

IdPath = Annotated[
    int, Path(alias="id", ge=1, description="Identificador da arma.")
]


def _obter_ou_404(db: Session, recurso_id: int) -> ArmaModel:
    recurso = db.get(ArmaModel, recurso_id)
    if recurso is None:
        raise NaoEncontradoError("arma")
    return recurso


@router.post(
    "",
    response_model=Arma,
    status_code=201,
    summary="Criar arma",
    description="Cadastra uma arma com nome, dano e tipo. O identificador é gerado pela API.",
    responses=respostas(400, 401, 422),
)
def criar_arma(dto: CreateArmaDTO, db: Session = Depends(get_db)):
    recurso = ArmaModel(
        nome=dto.nome,
        dano=dto.dano,
        tipo=TipoArmaModel(dto.tipo.value),
    )
    db.add(recurso)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(recurso)
    return recurso


@router.get(
    "",
    response_model=ListaArmas,
    summary="Listar armas",
    description="Retorna uma lista paginada de armas, com filtro opcional pelo nome.",
    responses=respostas(400, 401, 422),
)
def listar_armas(
    pagina: Annotated[int, Query(ge=1, description="Número da página desejada.")] = 1,
    limite: Annotated[
        int, Query(ge=1, le=100, description="Quantidade máxima de itens por página.")
    ] = 10,
    nome: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=80,
            description="Filtra armas cujo nome contém o texto informado.",
        ),
    ] = None,
    db: Session = Depends(get_db),
):
    filtros = []
    if nome is not None:
        filtros.append(ArmaModel.nome.icontains(nome, autoescape=True))
    total = db.scalar(select(func.count()).select_from(ArmaModel).where(*filtros)) or 0
    itens = db.scalars(
        select(ArmaModel)
        .where(*filtros)
        .order_by(ArmaModel.id)
        .offset((pagina - 1) * limite)
        .limit(limite)
    ).all()
    return ListaArmas(itens=itens, pagina=pagina, limite=limite, total=total)


@router.get(
    "/{id}",
    response_model=Arma,
    summary="Buscar arma por ID",
    responses=respostas(400, 401, 404, 422),
)
def buscar_arma(recurso_id: IdPath, db: Session = Depends(get_db)):
    return _obter_ou_404(db, recurso_id)


@router.put(
    "/{id}",
    response_model=Arma,
    summary="Atualizar arma",
    description="Substitui todos os dados editáveis. Todos os campos devem ser enviados.",
    responses=respostas(400, 401, 404, 422),
)
def atualizar_arma(recurso_id: IdPath, dto: UpdateArmaDTO, db: Session = Depends(get_db)):
    recurso = _obter_ou_404(db, recurso_id)
    recurso.nome = dto.nome
    recurso.dano = dto.dano
    recurso.tipo = TipoArmaModel(dto.tipo.value)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(recurso)
    return recurso


@router.delete(
    "/{id}",
    status_code=204,
    response_class=Response,
    summary="Excluir arma",
    description="Remove a arma. Retorna 409 se estiver vinculada a algum personagem.",
    dependencies=[Depends(require_role("ADMIN"))],
    responses=respostas(400, 401, 403, 404, 409, 422),
)
def excluir_arma(recurso_id: IdPath, db: Session = Depends(get_db)):
    recurso = _obter_ou_404(db, recurso_id)
    em_uso = db.scalar(
        select(func.count()).select_from(PersonagemModel).where(PersonagemModel.arma_id == recurso_id)
    )
    if em_uso:
        raise RecursoEmUsoError("arma")
    db.delete(recurso)
    try:
        db.commit()
    except IntegrityError as exc:  # rede de segurança: FK impediu a exclusão
        db.rollback()
        raise RecursoEmUsoError("arma") from exc
    except Exception:
        db.rollback()
        raise
    return Response(status_code=204)
