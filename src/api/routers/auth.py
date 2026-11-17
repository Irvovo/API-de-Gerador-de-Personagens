"""Autenticação: ``POST /api/v1/auth/login`` (público) e ``GET /api/v1/auth/me``."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..exceptions import NaoAutenticadoError, respostas
from ..models import UserModel
from ..schemas import LoginRequestDTO, TokenResponseDTO, UserResponse
from ..security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    criar_access_token,
    get_current_user,
    hash_senha,
    verificar_senha,
)

router = APIRouter(prefix="/auth", tags=["Autenticação"])

# Hash de uma senha qualquer: usado quando o e-mail não existe, para que o tempo
# de resposta não revele quais e-mails estão cadastrados.
_HASH_FALSO = hash_senha("senha-inexistente")


@router.post(
    "/login",
    response_model=TokenResponseDTO,
    summary="Autenticar usuário",
    description="Valida e-mail e senha e devolve um token JWT (Bearer).",
    responses=respostas(400, 401, 422),
)
def login(dto: LoginRequestDTO, db: Session = Depends(get_db)) -> TokenResponseDTO:
    user = db.scalar(select(UserModel).where(func.lower(UserModel.email) == dto.email.lower()))
    senha_ok = verificar_senha(dto.senha, user.senha_hash if user else _HASH_FALSO)
    if user is None or not senha_ok:
        raise NaoAutenticadoError("E-mail ou senha inválidos.")
    return TokenResponseDTO(
        access_token=criar_access_token(user),
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Usuário autenticado",
    responses=respostas(401),
)
def me(user: UserModel = Depends(get_current_user)) -> UserModel:
    return user
