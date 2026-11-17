"""Contratos Pydantic v2 da API de Gerador de Personagens.

Espelha os Data Schemas do contrato `api_gerador_personagens.json` (Apidog) e
as extensões de Autenticação definidas no PLAN.md.

Convenções (STYLEGUIDE.md, seção 3.4):
- atributos em ``snake_case`` no Python, expostos em ``camelCase`` no JSON via
  ``Field(alias=...)``;
- ``id`` é inteiro (int64, mínimo 1), gerado pela API e somente leitura;
- schemas de saída NÃO têm restrições mais rígidas que os DTOs de entrada
  (PLAN.md, item 4.9), para não quebrar a serialização de dados válidos.

As respostas devem ser serializadas por alias (``response_model_by_alias``,
padrão do FastAPI) para preservar o camelCase do contrato.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Base e enums
# ---------------------------------------------------------------------------


class BaseSchema(BaseModel):
    """Base de todos os schemas da API."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class TipoArma(str, Enum):
    """Categoria da arma (enum do contrato)."""

    CORPO_A_CORPO = "corpo_a_corpo"
    DISTANCIA = "distancia"
    MAGICA = "magica"


class TipoHabilidade(str, Enum):
    """Categoria da habilidade (enum do contrato)."""

    FISICA = "fisica"
    MAGICA = "magica"
    SUPORTE = "suporte"


# ---------------------------------------------------------------------------
# Tipos reutilizáveis (restrições do contrato)
# ---------------------------------------------------------------------------

IdRecurso = Annotated[
    int,
    Field(ge=1, description="Identificador único gerado pela API.", examples=[1]),
]
IdReferencia = Annotated[int, Field(ge=1)]

Nome2a80 = Annotated[str, Field(min_length=2, max_length=80)]
Descricao10a500 = Annotated[str, Field(min_length=10, max_length=500)]
DanoBase = Annotated[int, Field(ge=0, le=100)]

NomeArma = Annotated[
    str,
    Field(
        min_length=4,
        max_length=80,
        description="Nome da arma/equipamento de ataque.",
        examples=["Espada longa"],
    ),
]
DanoArma = Annotated[
    int,
    Field(
        ge=0,
        le=100,
        description="Quantidade de dano base causada pela arma, entre 0 e 100.",
        examples=[25],
    ),
]
NomeClasse = Annotated[
    str,
    Field(
        min_length=2,
        max_length=80,
        description="Nome da classe do personagem.",
        examples=["Guerreiro"],
    ),
]
DescricaoClasse = Annotated[
    str,
    Field(
        min_length=10,
        max_length=500,
        description="Características e especialidades da classe.",
        examples=["Classe especializada em combate físico e uso de armas."],
    ),
]
NomeFraqueza = Annotated[
    str,
    Field(
        min_length=2,
        max_length=80,
        description="Nome que identifica a fraqueza.",
        examples=["Vulnerabilidade ao fogo"],
    ),
]
DescricaoFraqueza = Annotated[
    str,
    Field(
        min_length=10,
        max_length=500,
        description="Explicação da fraqueza e de seu efeito sobre o personagem.",
        examples=["O personagem recebe dano adicional de ataques de fogo."],
    ),
]
NomeHabilidade = Annotated[
    str,
    Field(
        min_length=2,
        max_length=80,
        description="Nome que identifica a habilidade.",
        examples=["Bola de fogo"],
    ),
]
DescricaoHabilidade = Annotated[
    str,
    Field(
        min_length=10,
        max_length=500,
        description="Explicação do efeito da habilidade.",
        examples=["Lança uma esfera de fogo contra um alvo."],
    ),
]
DanoHabilidade = Annotated[
    int,
    Field(
        ge=0,
        le=100,
        description="Quantidade de dano base; pode ser zero para habilidades sem dano.",
        examples=[40],
    ),
]
NomePersonagem = Annotated[
    str,
    Field(
        min_length=2,
        max_length=80,
        description="Nome do personagem.",
        examples=["Lyra"],
    ),
]


