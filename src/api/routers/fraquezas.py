"""CRUD de /api/v1/fraquezas (ORM + JWT/RBAC)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..exceptions import NaoEncontradoError, RecursoEmUsoError, respostas
from ..models import FraquezaModel, PersonagemModel
from ..schemas import (
    Fraqueza,
    CreateFraquezaDTO,
    ListaFraquezas,
    UpdateFraquezaDTO,
)
from ..security import get_current_user, require_role

router = APIRouter(
    prefix="/fraquezas",
    tags=["Fraqueza"],
    dependencies=[Depends(get_current_user)],
)

IdPath = Annotated[
    int, Path(alias="id", ge=1, description="Identificador da fraqueza.")
]


def _obter_ou_404(db: Session, recurso_id: int) -> FraquezaModel:
    recurso = db.get(FraquezaModel, recurso_id)
    if recurso is None:
        raise NaoEncontradoError("fraqueza")
    return recurso


@router.post(
    "",
    response_model=Fraqueza,
    status_code=201,
    summary="Criar fraqueza",
    description="Cadastra uma fraqueza com nome e descrição. O identificador é gerado pela API.",
    responses=respostas(400, 401, 422),
)
def criar_fraqueza(dto: CreateFraquezaDTO, db: Session = Depends(get_db)):
    recurso = FraquezaModel(
        nome=dto.nome,
        descricao=dto.descricao,
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
    response_model=ListaFraquezas,
    summary="Listar fraquezas",
    description="Retorna uma lista paginada de fraquezas, com filtro opcional pelo nome.",
    responses=respostas(400, 401, 422),
)
def listar_fraquezas(
    pagina: Annotated[int, Query(ge=1, description="Número da página desejada.")] = 1,
    limite: Annotated[
        int, Query(ge=1, le=100, description="Quantidade máxima de itens por página.")
    ] = 10,
    nome: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=80,
            description="Filtra fraquezas cujo nome contém o texto informado.",
        ),
    ] = None,
    db: Session = Depends(get_db),
):
    filtros = []
    if nome is not None:
        filtros.append(FraquezaModel.nome.icontains(nome, autoescape=True))
    total = db.scalar(select(func.count()).select_from(FraquezaModel).where(*filtros)) or 0
    itens = db.scalars(
        select(FraquezaModel)
        .where(*filtros)
        .order_by(FraquezaModel.id)
        .offset((pagina - 1) * limite)
        .limit(limite)
    ).all()
    return ListaFraquezas(itens=itens, pagina=pagina, limite=limite, total=total)


@router.get(
    "/{id}",
    response_model=Fraqueza,
    summary="Buscar fraqueza por ID",
    responses=respostas(400, 401, 404, 422),
)
def buscar_fraqueza(recurso_id: IdPath, db: Session = Depends(get_db)):
    return _obter_ou_404(db, recurso_id)


@router.put(
    "/{id}",
    response_model=Fraqueza,
    summary="Atualizar fraqueza",
    description="Substitui todos os dados editáveis. Todos os campos devem ser enviados.",
    responses=respostas(400, 401, 404, 422),
)
def atualizar_fraqueza(recurso_id: IdPath, dto: UpdateFraquezaDTO, db: Session = Depends(get_db)):
    recurso = _obter_ou_404(db, recurso_id)
    recurso.nome = dto.nome
    recurso.descricao = dto.descricao
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
    summary="Excluir fraqueza",
    description="Remove a fraqueza. Retorna 409 se estiver vinculada a algum personagem.",
    dependencies=[Depends(require_role("ADMIN"))],
    responses=respostas(400, 401, 403, 404, 409, 422),
)
def excluir_fraqueza(recurso_id: IdPath, db: Session = Depends(get_db)):
    recurso = _obter_ou_404(db, recurso_id)
    em_uso = db.scalar(
        select(func.count()).select_from(PersonagemModel).where(PersonagemModel.fraqueza_id == recurso_id)
    )
    if em_uso:
        raise RecursoEmUsoError("fraqueza")
    db.delete(recurso)
    try:
        db.commit()
    except IntegrityError as exc:  # rede de segurança: FK impediu a exclusão
        db.rollback()
        raise RecursoEmUsoError("fraqueza") from exc
    except Exception:
        db.rollback()
        raise
    return Response(status_code=204)
