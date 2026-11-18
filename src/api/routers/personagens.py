"""CRUD de /api/v1/personagens (ORM com eager loading, protegido por JWT/RBAC)."""

import random
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..exceptions import (
    NaoEncontradoError,
    ReferenciaInvalidaError,
    SemRecursosError,
    respostas,
)
from ..models import (
    ArmaModel,
    ClasseModel,
    FraquezaModel,
    HabilidadeModel,
    PersonagemModel,
)
from ..schemas import (
    CreatePersonagemAleatorioDTO,
    CreatePersonagemDTO,
    ListaPersonagens,
    Personagem,
    UpdatePersonagemDTO,
)
from ..security import get_current_user, require_role

router = APIRouter(
    prefix="/personagens",
    tags=["Personagem"],
    dependencies=[Depends(get_current_user)],
)

IdPath = Annotated[
    int, Path(alias="id", ge=1, description="Identificador do personagem.")
]

# Uma consulta por relacionamento (selectinload): o total de queries não cresce
# com o número de personagens (sem N+1).
_EAGER = (
    selectinload(PersonagemModel.classe),
    selectinload(PersonagemModel.arma),
    selectinload(PersonagemModel.fraqueza),
    selectinload(PersonagemModel.habilidades),
)


MAX_HABILIDADES_ALEATORIO = 3  # maxItems de Personagem.habilidades no contrato (D11)

_NOMES = (
    "Thorgar", "Elara", "Zephyr", "Lyra", "Kael", "Brenna", "Dorian", "Selene",
    "Rurik", "Isolde", "Fenrir", "Mirael", "Garrick", "Nyx", "Alaric", "Thalia",
)
_EPITETOS = (
    "o Implacável", "a Sombria", "o Destemido", "a Veloz", "o Sábio", "a Lendária",
    "o Errante", "a Guardiã", "o Corvo", "a Tempestade", "o Último Herdeiro", "a Escarlate",
)


def get_aleatorio() -> random.Random:
    """Fonte de aleatoriedade da rota ``/aleatorio``; os testes a substituem por uma semente fixa."""
    return random.Random()


def _gerar_nome(rng: random.Random) -> str:
    return f"{rng.choice(_NOMES)}, {rng.choice(_EPITETOS)}"


def _sortear_id(db: Session, modelo: type, recurso: str, rng: random.Random) -> int:
    """Sorteia um ``id`` existente (só ids são carregados, não a tabela inteira)."""
    ids = list(db.scalars(select(modelo.id).order_by(modelo.id)))
    if not ids:
        raise SemRecursosError(recurso)
    return rng.choice(ids)


def _carregar(db: Session, personagem_id: int) -> PersonagemModel | None:
    return db.scalar(
        select(PersonagemModel).options(*_EAGER).where(PersonagemModel.id == personagem_id)
    )


def _obter_ou_404(db: Session, personagem_id: int) -> PersonagemModel:
    personagem = _carregar(db, personagem_id)
    if personagem is None:
        raise NaoEncontradoError("personagem")
    return personagem


def _validar_referencias(
    db: Session, dto: CreatePersonagemDTO | UpdatePersonagemDTO
) -> list[HabilidadeModel]:
    """D6: referência inexistente => 422 com ``codigo`` específico.

    Retorna as habilidades (ordenadas por id) quando tudo existe.
    """
    if db.get(ClasseModel, dto.classe_id) is None:
        raise ReferenciaInvalidaError("classe", "A classe informada em classeId não existe.")
    if db.get(ArmaModel, dto.arma_id) is None:
        raise ReferenciaInvalidaError("arma", "A arma informada em armaId não existe.")
    if db.get(FraquezaModel, dto.fraqueza_id) is None:
        raise ReferenciaInvalidaError("fraqueza", "A fraqueza informada em fraquezaId não existe.")

    habilidades = list(
        db.scalars(
            select(HabilidadeModel)
            .where(HabilidadeModel.id.in_(dto.habilidade_ids))
            .order_by(HabilidadeModel.id)
        )
    )
    inexistentes = sorted(set(dto.habilidade_ids) - {h.id for h in habilidades})
    if inexistentes:
        raise ReferenciaInvalidaError(
            "habilidade", f"Habilidades inexistentes em habilidadeIds: {inexistentes}."
        )
    return habilidades


@router.post(
    "",
    response_model=Personagem,
    status_code=201,
    summary="Criar personagem",
    description="Cadastra um personagem com nome, classe, habilidades, arma e fraqueza.",
    responses=respostas(400, 401, 422),
)
def criar_personagem(dto: CreatePersonagemDTO, db: Session = Depends(get_db)):
    habilidades = _validar_referencias(db, dto)
    personagem = PersonagemModel(
        nome=dto.nome,
        classe_id=dto.classe_id,
        arma_id=dto.arma_id,
        fraqueza_id=dto.fraqueza_id,
        habilidades=habilidades,
    )
    db.add(personagem)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _obter_ou_404(db, personagem.id)