# ---------------------------------------------------------------------------
# Paginação genérica (itens, pagina, limite, total)
# ---------------------------------------------------------------------------

T = TypeVar("T")


class Pagina(BaseSchema, Generic[T]):
    """Envelope de listagem paginada do contrato."""

    itens: list[T] = Field(description="Recursos retornados na página atual.")
    pagina: int = Field(ge=1, description="Número da página atual.", examples=[1])
    limite: int = Field(
        ge=1,
        le=100,
        description="Quantidade máxima de itens por página.",
        examples=[10],
    )
    total: int = Field(
        ge=0,
        description="Total de recursos encontrados em todas as páginas.",
        examples=[1],
    )


# ---------------------------------------------------------------------------
# Arma
# ---------------------------------------------------------------------------


class CreateArmaDTO(BaseSchema):
    nome: NomeArma
    dano: DanoArma
    tipo: TipoArma = Field(description="Categoria da arma.", examples=["corpo_a_corpo"])


class UpdateArmaDTO(BaseSchema):
    nome: NomeArma
    dano: DanoArma
    tipo: TipoArma = Field(description="Categoria da arma.", examples=["corpo_a_corpo"])


class Arma(BaseSchema):
    id: IdRecurso
    nome: NomeArma
    dano: DanoArma
    tipo: TipoArma = Field(description="Categoria da arma.", examples=["corpo_a_corpo"])


class ListaArmas(Pagina[Arma]):
    pass


# ---------------------------------------------------------------------------
# Classe
# ---------------------------------------------------------------------------


class CreateClasseDTO(BaseSchema):
    nome: NomeClasse
    descricao: DescricaoClasse


class UpdateClasseDTO(BaseSchema):
    nome: NomeClasse
    descricao: DescricaoClasse


class Classe(BaseSchema):
    id: IdRecurso
    nome: NomeClasse
    descricao: DescricaoClasse


class ListaClasses(Pagina[Classe]):
    pass


# ---------------------------------------------------------------------------
# Fraqueza
# ---------------------------------------------------------------------------


class CreateFraquezaDTO(BaseSchema):
    nome: NomeFraqueza
    descricao: DescricaoFraqueza


class UpdateFraquezaDTO(BaseSchema):
    nome: NomeFraqueza
    descricao: DescricaoFraqueza


class Fraqueza(BaseSchema):
    id: IdRecurso
    nome: NomeFraqueza
    descricao: DescricaoFraqueza


class ListaFraquezas(Pagina[Fraqueza]):
    pass


# ---------------------------------------------------------------------------
# Habilidade
# ---------------------------------------------------------------------------


class CreateHabilidadeDTO(BaseSchema):
    nome: NomeHabilidade
    tipo: TipoHabilidade = Field(description="Categoria da habilidade.", examples=["magica"])
    descricao: DescricaoHabilidade
    dano: DanoHabilidade


class UpdateHabilidadeDTO(BaseSchema):
    nome: NomeHabilidade
    tipo: TipoHabilidade = Field(description="Categoria da habilidade.", examples=["magica"])
    descricao: DescricaoHabilidade
    dano: DanoHabilidade


class Habilidade(BaseSchema):
    id: IdRecurso
    nome: NomeHabilidade
    tipo: TipoHabilidade = Field(description="Categoria da habilidade.", examples=["magica"])
    descricao: DescricaoHabilidade
    dano: DanoHabilidade


class ListaHabilidades(Pagina[Habilidade]):
    pass


# ---------------------------------------------------------------------------
# Personagem
# ---------------------------------------------------------------------------

ClasseId = Annotated[
    int,
    Field(
        ge=1,
        alias="classeId",
        description="Identificador de uma classe existente.",
        examples=[1],
    ),
]
ArmaId = Annotated[
    int,
    Field(
        ge=1,
        alias="armaId",
        description="Identificador de uma arma existente.",
        examples=[1],
    ),
]
FraquezaId = Annotated[
    int,
    Field(
        ge=1,
        alias="fraquezaId",
        description="Identificador de uma fraqueza existente.",
        examples=[1],
    ),
]
HabilidadeIds = Annotated[
    list[IdReferencia],
    Field(
        min_length=1,
        alias="habilidadeIds",
        description="Identificadores das habilidades existentes atribuídas ao personagem.",
        examples=[[1, 2]],
    ),
]


