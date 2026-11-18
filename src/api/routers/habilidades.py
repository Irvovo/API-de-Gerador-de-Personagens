"""CRUD de /api/v1/habilidades (ORM + JWT/RBAC)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..exceptions import NaoEncontradoError, RecursoEmUsoError, respostas
from ..models import HabilidadeModel, PersonagemHabilidadeModel
from ..models import TipoHabilidade as TipoHabilidadeModel
from ..schemas import (
    Habilidade,
    CreateHabilidadeDTO,
    ListaHabilidades,
    UpdateHabilidadeDTO,
)
from ..security import get_current_user, require_role

router = APIRouter(
    prefix="/habilidades",
    tags=["Habilidade"],
    dependencies=[Depends(get_current_user)],
)

IdPath = Annotated[
    int, Path(alias="id", ge=1, description="Identificador da habilidade.")
]


def _obter_ou_404(db: Session, recurso_id: int) -> HabilidadeModel:
    recurso = db.get(HabilidadeModel, recurso_id)
    if recurso is None:
        raise NaoEncontradoError("habilidade")
    return recurso


@router.post(
    "",
    response_model=Habilidade,
    status_code=201,
    summary="Criar habilidade",
    description="Cadastra uma habilidade com nome, tipo, descrição e dano. O identificador é gerado pela API.",
    responses=respostas(400, 401, 422),
)
def criar_habilidade(dto: CreateHabilidadeDTO, db: Session = Depends(get_db)):
    recurso = HabilidadeModel(
        nome=dto.nome,
        tipo=TipoHabilidadeModel(dto.tipo.value),
        descricao=dto.descricao,
        dano=dto.dano,
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
    response_model=ListaHabilidades,
    summary="Listar habilidades",
    description="Retorna uma lista paginada de habilidades, com filtro opcional pelo nome.",
    responses=respostas(400, 401, 422),
)
def listar_habilidades(
    pagina: Annotated[int, Query(ge=1, description="Número da página desejada.")] = 1,
    limite: Annotated[
        int, Query(ge=1, le=100, description="Quantidade máxima de itens por página.")
    ] = 10,
    nome: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=80,
            description="Filtra habilidades cujo nome contém o texto informado.",
        ),
    ] = None,
    db: Session = Depends(get_db),
):
    filtros = []
    if nome is not None:
        filtros.append(HabilidadeModel.nome.icontains(nome, autoescape=True))
    total = db.scalar(select(func.count()).select_from(HabilidadeModel).where(*filtros)) or 0
    itens = db.scalars(
        select(HabilidadeModel)
        .where(*filtros)
        .order_by(HabilidadeModel.id)
        .offset((pagina - 1) * limite)
        .limit(limite)
    ).all()
    return ListaHabilidades(itens=itens, pagina=pagina, limite=limite, total=total)


@router.get(
    "/{id}",
    response_model=Habilidade,
    summary="Buscar habilidade por ID",
    responses=respostas(400, 401, 404, 422, recurso="habilidade"),
)
def buscar_habilidade(recurso_id: IdPath, db: Session = Depends(get_db)):
    return _obter_ou_404(db, recurso_id)


@router.put(
    "/{id}",
    response_model=Habilidade,
    summary="Atualizar habilidade",
    description="Substitui todos os dados editáveis. Todos os campos devem ser enviados.",
    responses=respostas(400, 401, 404, 422, recurso="habilidade"),
)
def atualizar_habilidade(recurso_id: IdPath, dto: UpdateHabilidadeDTO, db: Session = Depends(get_db)):
    recurso = _obter_ou_404(db, recurso_id)
    recurso.nome = dto.nome
    recurso.tipo = TipoHabilidadeModel(dto.tipo.value)
    recurso.descricao = dto.descricao
    recurso.dano = dto.dano
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
    summary="Excluir habilidade",
    description="Remove a habilidade. Retorna 409 se estiver vinculada a algum personagem.",
    dependencies=[Depends(require_role("ADMIN"))],
    responses=respostas(400, 401, 403, 404, 409, 422, recurso="habilidade"),
)
def excluir_habilidade(recurso_id: IdPath, db: Session = Depends(get_db)):
    recurso = _obter_ou_404(db, recurso_id)
    em_uso = db.scalar(
        select(func.count()).select_from(PersonagemHabilidadeModel).where(PersonagemHabilidadeModel.habilidade_id == recurso_id)
    )
    if em_uso:
        raise RecursoEmUsoError("habilidade")
    db.delete(recurso)
    try:
        db.commit()
    except IntegrityError as exc:  # rede de segurança: FK impediu a exclusão
        db.rollback()
        raise RecursoEmUsoError("habilidade") from exc
    except Exception:
        db.rollback()
        raise
    return Response(status_code=204)