@router.post(
    "/aleatorio",
    response_model=Personagem,
    status_code=201,
    summary="Criar personagem aleatório",
    description=(
        "Sorteia classe, arma, fraqueza e de 1 a 3 habilidades entre os registros existentes e "
        "cadastra o personagem. O body é opcional: `nome` define o nome; sem ele a API gera um."
    ),
    responses=respostas(400, 401, 422),
)
def criar_personagem_aleatorio(
    dto: Annotated[CreatePersonagemAleatorioDTO | None, Body()] = None,
    db: Session = Depends(get_db),
    rng: random.Random = Depends(get_aleatorio),
):
    # Ordem fixa das checagens (D11): classe, arma, fraqueza, habilidade.
    classe_id = _sortear_id(db, ClasseModel, "classe", rng)
    arma_id = _sortear_id(db, ArmaModel, "arma", rng)
    fraqueza_id = _sortear_id(db, FraquezaModel, "fraqueza", rng)
    ids_habilidades = list(db.scalars(select(HabilidadeModel.id).order_by(HabilidadeModel.id)))
    if not ids_habilidades:
        raise SemRecursosError("habilidade")
    quantidade = rng.randint(1, min(MAX_HABILIDADES_ALEATORIO, len(ids_habilidades)))
    escolhidas = rng.sample(ids_habilidades, quantidade)

    nome = dto.nome if dto is not None and dto.nome is not None else _gerar_nome(rng)
    personagem = PersonagemModel(
        nome=nome,
        classe_id=classe_id,
        arma_id=arma_id,
        fraqueza_id=fraqueza_id,
        habilidades=list(
            db.scalars(
                select(HabilidadeModel)
                .where(HabilidadeModel.id.in_(escolhidas))
                .order_by(HabilidadeModel.id)
            )
        ),
    )
    db.add(personagem)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _obter_ou_404(db, personagem.id)


@router.get(
    "",
    response_model=ListaPersonagens,
    summary="Listar personagens",
    description="Retorna uma lista paginada de personagens, com filtro opcional pelo nome.",
    responses=respostas(400, 401, 422),
)
def listar_personagens(
    pagina: Annotated[int, Query(ge=1, description="Número da página desejada.")] = 1,
    limite: Annotated[
        int, Query(ge=1, le=100, description="Quantidade máxima de itens por página.")
    ] = 10,
    nome: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=80,
            description="Filtra personagens cujo nome contém o texto informado.",
        ),
    ] = None,
    db: Session = Depends(get_db),
):
    filtros = []
    if nome is not None:
        filtros.append(PersonagemModel.nome.icontains(nome, autoescape=True))
    total = db.scalar(select(func.count()).select_from(PersonagemModel).where(*filtros)) or 0
    itens = db.scalars(
        select(PersonagemModel)
        .options(*_EAGER)
        .where(*filtros)
        .order_by(PersonagemModel.id)
        .offset((pagina - 1) * limite)
        .limit(limite)
    ).all()
    return ListaPersonagens(itens=itens, pagina=pagina, limite=limite, total=total)


@router.get(
    "/{id}",
    response_model=Personagem,
    summary="Buscar personagem por ID",
    responses=respostas(400, 401, 404, 422, recurso="personagem"),
)
def buscar_personagem(personagem_id: IdPath, db: Session = Depends(get_db)):
    return _obter_ou_404(db, personagem_id)


@router.put(
    "/{id}",
    response_model=Personagem,
    summary="Atualizar personagem",
    description="Substitui todos os dados editáveis, inclusive o conjunto de habilidades.",
    responses=respostas(400, 401, 404, 422, recurso="personagem"),
)
def atualizar_personagem(
    personagem_id: IdPath, dto: UpdatePersonagemDTO, db: Session = Depends(get_db)
):
    personagem = _obter_ou_404(db, personagem_id)
    habilidades = _validar_referencias(db, dto)
    personagem.nome = dto.nome
    personagem.classe_id = dto.classe_id
    personagem.arma_id = dto.arma_id
    personagem.fraqueza_id = dto.fraqueza_id
    personagem.habilidades = habilidades
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.expire(personagem)  # força recarregar classe/arma/fraqueza após trocar os ids
    return _obter_ou_404(db, personagem_id)


@router.delete(
    "/{id}",
    status_code=204,
    response_class=Response,
    summary="Excluir personagem",
    dependencies=[Depends(require_role("ADMIN"))],
    responses=respostas(400, 401, 403, 404, 422, recurso="personagem"),
)
def excluir_personagem(personagem_id: IdPath, db: Session = Depends(get_db)):
    personagem = _obter_ou_404(db, personagem_id)
    db.delete(personagem)  # o ORM remove também as linhas de personagem_habilidades
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return Response(status_code=204)
