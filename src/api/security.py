"""Segurança: hash de senha, JWT (HS256) e dependências RBAC."""

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .exceptions import AcessoNegadoError, NaoAutenticadoError
from .models import Role, UserModel

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me-in-production-0123456789")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
PBKDF2_ITERATIONS = int(os.getenv("PBKDF2_ITERATIONS", "600000"))

_PREFIXO_HASH = "pbkdf2_sha256"


# ---------------------------------------------------------------------------
# Senhas (D9): pbkdf2_hmac da biblioteca padrão
# ---------------------------------------------------------------------------


def hash_senha(senha: str) -> str:
    """Formato: ``pbkdf2_sha256$<iterações>$<salt hex>$<hash hex>``."""
    salt = os.urandom(16)
    derivada = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{_PREFIXO_HASH}${PBKDF2_ITERATIONS}${salt.hex()}${derivada.hex()}"


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    try:
        prefixo, iteracoes, salt_hex, hash_hex = hash_armazenado.split("$")
        if prefixo != _PREFIXO_HASH:
            return False
        derivada = hashlib.pbkdf2_hmac(
            "sha256", senha.encode("utf-8"), bytes.fromhex(salt_hex), int(iteracoes)
        )
        return hmac.compare_digest(derivada, bytes.fromhex(hash_hex))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


def criar_access_token(user: UserModel) -> str:
    agora = datetime.now(timezone.utc)
    role = user.role.value if isinstance(user.role, Role) else str(user.role)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": role,
        "iat": agora,
        "exp": agora + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decodificar_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise NaoAutenticadoError("Token expirado.") from exc
    except jwt.InvalidTokenError as exc:
        raise NaoAutenticadoError("Token inválido.") from exc


# ---------------------------------------------------------------------------
# Dependências
# ---------------------------------------------------------------------------

# auto_error=False: a ausência do cabeçalho vira 401 no formato ApiError
# (o padrão do FastAPI seria 403 com {"detail": ...}).
bearer_scheme = HTTPBearer(auto_error=False, description="Token JWT obtido em /api/v1/auth/login")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> UserModel:
    if credentials is None:
        raise NaoAutenticadoError("Cabeçalho Authorization: Bearer <token> ausente.")
    payload = decodificar_token(credentials.credentials)
    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError) as exc:
        raise NaoAutenticadoError("Token inválido.") from exc
    user = db.get(UserModel, user_id)
    if user is None:
        raise NaoAutenticadoError("Usuário do token não existe.")
    return user


def require_role(*roles: str | Role):
    """Fábrica de dependência: 403 se o papel do usuário não estiver em ``roles``."""
    permitidos = {Role(r) for r in roles}

    def _verificar(user: UserModel = Depends(get_current_user)) -> UserModel:
        if user.role not in permitidos:
            raise AcessoNegadoError()
        return user

    return _verificar
