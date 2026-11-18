"""CRUD de /api/v1/classes (ORM + JWT/RBAC)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..exceptions import NaoEncontradoError, RecursoEmUsoError, respostas
from ..models import ClasseModel, PersonagemModel
from ..schemas import (
    Classe,
    CreateClasseDTO,
    ListaClasses,
    UpdateClasseDTO,
)
from ..security import get_current_user, require_role

router = APIRouter(
    prefix="/classes",
    tags=["Classe"],
    dependencies=[Depends(get_current_user)],
)

IdPath = Annotated[
    int, Path(alias="id", ge=1, description="Identificador da classe.")
]


def _obter_ou_404(db: Session, recurso_id: int) -> ClasseModel:
    recurso = db.get(ClasseModel, recurso_id)
    if recurso is None:
        raise NaoEncontradoError("classe")
    return recurso


@router.post(
    "",
    response_model=Classe,
    status_code=201,
    summary="Criar classe",
    description="Cadastra uma classe com nome e descrição. O identificador é gerado pela API.",
    responses=respostas(400, 401, 422),
)
def criar_classe(dto: CreateClasseDTO, db: Session = Depends(get_db)):
    recurso = ClasseModel(
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
    response_model=ListaClasses,
    summary="Listar classes",
    description="Retorna uma lista paginada de classes, com filtro opcional pelo nome.",
    responses=respostas(400, 401, 422),
)
def listar_classes(
    pagina: Annotated[int, Query(ge=1, description="Número da página desejada.")] = 1,
    limite: Annotated[
        int, Query(ge=1, le=100, description="Quantidade máxima de itens por página.")
    ] = 10,
    nome: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=80,
            description="Filtra classes cujo nome contém o texto informado.",
        ),
    ] = None,
    db: Session = Depends(get_db),
):
    filtros = []
    if nome is not None:
        filtros.append(ClasseModel.nome.icontains(nome, autoescape=True))
    total = db.scalar(select(func.count()).select_from(ClasseModel).where(*filtros)) or 0
    itens = db.scalars(
        select(ClasseModel)
        .where(*filtros)
        .order_by(ClasseModel.id)
        .offset((pagina - 1) * limite)
        .limit(limite)
    ).all()
    return ListaClasses(itens=itens, pagina=pagina, limite=limite, total=total)


@router.get(
    "/{id}",
    response_model=Classe,
    summary="Buscar classe por ID",
    responses=respostas(400, 401, 404, 422, recurso="classe"),
)
def buscar_classe(recurso_id: IdPath, db: Session = Depends(get_db)):
    return _obter_ou_404(db, recurso_id)


@router.put(
    "/{id}",
    response_model=Classe,
    summary="Atualizar classe",
    description="Substitui todos os dados editáveis. Todos os campos devem ser enviados.",
    responses=respostas(400, 401, 404, 422, recurso="classe"),
)
def atualizar_classe(recurso_id: IdPath, dto: UpdateClasseDTO, db: Session = Depends(get_db)):
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
    summary="Excluir classe",
    description="Remove a classe. Retorna 409 se estiver vinculada a algum personagem.",
    dependencies=[Depends(require_role("ADMIN"))],
    responses=respostas(400, 401, 403, 404, 409, 422, recurso="classe"),
)
def excluir_classe(recurso_id: IdPath, db: Session = Depends(get_db)):
    recurso = _obter_ou_404(db, recurso_id)
    em_uso = db.scalar(
        select(func.count()).select_from(PersonagemModel).where(PersonagemModel.classe_id == recurso_id)
    )
    if em_uso:
        raise RecursoEmUsoError("classe")
    db.delete(recurso)
    try:
        db.commit()
    except IntegrityError as exc:  # rede de segurança: FK impediu a exclusão
        db.rollback()
        raise RecursoEmUsoError("classe") from exc
    except Exception:
        db.rollback()
        raise
    return Response(status_code=204)