def _rejeitar_ids_duplicados(valor: list[int]) -> list[int]:
    if len(set(valor)) != len(valor):
        raise ValueError("habilidadeIds não pode conter identificadores repetidos.")
    return valor


class CreatePersonagemDTO(BaseSchema):
    nome: NomePersonagem
    classe_id: ClasseId
    habilidade_ids: HabilidadeIds
    arma_id: ArmaId
    fraqueza_id: FraquezaId

    @field_validator("habilidade_ids")
    @classmethod
    def _sem_duplicados(cls, valor: list[int]) -> list[int]:
        return _rejeitar_ids_duplicados(valor)


class CreatePersonagemAleatorioDTO(BaseSchema):
    """Body opcional de ``POST /personagens/aleatorio`` (D11): só o nome pode ser escolhido."""

    nome: NomePersonagem | None = Field(
        default=None,
        description="Nome do personagem. Se omitido, a API gera um nome.",
    )


class UpdatePersonagemDTO(BaseSchema):
    nome: NomePersonagem
    classe_id: ClasseId
    habilidade_ids: HabilidadeIds
    arma_id: ArmaId
    fraqueza_id: FraquezaId

    @field_validator("habilidade_ids")
    @classmethod
    def _sem_duplicados(cls, valor: list[int]) -> list[int]:
        return _rejeitar_ids_duplicados(valor)


class Personagem(BaseSchema):
    id: IdRecurso
    nome: NomePersonagem
    classe: Classe
    habilidades: list[Habilidade] = Field(
        min_length=1,
        description="Habilidades atribuídas ao personagem.",
    )
    arma: Arma
    fraqueza: Fraqueza


class ListaPersonagens(Pagina[Personagem]):
    pass


# ---------------------------------------------------------------------------
# Erros (D1: formato ApiError do contrato)
# ---------------------------------------------------------------------------


class ApiError(BaseSchema):
    status: int = Field(ge=400, le=599, description="Código HTTP do erro.", examples=[404])
    codigo: str = Field(
        min_length=1,
        max_length=80,
        description="Identificador do tipo de erro, em MAIUSCULAS_COM_UNDERSCORE.",
        examples=["ARMA_NAO_ENCONTRADA"],
    )
    mensagem: str = Field(
        min_length=1,
        max_length=500,
        description="Explicação do erro para quem usa a API.",
        examples=["Não existe arma com o ID informado."],
    )


# ---------------------------------------------------------------------------
# Autenticação (extensão ao contrato — PLAN.md)
# ---------------------------------------------------------------------------


class LoginRequestDTO(BaseSchema):
    email: str = Field(
        min_length=3,
        max_length=254,
        description="E-mail do usuário.",
        examples=["admin@example.com"],
    )
    senha: str = Field(
        min_length=1,
        max_length=128,
        description="Senha do usuário.",
        examples=["senha-secreta"],
    )


class TokenResponseDTO(BaseSchema):
    access_token: str = Field(
        alias="accessToken",
        description="Token JWT (HS256) para o cabeçalho Authorization: Bearer.",
    )
    token_type: Literal["bearer"] = Field(
        default="bearer",
        alias="tokenType",
        description="Tipo do token.",
        examples=["bearer"],
    )
    expires_in: int = Field(
        ge=1,
        alias="expiresIn",
        description="Validade do token, em segundos.",
        examples=[3600],
    )


class UserResponse(BaseSchema):
    id: IdRecurso
    nome: str = Field(description="Nome do usuário.", examples=["Administrador"])
    email: str = Field(description="E-mail do usuário.", examples=["admin@example.com"])
    role: Literal["ADMIN", "MEMBER"] = Field(
        description="Papel do usuário (RBAC).", examples=["ADMIN"]
    )
